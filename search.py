"""Site-wide search.

Deliberately plain: lowercase substring matching in SQLite, scored in Python.
The whole corpus is a few hundred rows, so an index (FTS5) would add schema and
rebuild complexity to solve a problem this content does not have. If the corpus
ever grows past a few thousand topics, this is the module to replace -- the
callers only depend on `search_all` and `highlight`.

No Flask imports: results are model objects plus metadata, and the templates
build the URLs. That keeps this testable without a request context.
"""

import re
from html import escape

from markupsafe import Markup

from formatting import plain_text
from models import Course, Lesson, Objective, Phase, Topic

MIN_QUERY_LENGTH = 2
SNIPPET_RADIUS = 90

# Where a match lands says how relevant it is: a hit in a title is a much
# stronger signal than the same word buried in a paragraph.
SCORE_TITLE_EXACT = 100
SCORE_TITLE_PREFIX = 80
SCORE_TITLE_CONTAINS = 60
SCORE_CODE = 50
SCORE_SUMMARY = 40
SCORE_BODY = 20


class Hit:
    """One search result: what matched, how strongly, and the text to show."""

    __slots__ = ("kind", "obj", "score", "snippet")

    def __init__(self, kind, obj, score, snippet=""):
        self.kind = kind
        self.obj = obj
        self.score = score
        self.snippet = snippet

    def to_dict(self):
        data = {"kind": self.kind, "score": self.score, "snippet": self.snippet}
        if self.kind == "topic":
            data.update(
                {
                    "slug": self.obj.slug,
                    "title": self.obj.title,
                    "course": self.obj.lesson.course.code,
                    "lesson": self.obj.lesson.number,
                }
            )
        elif self.kind == "lesson":
            data.update(
                {
                    "number": self.obj.number,
                    "title": self.obj.title,
                    "course": self.obj.course.code,
                }
            )
        elif self.kind == "course":
            data.update({"code": self.obj.code, "title": self.obj.title})
        elif self.kind == "objective":
            data.update({"code": self.obj.code, "title": self.obj.title})
        elif self.kind == "phase":
            data.update({"slug": self.obj.slug, "title": self.obj.name})
        return data


def _title_score(title, query):
    lowered = (title or "").lower()
    if lowered == query:
        return SCORE_TITLE_EXACT
    if lowered.startswith(query):
        return SCORE_TITLE_PREFIX
    if query in lowered:
        return SCORE_TITLE_CONTAINS
    return 0


def _snippet(text, query):
    """A window of body text centred on the match, so the reader can see why
    the result came back without opening it."""
    flat = plain_text(text)
    position = flat.lower().find(query)
    if position < 0:
        return flat[: SNIPPET_RADIUS * 2] + ("…" if len(flat) > SNIPPET_RADIUS * 2 else "")

    start = max(0, position - SNIPPET_RADIUS)
    end = min(len(flat), position + len(query) + SNIPPET_RADIUS)
    return ("…" if start > 0 else "") + flat[start:end] + ("…" if end < len(flat) else "")


def search_all(query, limit_per_kind=15):
    """Return {kind: [Hit, ...]} ordered best-first within each kind."""
    normalised = (query or "").strip().lower()
    results = {"topic": [], "lesson": [], "course": [], "objective": [], "phase": []}

    if len(normalised) < MIN_QUERY_LENGTH:
        return results

    for topic in Topic.query.all():
        score = _title_score(topic.title, normalised)
        if normalised in (topic.summary or "").lower():
            score += SCORE_SUMMARY
        body_hit = normalised in plain_text(topic.body).lower()
        if body_hit:
            score += SCORE_BODY
        if any(normalised in objective.code.lower() for objective in topic.objectives):
            score += SCORE_CODE
        if score:
            snippet = topic.summary or ""
            if body_hit and not (topic.summary and normalised in topic.summary.lower()):
                snippet = _snippet(topic.body, normalised)
            results["topic"].append(Hit("topic", topic, score, snippet))

    for lesson in Lesson.query.all():
        score = _title_score(lesson.title, normalised)
        if score:
            plural = "s" if len(lesson.topics) != 1 else ""
            results["lesson"].append(
                Hit("lesson", lesson, score, f"{len(lesson.topics)} topic{plural}")
            )

    for course in Course.query.all():
        score = _title_score(course.title, normalised)
        if normalised in course.code.lower():
            score += SCORE_CODE
        if normalised in (course.description or "").lower():
            score += SCORE_BODY
        if score:
            results["course"].append(Hit("course", course, score, plain_text(course.description)))

    for objective in Objective.query.all():
        score = _title_score(objective.title, normalised)
        if normalised in objective.code.lower():
            score += SCORE_CODE
        if score:
            plural = "s" if len(objective.topics) != 1 else ""
            results["objective"].append(
                Hit("objective", objective, score, f"{len(objective.topics)} topic{plural}")
            )

    for phase in Phase.query.all():
        score = _title_score(phase.name, normalised)
        if normalised in (phase.summary or "").lower():
            score += SCORE_BODY
        if score:
            results["phase"].append(Hit("phase", phase, score, plain_text(phase.summary)))

    for kind, hits in results.items():
        hits.sort(key=lambda hit: -hit.score)
        results[kind] = hits[:limit_per_kind]

    return results


def total_hits(results):
    return sum(len(hits) for hits in results.values())


def highlight(text, query):
    """Escape `text`, then wrap every occurrence of `query` in <mark>."""
    if not text:
        return Markup("")

    escaped = escape(str(text))
    normalised = (query or "").strip()
    if len(normalised) < MIN_QUERY_LENGTH:
        return Markup(escaped)

    pattern = re.compile(re.escape(escape(normalised)), re.IGNORECASE)
    return Markup(pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", escaped))
