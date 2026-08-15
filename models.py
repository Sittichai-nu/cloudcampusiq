import json

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# A topic's kind drives how it is labelled and filtered in the UI. The loader
# rejects anything outside this set so a typo in YAML fails the build instead
# of quietly producing an unfilterable topic.
TOPIC_KINDS = ("concept", "tool", "document", "process", "formula")


topic_objectives = db.Table(
    "topic_objectives",
    db.Column("topic_id", db.Integer, db.ForeignKey("topic.id"), primary_key=True),
    db.Column("objective_id", db.Integer, db.ForeignKey("objective.id"), primary_key=True),
)


def objective_sort_key(code):
    """Turn an objective code into an int that sorts the way humans expect.

    Plain string ordering puts "1.10" before "1.9" because it compares "1"
    against "9" character by character. Packing major/minor into one integer
    (1.10 -> 1010, 1.9 -> 1009) fixes that and lets the DB do the ordering.
    """
    major, _, minor = code.partition(".")
    return int(major) * 1000 + int(minor or 0)


def domain_code_for(objective_code):
    """Objective "2.1" belongs to domain "2.0" -- the prefix is the link."""
    major, _, _ = objective_code.partition(".")
    return f"{int(major)}.0"


class Domain(db.Model):
    """A top-level exam domain, e.g. "2.0"."""

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False, default="")
    summary = db.Column(db.Text, nullable=False, default="")
    order = db.Column(db.Integer, nullable=False)

    objectives = db.relationship(
        "Objective",
        backref="domain",
        cascade="all, delete-orphan",
        order_by="Objective.sort_key",
    )

    @property
    def label(self):
        """Domains ship with an empty title until someone fills it in from the
        official objectives list, so fall back to the bare code."""
        return f"{self.code} {self.title}".strip() if self.title else self.code

    def topics(self):
        seen = {}
        for objective in self.objectives:
            for topic in objective.topics:
                seen[topic.id] = topic
        return sorted(seen.values(), key=lambda t: (t.lesson.number, t.order))

    def to_dict(self, include_objectives=False):
        data = {
            "code": self.code,
            "title": self.title,
            "summary": self.summary,
        }
        if include_objectives:
            data["objectives"] = [o.to_dict() for o in self.objectives]
        return data


class Objective(db.Model):
    """A single exam objective, e.g. "2.1", owned by a Domain."""

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    title = db.Column(db.String(300), nullable=False, default="")
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), nullable=False)
    sort_key = db.Column(db.Integer, nullable=False)
    # The sub-points the exam actually asks about under this objective, one per
    # line. This is the exam-facing checklist: a reader can compare it against
    # the topic they just read and see what is still uncovered.
    exam_points = db.Column(db.Text, nullable=False, default="")

    @property
    def label(self):
        return f"{self.code} {self.title}".strip() if self.title else self.code

    def point_list(self):
        return [line.strip() for line in (self.exam_points or "").split("\n") if line.strip()]

    def to_dict(self):
        return {
            "code": self.code,
            "title": self.title,
            "domain": self.domain.code,
            "exam_points": self.point_list(),
        }


class Phase(db.Model):
    """A project life cycle phase. Topics point at the phase they happen in,
    which is what lets a reader ask "when in a project does this apply?"."""

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    summary = db.Column(db.Text, nullable=False, default="")

    topics = db.relationship("Topic", backref="phase", order_by="Topic.order")

    def to_dict(self):
        return {
            "slug": self.slug,
            "name": self.name,
            "order": self.order,
            "summary": self.summary,
        }


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    lessons = db.relationship(
        "Lesson",
        backref="course",
        cascade="all, delete-orphan",
        order_by="Lesson.number",
    )

    def topic_count(self):
        return sum(len(lesson.topics) for lesson in self.lessons)

    def to_dict(self, include_lessons=False):
        data = {
            "code": self.code,
            "title": self.title,
            "description": self.description,
            "lesson_count": len(self.lessons),
            "topic_count": self.topic_count(),
        }
        if include_lessons:
            data["lessons"] = [lesson.to_dict() for lesson in self.lessons]
        return data


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    verified = db.Column(db.Boolean, nullable=False)
    source = db.Column(db.String(300), nullable=False)

    topics = db.relationship(
        "Topic",
        backref="lesson",
        cascade="all, delete-orphan",
        order_by="Topic.order",
    )

    __table_args__ = (db.UniqueConstraint("course_id", "number"),)

    def to_dict(self, include_topics=False):
        data = {
            "number": self.number,
            "title": self.title,
            "verified": self.verified,
            "source": self.source,
            "topic_count": len(self.topics),
        }
        if include_topics:
            data["topics"] = [topic.to_dict() for topic in self.topics]
        return data


class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lesson.id"), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    order = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.Text, nullable=False, default="")
    kind = db.Column(db.String(20), nullable=False, default="concept")
    body = db.Column(db.Text, nullable=False)
    phase_id = db.Column(db.Integer, db.ForeignKey("phase.id"), nullable=True)
    verified = db.Column(db.Boolean, nullable=False)
    source = db.Column(db.String(300), nullable=False)

    objectives = db.relationship(
        "Objective",
        secondary=topic_objectives,
        backref="topics",
        order_by="Objective.sort_key",
    )
    steps = db.relationship(
        "TopicStep",
        backref="topic",
        cascade="all, delete-orphan",
        order_by="TopicStep.order",
    )
    visuals = db.relationship(
        "Visual",
        backref="topic",
        cascade="all, delete-orphan",
        order_by="Visual.order",
    )
    links = db.relationship(
        "TopicLink",
        foreign_keys="TopicLink.topic_id",
        back_populates="topic",
        cascade="all, delete-orphan",
    )

    def tag_list(self):
        return [objective.code for objective in self.objectives]

    def domains(self):
        seen = {}
        for objective in self.objectives:
            seen[objective.domain.code] = objective.domain
        return sorted(seen.values(), key=lambda d: d.order)

    def related_topics(self):
        """Explicitly linked topics first, then topics that share an objective.

        The second half is what makes the graph useful without hand-authoring
        every edge: tagging two topics "2.1" is already a statement that they
        belong together, so the app treats it as one.
        """
        related = []
        seen = {self.id}

        for link in self.links:
            if link.related_topic_id in seen:
                continue
            seen.add(link.related_topic_id)
            related.append((link.related, link.note or "Related topic"))

        for objective in self.objectives:
            for topic in objective.topics:
                if topic.id in seen:
                    continue
                seen.add(topic.id)
                related.append((topic, f"Also covers objective {objective.code}"))

        return related

    def to_dict(self, include_body=True):
        data = {
            "slug": self.slug,
            "order": self.order,
            "title": self.title,
            "summary": self.summary,
            "kind": self.kind,
            "objectives": self.tag_list(),
            "domains": [domain.code for domain in self.domains()],
            "phase": self.phase.slug if self.phase else None,
            "verified": self.verified,
            "source": self.source,
        }
        if include_body:
            data["body"] = self.body
            data["steps"] = [step.to_dict() for step in self.steps]
            data["visuals"] = [visual.to_dict() for visual in self.visuals]
            data["related"] = [
                {"slug": topic.slug, "title": topic.title, "reason": reason}
                for topic, reason in self.related_topics()
            ]
        return data


class TopicStep(db.Model):
    """One ordered step of a procedure -- how a document gets built, how a
    tool gets used. Kept separate from body so the UI can number them."""

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False, default="")

    def to_dict(self):
        return {"order": self.order, "title": self.title, "body": self.body}


class TopicLink(db.Model):
    """A hand-authored edge between two topics, with a reason."""

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)
    related_topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)
    note = db.Column(db.String(200), nullable=True)

    topic = db.relationship("Topic", foreign_keys=[topic_id], back_populates="links")
    related = db.relationship("Topic", foreign_keys=[related_topic_id])


class Visual(db.Model):
    """A diagram attached to a topic. `spec` is the renderer's input data as
    JSON; the renderer itself is chosen by `kind` (see visuals.py).

    A topic may carry several: a dense topic usually has more than one thing
    worth comparing, and splitting those into separate tables reads far better
    than one long prose list.
    """

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)
    order = db.Column(db.Integer, nullable=False, default=1)
    kind = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False, default="")
    caption = db.Column(db.Text, nullable=False, default="")
    spec = db.Column(db.Text, nullable=False)

    def data(self):
        return json.loads(self.spec)

    def to_dict(self):
        return {
            "kind": self.kind,
            "title": self.title,
            "caption": self.caption,
            "data": self.data(),
        }
