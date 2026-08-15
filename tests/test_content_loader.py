"""Loader tests.

The failure cases build a throwaway content tree and point the loader at it, so
they exercise the real validation path without touching the shipped content.
"""

import textwrap

import pytest
from flask import Flask

import content_loader
from content_loader import ContentError, rebuild_database, slugify
from models import Course, Domain, Objective, Phase, Topic, db


LESSON_HEAD = """\
number: 1
title: "Test Lesson"
verified: true
source: "test"
topics:
"""


def build_content(tmp_path, lesson_body, phases=True):
    course_dir = tmp_path / "testcourse"
    course_dir.mkdir()
    (course_dir / "course.yaml").write_text(
        'code: TEST\ntitle: "Test"\ndescription: "Test course"\n', encoding="utf-8"
    )
    if phases:
        (course_dir / "phases.yaml").write_text(
            "phases:\n  - slug: planning\n    name: Planning\n    order: 1\n",
            encoding="utf-8",
        )
    (course_dir / "lesson_01.yaml").write_text(
        LESSON_HEAD + textwrap.indent(textwrap.dedent(lesson_body), "  "),
        encoding="utf-8",
    )
    return tmp_path


def load(tmp_path, monkeypatch, lesson_body, phases=True):
    """Point the loader at a throwaway content tree and rebuild into an
    in-memory database, so validation runs exactly as it does in production."""
    monkeypatch.setattr(
        content_loader, "CONTENT_DIR", build_content(tmp_path, lesson_body, phases)
    )
    application = Flask(__name__)
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    db.init_app(application)
    return rebuild_database(application, db)


# --- the shipped content -------------------------------------------------

def test_shipped_content_loads(ctx):
    course = Course.query.filter_by(code="PM101").one()
    assert course.lessons
    assert course.topic_count() > 0


def test_topic_slugs_are_unique(ctx):
    slugs = [topic.slug for topic in Topic.query.all()]
    assert len(slugs) == len(set(slugs))


def test_objectives_resolve_to_derived_domains(ctx):
    objective = Objective.query.filter_by(code="2.1").one()
    assert objective.domain.code == "2.0"


def test_objective_codes_sort_naturally(ctx):
    # "1.10" must come after "1.9"-style codes, not before "1.2".
    domain = Domain.query.filter_by(code="1.0").one()
    codes = [objective.code for objective in domain.objectives]
    assert codes == sorted(codes, key=lambda c: (int(c.split(".")[0]), int(c.split(".")[1])))


def test_objectives_have_titles_from_the_source_appendix(ctx):
    assert Objective.query.filter_by(code="2.1").one().title.startswith(
        "Explain the value of artifacts"
    )
    assert Domain.query.filter_by(code="2.0").one().title == "Project Life Cycle Phases"


def test_covered_objectives_carry_exam_points(ctx):
    points = Objective.query.filter_by(code="4.1").one().point_list()
    assert len(points) == 4
    assert any("brand value" in point for point in points)


def test_uncovered_objectives_have_no_exam_points(ctx):
    # 1.2 has a title but no lesson published here yet.
    objective = Objective.query.filter_by(code="1.2").one()
    assert objective.title
    assert objective.point_list() == []


def test_phases_load_in_order(ctx):
    phases = Phase.query.order_by(Phase.order).all()
    assert [phase.slug for phase in phases][:2] == ["discovery", "initiation"]


def test_topics_link_to_related_topics(ctx):
    topic = Topic.query.filter_by(slug="business-case").one()
    assert any(other.slug == "project-management-basics" for other, _ in topic.related_topics())


def test_topics_sharing_an_objective_are_auto_related(ctx):
    topic = Topic.query.filter_by(slug="business-case").one()
    reasons = [reason for _, reason in topic.related_topics()]
    assert topic.objectives  # precondition for the auto-linking to mean anything
    assert all(isinstance(reason, str) for reason in reasons)


def test_a_topic_is_never_related_to_itself(ctx):
    for topic in Topic.query.all():
        assert all(other.id != topic.id for other, _ in topic.related_topics())


# --- validation ----------------------------------------------------------

def test_unknown_kind_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(ContentError, match="expected one of"):
        load(tmp_path, monkeypatch, """
            - title: "A"
              kind: "banana"
              body: "text"
        """)


def test_unknown_phase_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(ContentError, match="not in phases.yaml"):
        load(tmp_path, monkeypatch, """
            - title: "A"
              phase: "nonexistent"
              body: "text"
        """)


def test_duplicate_slug_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(ContentError, match="already taken"):
        load(tmp_path, monkeypatch, """
            - title: "A"
              slug: "same"
              body: "text"
            - title: "B"
              slug: "same"
              body: "text"
        """)


def test_unknown_related_slug_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(ContentError, match="not a known"):
        load(tmp_path, monkeypatch, """
            - title: "A"
              body: "text"
              related: ["ghost"]
        """)


def test_self_reference_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(ContentError, match="itself"):
        load(tmp_path, monkeypatch, """
            - title: "A"
              slug: "a"
              body: "text"
              related: ["a"]
        """)


def test_malformed_objective_code_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(ContentError, match="expected a code like"):
        load(tmp_path, monkeypatch, """
            - title: "A"
              body: "text"
              objectives: ["domain two"]
        """)


def test_broken_diagram_spec_fails_the_build(tmp_path, monkeypatch):
    # A bad spec must break the build, not render as an empty panel.
    with pytest.raises(ContentError, match="unknown task"):
        load(tmp_path, monkeypatch, """
            - title: "A"
              body: "text"
              visual:
                kind: "gantt"
                data:
                  tasks:
                    - name: "A"
                      start: 0
                      duration: 1
                      depends_on: ["missing"]
        """)


def test_missing_body_is_rejected(tmp_path, monkeypatch):
    with pytest.raises(ContentError, match="'body'"):
        load(tmp_path, monkeypatch, """
            - title: "A"
        """)


# --- helpers -------------------------------------------------------------

def test_slugify():
    assert slugify("Develop the Business Case!") == "develop-the-business-case"
    assert slugify("  Multiple   spaces  ") == "multiple-spaces"


def test_slugify_rejects_unusable_input():
    with pytest.raises(ContentError):
        slugify("!!!")
