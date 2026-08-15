import pytest

from visuals import EXAMPLES, RENDERERS, VisualError, render


def test_every_example_renders():
    # /diagrams renders EXAMPLES directly, so a broken example is a broken page.
    for example in EXAMPLES:
        markup = render(example["kind"], example["data"], example["title"])
        assert markup.strip()


def test_every_renderer_has_an_example():
    documented = {example["kind"] for example in EXAMPLES}
    assert documented == set(RENDERERS)


def test_unknown_kind_raises():
    with pytest.raises(VisualError, match="unknown visual kind"):
        render("piechart", {})


# --- gantt ---------------------------------------------------------------

def test_gantt_draws_a_bar_per_task():
    markup = render("gantt", {"tasks": [
        {"name": "A", "start": 0, "duration": 2},
        {"name": "B", "start": 2, "duration": 3},
    ]})
    assert markup.count("<rect") == 2
    assert "<svg" in markup


def test_gantt_zero_duration_renders_a_milestone_diamond():
    markup = render("gantt", {"tasks": [
        {"name": "Kickoff", "start": 0, "duration": 0},
    ]})
    assert "<polygon" in markup
    assert "milestone" in markup
    assert "<rect" not in markup


def test_gantt_draws_dependency_arrows():
    markup = render("gantt", {"tasks": [
        {"name": "A", "start": 0, "duration": 2},
        {"name": "B", "start": 2, "duration": 2, "depends_on": ["A"]},
    ]})
    assert "<polyline" in markup
    assert "marker-end" in markup


def test_gantt_rejects_a_dependency_on_an_unknown_task():
    with pytest.raises(VisualError, match="unknown task"):
        render("gantt", {"tasks": [
            {"name": "A", "start": 0, "duration": 1, "depends_on": ["Nope"]},
        ]})


def test_gantt_rejects_missing_fields():
    with pytest.raises(VisualError, match="'duration'"):
        render("gantt", {"tasks": [{"name": "A", "start": 0}]})


def test_gantt_rejects_negative_duration():
    with pytest.raises(VisualError, match="negative"):
        render("gantt", {"tasks": [{"name": "A", "start": 0, "duration": -2}]})


def test_gantt_rejects_empty_tasks():
    with pytest.raises(VisualError, match="non-empty"):
        render("gantt", {"tasks": []})


def test_gantt_escapes_task_names():
    markup = render("gantt", {"tasks": [
        {"name": "<script>", "start": 0, "duration": 1},
    ]})
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup


# --- flow ----------------------------------------------------------------

def test_flow_draws_a_box_per_node():
    markup = render("flow", {"nodes": [
        {"label": "One"}, {"label": "Two"}, {"label": "Three"},
    ]})
    # One rect per node, plus a numbered circle each.
    assert markup.count("<rect") == 3
    assert markup.count("<circle") == 3


def test_flow_draws_arrows_between_nodes_only():
    markup = render("flow", {"nodes": [{"label": "A"}, {"label": "B"}]})
    assert markup.count("<line") == 1


def test_flow_accepts_bare_strings_as_nodes():
    markup = render("flow", {"nodes": ["A", "B"]})
    assert markup.count("<rect") == 2


def test_flow_rejects_empty_nodes():
    with pytest.raises(VisualError, match="non-empty"):
        render("flow", {"nodes": []})


# --- table ---------------------------------------------------------------

def test_table_renders_headers_and_rows():
    markup = render("table", {
        "headers": ["A", "B"],
        "rows": [["1", "2"], ["3", "4"]],
    })
    assert markup.count('<th scope="col">') == 2
    assert markup.count("<tr>") == 3  # header row + 2 body rows
    assert markup.count("<td>") == 4


def test_table_rejects_a_row_with_the_wrong_cell_count():
    with pytest.raises(VisualError, match="but there are 2 headers"):
        render("table", {"headers": ["A", "B"], "rows": [["1"]]})


def test_table_escapes_cell_content():
    markup = render("table", {"headers": ["H"], "rows": [["<b>bold</b>"]]})
    assert "<b>" not in markup
    assert "&lt;b&gt;" in markup
