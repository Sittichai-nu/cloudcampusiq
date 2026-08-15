from formatting import format_body, plain_text


def render(text):
    return str(format_body(text))


def test_blank_lines_become_separate_paragraphs():
    html = render("First paragraph.\n\nSecond paragraph.")
    assert html.count("<p>") == 2
    assert "First paragraph." in html
    assert "Second paragraph." in html


def test_wrapped_lines_rejoin_into_one_sentence():
    # YAML block scalars hard-wrap mid-sentence; the newline must not survive.
    html = render("A sentence that was\nwrapped by the editor.")
    assert "<p>A sentence that was wrapped by the editor.</p>" == html


def test_bullets_become_a_list():
    html = render("- one\n- two\n- three")
    assert html.count("<li>") == 3
    assert "<ul" in html


def test_bullet_continuation_folds_into_the_item_above():
    html = render("- a template is a reusable form for\n  something every project needs")
    assert html.count("<li>") == 1
    assert "reusable form for something every project needs" in html


def test_numbered_list_keeps_its_start_number():
    html = render("1. first\n2. second")
    assert '<ol class="topic-list" start="1">' in html
    assert html.count("<li>") == 2


def test_lead_in_line_becomes_a_subheading():
    html = render("The 5 phases:\n- Discovery\n- Initiation")
    assert '<h4 class="topic-subhead">The 5 phases</h4>' in html
    assert html.count("<li>") == 2


def test_remember_paragraph_becomes_a_callout():
    html = render("Remember: know the ROI formula.")
    assert 'class="topic-callout"' in html
    assert "Key exam point" in html
    assert "know the ROI formula." in html
    assert "Remember:" not in html


def test_double_dash_becomes_an_em_dash():
    assert "—" in render("Discovery -- the first phase.")


def test_html_in_content_is_escaped():
    html = render('<script>alert("x")</script>')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_empty_body_renders_nothing():
    assert render("") == ""


def test_plain_text_collapses_whitespace():
    assert plain_text("a\n\n  b   c\n") == "a b c"
