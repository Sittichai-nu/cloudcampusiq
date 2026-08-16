import pytest

PAGES = [
    "/",
    "/courses",
    "/courses/pm101",
    "/courses/PM101",
    "/courses/pm101/lesson/1",
    "/topics",
    "/topics/business-case",
    "/domains",
    "/domains/2.0",
    "/phases",
    "/phases/discovery",
    "/search?q=business",
    "/search",
    "/diagrams",
    "/login",
]


@pytest.mark.parametrize("path", PAGES)
def test_page_renders(client, path):
    response = client.get(path)
    assert response.status_code == 200


def test_topic_page_shows_where_it_fits(client):
    body = client.get("/topics/business-case").get_data(as_text=True)
    assert "Where this fits" in body
    assert "Discovery" in body       # its phase
    assert "Obj 2.1" in body         # its objective
    assert "Lesson 1" in body


def test_topic_page_shows_the_exam_objective_checklist(client):
    body = client.get("/topics/business-case").get_data(as_text=True)
    assert "What the exam asks here" in body
    assert "Explain the value of artifacts" in body      # objective 2.1 title
    assert "Return on investment analysis" in body       # one of its exam points


def test_exam_claims_are_sourced_to_the_objectives_appendix(client):
    body = client.get("/topics/business-case").get_data(as_text=True)
    assert "Exam scope" in body
    assert "The appendix maps this topic to two objectives" in body


def test_a_topic_with_no_objective_says_so_rather_than_inventing_one(client):
    # Topic 1A is mapped to no objective in the appendix. Saying that plainly
    # beats manufacturing an exam claim for it.
    body = client.get("/topics/project-management-basics").get_data(as_text=True)
    assert "maps no exam objective to this topic" in body


def test_body_callouts_do_not_claim_exam_authority(client):
    # The "Remember:" lines are the author's mnemonics, not sourced exam facts.
    for slug in ("project-management-basics", "business-case", "project-characteristics"):
        body = client.get(f"/topics/{slug}").get_data(as_text=True)
        assert "topic-callout-label\">Recall<" in body
        assert "Key exam point" not in body


def test_topic_page_renders_every_diagram_it_declares(client):
    body = client.get("/topics/project-characteristics").get_data(as_text=True)
    assert body.count('class="visual-panel"') == 4


def test_domain_page_names_the_domain_and_its_objectives(client):
    body = client.get("/domains/1.0").get_data(as_text=True)
    assert "Project Management Concepts" in body
    assert "Obj 1.10" in body
    assert "Organizational structures" in body


def test_topic_body_is_structured_not_one_blob(client):
    body = client.get("/topics/business-case").get_data(as_text=True)
    assert "<ul class=\"topic-list\"" in body
    assert "topic-subhead" in body
    assert "topic-callout" in body


def test_topic_page_renders_its_diagram_inline(client):
    body = client.get("/topics/business-case").get_data(as_text=True)
    assert "visual-panel" in body
    assert "visual-table" in body
    # Markup must be rendered, not escaped into visible tags.
    assert "&lt;table" not in body


def test_gantt_renders_as_svg_on_the_catalog(client):
    body = client.get("/diagrams").get_data(as_text=True)
    assert "<svg" in body
    assert "&lt;svg" not in body


def test_catalog_is_labelled_as_sample_data(client):
    body = client.get("/diagrams").get_data(as_text=True)
    assert "not course material" in body


def test_course_catalog_is_database_driven(client):
    body = client.get("/courses").get_data(as_text=True)
    assert "Business of IT" in body
    assert "/courses/PM101" in body


def test_topic_filters_narrow_the_index(client):
    everything = client.get("/topics").get_data(as_text=True)
    filtered = client.get("/topics?phase=discovery").get_data(as_text=True)
    assert everything.count("topic-tile\"") > filtered.count("topic-tile\"")
    assert "business-case" in filtered


def test_filters_combine(client):
    body = client.get("/topics?phase=discovery&kind=document").get_data(as_text=True)
    assert "business-case" in body


def test_filter_with_no_matches_says_so(client):
    body = client.get("/topics?kind=formula").get_data(as_text=True)
    assert "No topics match those filters." in body


def test_search_reports_no_results(client):
    body = client.get("/search?q=zzzzqqqq").get_data(as_text=True)
    assert "Nothing matched" in body


def test_search_highlights_the_match(client):
    body = client.get("/search?q=business").get_data(as_text=True)
    assert "<mark>" in body


def test_unknown_page_returns_the_html_404(client):
    response = client.get("/topics/does-not-exist")
    assert response.status_code == 404
    assert "That page does not exist" in response.get_data(as_text=True)


def test_unknown_course_404s(client):
    assert client.get("/courses/nope").status_code == 404


def test_unknown_lesson_404s(client):
    assert client.get("/courses/pm101/lesson/99").status_code == 404


def test_retired_course_code_is_absent_from_every_page(client):
    # Assembled at runtime so this guard does not itself trip the repo-wide
    # banned-string scan in dev.ps1 / dev.sh.
    retired = "D" + "324"
    for path in PAGES:
        assert retired not in client.get(path).get_data(as_text=True)
