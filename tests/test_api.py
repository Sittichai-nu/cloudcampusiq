def test_list_courses(client):
    data = client.get("/api/v1/courses").get_json()
    codes = [course["code"] for course in data]
    assert "PM101" in codes
    assert all("lesson_count" in course for course in data)


def test_get_course_includes_lessons(client):
    data = client.get("/api/v1/courses/pm101").get_json()
    assert data["code"] == "PM101"
    assert data["lessons"][0]["number"] == 1


def test_get_lesson_includes_topics(client):
    data = client.get("/api/v1/courses/pm101/lessons/1").get_json()
    slugs = [topic["slug"] for topic in data["topics"]]
    assert "business-case" in slugs


def test_get_topic_returns_the_full_graph(client):
    data = client.get("/api/v1/topics/business-case").get_json()
    assert data["slug"] == "business-case"
    assert data["phase"] == "discovery"
    assert data["kind"] == "document"
    assert "2.1" in data["objectives"]
    assert "2.0" in data["domains"]
    assert data["steps"]
    assert [v["kind"] for v in data["visuals"]] == ["table", "table", "table"]
    assert data["related"]


def test_list_topics_supports_filters(client):
    everything = client.get("/api/v1/topics").get_json()
    filtered = client.get("/api/v1/topics?phase=discovery").get_json()
    assert len(filtered) < len(everything)
    assert all(topic["phase"] == "discovery" for topic in filtered)


def test_list_topics_filter_by_kind(client):
    data = client.get("/api/v1/topics?kind=concept").get_json()
    assert data
    assert all(topic["kind"] == "concept" for topic in data)


def test_list_domains(client):
    data = client.get("/api/v1/domains").get_json()
    assert any(domain["code"] == "2.0" for domain in data)


def test_get_domain_lists_its_topics(client):
    data = client.get("/api/v1/domains/2.0").get_json()
    assert data["code"] == "2.0"
    assert any(topic["slug"] == "business-case" for topic in data["topics"])


def test_list_phases_in_order(client):
    data = client.get("/api/v1/phases").get_json()
    assert [phase["slug"] for phase in data][:2] == ["discovery", "initiation"]


def test_get_phase_lists_its_topics(client):
    data = client.get("/api/v1/phases/discovery").get_json()
    assert any(topic["slug"] == "business-case" for topic in data["topics"])


def test_search_endpoint(client):
    data = client.get("/api/v1/search?q=business+case").get_json()
    assert data["total"] > 0
    assert any(hit["slug"] == "business-case" for hit in data["results"]["topic"])


def test_search_endpoint_with_no_query(client):
    data = client.get("/api/v1/search").get_json()
    assert data["total"] == 0


def test_missing_resource_returns_json_not_html(client):
    response = client.get("/api/v1/courses/nope")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "not found"


def test_unmatched_api_url_returns_json_not_html(client):
    # An unrouted /api/ URL used to fall through to the HTML error page.
    response = client.get("/api/v1/not-a-real-endpoint")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "not found"


def test_html_404_is_still_html(client):
    response = client.get("/definitely-not-a-page")
    assert response.status_code == 404
    assert not response.is_json
