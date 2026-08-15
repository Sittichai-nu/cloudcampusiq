"""Build the database from the YAML files in content/.

The YAML is the source of truth and lives in version control. SQLite is a
disposable read cache that is thrown away and rebuilt from scratch -- so the
only way to change what the site says is to change a content file, and every
change to the site's content shows up in `git log`.

Validation is strict on purpose. An unknown topic kind, a phase that does not
exist, a `related` slug pointing at nothing, or a malformed diagram spec all
raise here, at build time, rather than rendering as a blank panel that nobody
notices for a month.
"""

import json
import re
from pathlib import Path

import yaml

from models import (
    Course,
    Domain,
    Lesson,
    Objective,
    Phase,
    Topic,
    TopicLink,
    TopicStep,
    Visual,
    TOPIC_KINDS,
    domain_code_for,
    objective_sort_key,
)
from visuals import VisualError, render

CONTENT_DIR = Path(__file__).parent / "content"

OBJECTIVE_CODE = re.compile(r"^\d+\.\d+$")


class ContentError(ValueError):
    """A content file is malformed. Always names the file and the item."""


def _require(data, field, context):
    if not isinstance(data, dict) or field not in data or data[field] in (None, ""):
        raise ContentError(f"{context} is missing required field '{field}'")
    return data[field]


def _read_yaml(path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise ContentError(f"{path} is not valid YAML: {error}") from error


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    if not slug:
        raise ContentError(f"cannot build a slug from {value!r}")
    return slug[:80]


def _parse_objective_codes(topic_data, context):
    """Accept either the list form (`objectives: ["2.1"]`) or the older comma
    string (`objective_tags: "2.1, 4.1"`)."""
    codes = topic_data.get("objectives")
    if codes is None:
        raw = topic_data.get("objective_tags", "")
        codes = [part.strip() for part in str(raw).split(",")]

    cleaned = []
    for code in codes:
        code = str(code).strip()
        if not code:
            continue
        if not OBJECTIVE_CODE.match(code):
            raise ContentError(
                f"{context} has objective '{code}' -- expected a code like '2.1'"
            )
        if code not in cleaned:
            cleaned.append(code)
    return cleaned


class _Loader:
    def __init__(self, db):
        self.db = db
        self.domains = {}
        self.objectives = {}
        self.phases = {}
        self.topics_by_slug = {}
        self.pending_links = []
        self.stats = {
            "courses": 0,
            "lessons": 0,
            "topics": 0,
            "steps": 0,
            "visuals": 0,
            "domains": 0,
            "objectives": 0,
            "phases": 0,
        }

    # -- shared taxonomy -------------------------------------------------

    def domain(self, code, title="", summary=""):
        domain = self.domains.get(code)
        if domain is None:
            domain = Domain(
                code=code,
                title=title,
                summary=summary,
                order=int(code.partition(".")[0]),
            )
            self.db.session.add(domain)
            self.db.session.flush()
            self.domains[code] = domain
            self.stats["domains"] += 1
        else:
            # A declaration in domains.yaml fills in a domain that content
            # already referenced by bare code.
            if title:
                domain.title = title
            if summary:
                domain.summary = summary
        return domain

    def objective(self, code, title="", exam_points=None):
        points = "\n".join(str(point).strip() for point in (exam_points or []))
        objective = self.objectives.get(code)
        if objective is None:
            domain = self.domain(domain_code_for(code))
            objective = Objective(
                code=code,
                title=title,
                domain_id=domain.id,
                sort_key=objective_sort_key(code),
                exam_points=points,
            )
            self.db.session.add(objective)
            self.db.session.flush()
            self.objectives[code] = objective
            self.stats["objectives"] += 1
        else:
            # A topic may reference an objective before domains.yaml is read;
            # the declaration fills in what the bare reference could not.
            if title:
                objective.title = title
            if points:
                objective.exam_points = points
        return objective

    def load_domains(self, path):
        if not path.exists():
            return
        data = _read_yaml(path)
        for entry in data.get("domains", []):
            code = _require(entry, "code", f"{path}")
            domain = self.domain(code, entry.get("title", ""), entry.get("summary", ""))
            for objective_entry in entry.get("objectives", []):
                objective_code = _require(objective_entry, "code", f"{path} :: {code}")
                if domain_code_for(objective_code) != code:
                    raise ContentError(
                        f"{path}: objective '{objective_code}' is listed under domain "
                        f"'{code}' but its code belongs to domain "
                        f"'{domain_code_for(objective_code)}'"
                    )
                self.objective(
                    objective_code,
                    objective_entry.get("title", ""),
                    objective_entry.get("exam_points", []),
                )

    def load_phases(self, path):
        if not path.exists():
            return
        data = _read_yaml(path)
        for order, entry in enumerate(data.get("phases", []), start=1):
            context = f"{path} :: phase #{order}"
            name = _require(entry, "name", context)
            slug = entry.get("slug") or slugify(name)
            if slug in self.phases:
                raise ContentError(f"{context} reuses phase slug '{slug}'")
            phase = Phase(
                slug=slug,
                name=name,
                order=entry.get("order", order),
                summary=entry.get("summary", ""),
            )
            self.db.session.add(phase)
            self.db.session.flush()
            self.phases[slug] = phase
            self.stats["phases"] += 1

    # -- courses ---------------------------------------------------------

    def load_course(self, course_dir):
        course_yaml = course_dir / "course.yaml"
        data = _read_yaml(course_yaml)

        course = Course(
            code=str(_require(data, "code", f"{course_yaml}")).upper(),
            title=_require(data, "title", f"{course_yaml}"),
            description=_require(data, "description", f"{course_yaml}"),
        )
        self.db.session.add(course)
        self.db.session.flush()
        self.stats["courses"] += 1

        for lesson_yaml in sorted(course_dir.glob("lesson_*.yaml")):
            self.load_lesson(course, lesson_yaml)

    def load_lesson(self, course, lesson_yaml):
        data = _read_yaml(lesson_yaml)
        context = f"{lesson_yaml}"

        verified = _require(data, "verified", context)
        source = _require(data, "source", context)

        lesson = Lesson(
            course_id=course.id,
            number=_require(data, "number", context),
            title=_require(data, "title", context),
            verified=verified,
            source=source,
        )
        self.db.session.add(lesson)
        self.db.session.flush()
        self.stats["lessons"] += 1

        for index, topic_data in enumerate(data.get("topics", []), start=1):
            self.load_topic(lesson, topic_data, index, lesson_yaml, verified, source)

    def load_topic(self, lesson, topic_data, index, lesson_yaml, verified, source):
        title = _require(topic_data, "title", f"{lesson_yaml} :: topic #{index}")
        context = f"{lesson_yaml} :: topic '{title}'"

        slug = topic_data.get("slug") or slugify(title)
        if slug in self.topics_by_slug:
            raise ContentError(
                f"{context} uses slug '{slug}', which is already taken by "
                f"'{self.topics_by_slug[slug].title}'. Slugs are URLs -- they must be unique."
            )

        kind = topic_data.get("kind", "concept")
        if kind not in TOPIC_KINDS:
            raise ContentError(
                f"{context} has kind '{kind}' -- expected one of {', '.join(TOPIC_KINDS)}"
            )

        phase = None
        phase_slug = topic_data.get("phase")
        if phase_slug:
            phase = self.phases.get(phase_slug)
            if phase is None:
                known = ", ".join(sorted(self.phases)) or "none defined"
                raise ContentError(
                    f"{context} names phase '{phase_slug}', which is not in phases.yaml "
                    f"(known phases: {known})"
                )

        topic = Topic(
            lesson_id=lesson.id,
            slug=slug,
            order=topic_data.get("order", index),
            title=title,
            summary=topic_data.get("summary", ""),
            kind=kind,
            body=_require(topic_data, "body", context),
            phase_id=phase.id if phase else None,
            # A topic inherits its lesson's verification unless it says otherwise.
            verified=topic_data.get("verified", verified),
            source=topic_data.get("source", source),
        )
        self.db.session.add(topic)
        self.db.session.flush()
        self.topics_by_slug[slug] = topic
        self.stats["topics"] += 1

        for code in _parse_objective_codes(topic_data, context):
            topic.objectives.append(self.objective(code))

        for step_index, step_data in enumerate(topic_data.get("steps", []), start=1):
            step_context = f"{context} :: step #{step_index}"
            self.db.session.add(
                TopicStep(
                    topic_id=topic.id,
                    order=step_data.get("order", step_index),
                    title=_require(step_data, "title", step_context),
                    body=step_data.get("body", ""),
                )
            )
            self.stats["steps"] += 1

        visual_data = topic_data.get("visual")
        if visual_data:
            self.load_visual(topic, visual_data, context)

        # `related` accepts a bare slug or {slug, note} when the edge deserves
        # an explanation.
        for entry in topic_data.get("related", []) or []:
            if isinstance(entry, dict):
                related_slug = _require(entry, "slug", f"{context} :: related")
                note = entry.get("note", "")
            else:
                related_slug, note = entry, ""
            self.pending_links.append((topic, str(related_slug), note, context))

    def load_visual(self, topic, visual_data, context):
        kind = _require(visual_data, "kind", f"{context} :: visual")
        data = _require(visual_data, "data", f"{context} :: visual")

        # Render once now so a broken spec fails the build instead of showing
        # up as an empty panel at request time.
        try:
            render(kind, data, visual_data.get("title", ""))
        except VisualError as error:
            raise ContentError(f"{context} :: visual — {error}") from error

        self.db.session.add(
            Visual(
                topic_id=topic.id,
                kind=kind,
                title=visual_data.get("title", ""),
                caption=visual_data.get("caption", ""),
                spec=json.dumps(data),
            )
        )
        self.stats["visuals"] += 1

    def resolve_links(self):
        """Second pass: `related` can point forward to a topic defined in a
        later file, so links are only resolvable once every topic exists."""
        for topic, related_slug, note, context in self.pending_links:
            related = self.topics_by_slug.get(related_slug)
            if related is None:
                known = ", ".join(sorted(self.topics_by_slug))
                raise ContentError(
                    f"{context} is related to '{related_slug}', which is not a known "
                    f"topic slug (known: {known})"
                )
            if related.id == topic.id:
                raise ContentError(f"{context} lists itself as a related topic")
            self.db.session.add(
                TopicLink(topic_id=topic.id, related_topic_id=related.id, note=note or None)
            )


def rebuild_database(app, db):
    """Drop and rebuild the whole database from content/.

    Idempotent: drop_all + create_all means running it twice in a row produces
    exactly the same result as running it once.
    """
    with app.app_context():
        db.drop_all()
        db.create_all()

        loader = _Loader(db)

        for course_dir in sorted(CONTENT_DIR.glob("*")):
            if not course_dir.is_dir() or not (course_dir / "course.yaml").exists():
                continue
            loader.load_domains(course_dir / "domains.yaml")
            loader.load_phases(course_dir / "phases.yaml")
            loader.load_course(course_dir)

        loader.resolve_links()
        db.session.commit()
        return loader.stats


def format_stats(stats):
    order = ("courses", "lessons", "topics", "steps", "visuals", "domains", "objectives", "phases")
    return ", ".join(f"{stats[key]} {key}" for key in order if key in stats)
