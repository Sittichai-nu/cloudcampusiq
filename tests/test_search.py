from search import highlight, search_all, total_hits


def slugs(results):
    return [hit.obj.slug for hit in results["topic"]]


def test_short_queries_return_nothing(ctx):
    assert total_hits(search_all("a")) == 0
    assert total_hits(search_all("")) == 0


def test_finds_a_topic_by_title(ctx):
    assert "business-case" in slugs(search_all("business case"))


def test_finds_a_topic_by_body_text_only(ctx):
    # "ROI" appears in the body, not in any title.
    hits = search_all("roi")
    assert "business-case" in slugs(hits)


def test_title_matches_outrank_body_matches(ctx):
    hits = search_all("project")["topic"]
    assert len(hits) > 1
    scores = [hit.score for hit in hits]
    assert scores == sorted(scores, reverse=True)


def test_finds_a_topic_by_objective_code(ctx):
    assert "business-case" in slugs(search_all("2.1"))


def test_finds_a_phase(ctx):
    names = [hit.obj.name for hit in search_all("planning")["phase"]]
    assert "Planning" in names


def test_finds_a_course_by_code(ctx):
    codes = [hit.obj.code for hit in search_all("pm101")["course"]]
    assert "PM101" in codes


def test_body_snippet_contains_the_match(ctx):
    hit = next(h for h in search_all("roi")["topic"] if h.obj.slug == "business-case")
    assert "roi" in hit.snippet.lower()


def test_nonsense_query_finds_nothing(ctx):
    assert total_hits(search_all("zzzzqqqq")) == 0


def test_highlight_wraps_matches():
    assert "<mark>cat</mark>" in str(highlight("a cat sat", "cat"))


def test_highlight_is_case_insensitive():
    assert "<mark>Cat</mark>" in str(highlight("a Cat sat", "cat"))


def test_highlight_escapes_html():
    result = str(highlight("<b>bold</b>", "bold"))
    assert "<b>" not in result
    assert "&lt;b&gt;" in result
    assert "<mark>bold</mark>" in result


def test_highlight_does_not_mark_short_queries():
    assert "<mark>" not in str(highlight("a cat sat", "a"))
