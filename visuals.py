"""Server-rendered diagrams.

Every renderer is a pure function: spec dict in, markup string out. No Flask
imports, no database, no global state -- which is what makes them testable in
isolation and safe to call at content-load time to validate a spec.

Output is inline SVG (or a plain table) that references the site's existing CSS
custom properties, so a diagram picks up the site palette without a stylesheet
of its own and needs no JavaScript to appear.

Adding a renderer: write the function, add it to RENDERERS. That's the whole
extension point.
"""

from html import escape

# Canvas geometry. The viewBox scales to the container, so these are relative
# proportions rather than pixel promises.
CANVAS_WIDTH = 940
LABEL_WIDTH = 210
RIGHT_PAD = 24
ROW_HEIGHT = 38
BAR_HEIGHT = 22
AXIS_HEIGHT = 40
CHAR_WIDTH = 6.6  # approximate advance width at font-size 12


class VisualError(ValueError):
    """Raised when a spec is malformed. Surfaced at content-load time."""


def _require(data, key, context):
    if not isinstance(data, dict) or key not in data:
        raise VisualError(f"{context} is missing required key '{key}'")
    return data[key]


def _number(value, context):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VisualError(f"{context} must be a number, got {value!r}")
    return float(value)


def _wrap(text, max_chars):
    """Greedy word wrap. SVG has no automatic text flow, so lines are computed
    here and emitted as <tspan> elements."""
    words = str(text).split()
    if not words:
        return [""]

    lines = [words[0]]
    for word in words[1:]:
        if len(lines[-1]) + 1 + len(word) <= max_chars:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines


def _tspans(lines, x, first_y, line_height):
    return "".join(
        f'<tspan x="{_n(x)}" y="{_n(first_y + i * line_height)}">{escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )


def _n(value):
    """Trim float noise out of coordinate attributes."""
    rounded = round(float(value), 2)
    return int(rounded) if rounded == int(rounded) else rounded


def _svg_open(width, height, title):
    return (
        f'<svg class="visual-svg" viewBox="0 0 {_n(width)} {_n(height)}" '
        f'width="100%" height="{_n(height)}" role="img" '
        f'aria-label="{escape(title or "Diagram")}" '
        'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMinYMin meet">'
    )


# --------------------------------------------------------------------------
# Gantt
# --------------------------------------------------------------------------

def render_gantt(data, title=""):
    """Horizontal bars on a shared time axis.

    spec.data:
        unit:  label for the x axis ("week", "day", "sprint"). Default "unit".
        tasks: list of {name, start, duration, depends_on?}
               duration 0 renders as a milestone diamond.
    """
    tasks = _require(data, "tasks", "gantt spec")
    if not isinstance(tasks, list) or not tasks:
        raise VisualError("gantt spec 'tasks' must be a non-empty list")

    unit = str(data.get("unit", "unit"))

    parsed = []
    for index, task in enumerate(tasks):
        context = f"gantt task #{index + 1}"
        name = str(_require(task, "name", context))
        start = _number(_require(task, "start", context), f"{context} 'start'")
        duration = _number(_require(task, "duration", context), f"{context} 'duration'")
        if start < 0 or duration < 0:
            raise VisualError(f"{context} cannot have a negative start or duration")
        parsed.append(
            {
                "name": name,
                "start": start,
                "duration": duration,
                "depends_on": task.get("depends_on") or [],
            }
        )

    by_name = {task["name"]: i for i, task in enumerate(parsed)}
    for task in parsed:
        for dependency in task["depends_on"]:
            if dependency not in by_name:
                raise VisualError(
                    f"gantt task '{task['name']}' depends on unknown task '{dependency}'"
                )

    total = max(task["start"] + task["duration"] for task in parsed) or 1
    chart_width = CANVAS_WIDTH - LABEL_WIDTH - RIGHT_PAD
    height = AXIS_HEIGHT + len(parsed) * ROW_HEIGHT + 18

    def x_of(units):
        return LABEL_WIDTH + (units / total) * chart_width

    def row_y(index):
        return AXIS_HEIGHT + index * ROW_HEIGHT

    parts = [_svg_open(CANVAS_WIDTH, height, title or "Gantt chart")]
    parts.append(
        '<defs><marker id="gantt-arrow" viewBox="0 0 8 8" refX="7" refY="4" '
        'markerWidth="6" markerHeight="6" orient="auto">'
        '<path d="M0,0 L8,4 L0,8 z" fill="var(--muted, #5f6b7a)"/></marker></defs>'
    )

    # Axis: aim for at most ~10 gridlines whatever the timeline length.
    step = max(1, -(-int(total) // 10))
    tick = 0
    while tick <= total:
        x = x_of(tick)
        parts.append(
            f'<line x1="{_n(x)}" y1="{AXIS_HEIGHT - 12}" x2="{_n(x)}" y2="{_n(height - 12)}" '
            'stroke="var(--border, #d9e3f0)" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{_n(x)}" y="{AXIS_HEIGHT - 20}" font-size="11" '
            'fill="var(--muted, #5f6b7a)" text-anchor="middle">'
            f"{escape(str(tick))}</text>"
        )
        tick += step

    # Sits in the label column, clear of the first gridline's tick number.
    axis_label = unit if unit.endswith("s") else f"{unit}s"
    parts.append(
        f'<text x="8" y="{AXIS_HEIGHT - 20}" font-size="11" font-weight="bold" '
        'fill="var(--muted, #5f6b7a)">'
        f"{escape(axis_label.upper())}</text>"
    )

    # Dependency connectors are drawn first so bars sit on top of them.
    for index, task in enumerate(parsed):
        for dependency in task["depends_on"]:
            source = parsed[by_name[dependency]]
            source_index = by_name[dependency]
            x1 = x_of(source["start"] + source["duration"])
            y1 = row_y(source_index) + BAR_HEIGHT / 2
            x2 = x_of(task["start"])
            y2 = row_y(index) + BAR_HEIGHT / 2
            mid = max(x1 + 8, x2 - 8)
            parts.append(
                f'<polyline points="{_n(x1)},{_n(y1)} {_n(mid)},{_n(y1)} '
                f'{_n(mid)},{_n(y2)} {_n(x2)},{_n(y2)}" fill="none" '
                'stroke="var(--muted, #5f6b7a)" stroke-width="1" '
                'stroke-dasharray="3 3" marker-end="url(#gantt-arrow)"/>'
            )

    label_chars = int((LABEL_WIDTH - 16) / CHAR_WIDTH)
    for index, task in enumerate(parsed):
        y = row_y(index)
        lines = _wrap(task["name"], label_chars)[:2]
        first_y = y + BAR_HEIGHT / 2 + 4 - (len(lines) - 1) * 6
        parts.append(
            '<text font-size="12" fill="var(--text, #1f2937)">'
            f"{_tspans(lines, 8, first_y, 13)}</text>"
        )

        start_x = x_of(task["start"])
        size = 9  # milestone diamond half-width
        if task["duration"] == 0:
            # Milestone: a zero-length bar would be invisible, so mark it.
            centre_y = y + BAR_HEIGHT / 2
            parts.append(
                f'<polygon points="{_n(start_x)},{_n(centre_y - size)} '
                f'{_n(start_x + size)},{_n(centre_y)} {_n(start_x)},{_n(centre_y + size)} '
                f'{_n(start_x - size)},{_n(centre_y)}" fill="var(--primary-dark, #005ea6)"/>'
            )
            text_x = start_x + size + 6
        else:
            width = max(3.0, x_of(task["start"] + task["duration"]) - start_x)
            parts.append(
                f'<rect x="{_n(start_x)}" y="{_n(y)}" width="{_n(width)}" '
                f'height="{BAR_HEIGHT}" rx="6" fill="var(--primary, #0078d4)" '
                'fill-opacity="0.85"/>'
            )
            text_x = start_x + width + 6

        amount = task["duration"]
        readable = int(amount) if amount == int(amount) else amount
        caption = f"{readable} {unit}{'s' if readable != 1 else ''}" if amount else "milestone"

        # A caption on a task that runs to the end of the timeline would be
        # clipped by the viewBox, so flip it to the left of the marker instead.
        overflows = text_x + len(caption) * CHAR_WIDTH > CANVAS_WIDTH - 4
        if overflows:
            anchor, caption_x = "end", start_x - (size + 6 if amount == 0 else 6)
        else:
            anchor, caption_x = "start", text_x

        parts.append(
            f'<text x="{_n(caption_x)}" y="{_n(y + BAR_HEIGHT / 2 + 4)}" font-size="11" '
            f'text-anchor="{anchor}" fill="var(--muted, #5f6b7a)">{escape(caption)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Flow
# --------------------------------------------------------------------------

def render_flow(data, title=""):
    """A left-to-right chain of labelled boxes joined by arrows.

    spec.data:
        nodes: list of {label, note?}
    """
    nodes = _require(data, "nodes", "flow spec")
    if not isinstance(nodes, list) or not nodes:
        raise VisualError("flow spec 'nodes' must be a non-empty list")

    parsed = []
    for index, node in enumerate(nodes):
        context = f"flow node #{index + 1}"
        if isinstance(node, str):
            parsed.append({"label": node, "note": ""})
            continue
        parsed.append(
            {
                "label": str(_require(node, "label", context)),
                "note": str(node.get("note", "")),
            }
        )

    count = len(parsed)
    gap = 26
    box_width = (CANVAS_WIDTH - 2 * 12 - gap * (count - 1)) / count
    box_height = 108
    height = box_height + 30

    label_chars = max(6, int((box_width - 18) / CHAR_WIDTH))

    parts = [_svg_open(CANVAS_WIDTH, height, title or "Process flow")]
    parts.append(
        '<defs><marker id="flow-arrow" viewBox="0 0 8 8" refX="7" refY="4" '
        'markerWidth="7" markerHeight="7" orient="auto">'
        '<path d="M0,0 L8,4 L0,8 z" fill="var(--primary, #0078d4)"/></marker></defs>'
    )

    for index, node in enumerate(parsed):
        x = 12 + index * (box_width + gap)
        parts.append(
            f'<rect x="{_n(x)}" y="14" width="{_n(box_width)}" height="{box_height}" '
            'rx="12" fill="var(--primary-soft, #eaf4ff)" '
            'stroke="var(--primary, #0078d4)" stroke-width="1.5"/>'
        )
        parts.append(
            f'<circle cx="{_n(x + 18)}" cy="36" r="11" fill="var(--primary, #0078d4)"/>'
            f'<text x="{_n(x + 18)}" y="40" font-size="11" font-weight="bold" '
            f'fill="#ffffff" text-anchor="middle">{index + 1}</text>'
        )

        label_lines = _wrap(node["label"], label_chars)[:2]
        parts.append(
            '<text font-size="13" font-weight="bold" fill="var(--text, #1f2937)">'
            f"{_tspans(label_lines, x + 12, 68, 15)}</text>"
        )

        if node["note"]:
            note_lines = _wrap(node["note"], label_chars)[: 2 if len(label_lines) == 1 else 1]
            note_y = 68 + len(label_lines) * 15 + 2
            parts.append(
                '<text font-size="11" fill="var(--muted, #5f6b7a)">'
                f"{_tspans(note_lines, x + 12, note_y, 13)}</text>"
            )

        if index < count - 1:
            arrow_x = x + box_width
            parts.append(
                f'<line x1="{_n(arrow_x + 5)}" y1="{_n(14 + box_height / 2)}" '
                f'x2="{_n(arrow_x + gap - 7)}" y2="{_n(14 + box_height / 2)}" '
                'stroke="var(--primary, #0078d4)" stroke-width="2" '
                'marker-end="url(#flow-arrow)"/>'
            )

    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Table
# --------------------------------------------------------------------------

def render_table(data, title=""):
    """A comparison table. Plain HTML -- SVG would only make it worse.

    spec.data:
        headers: list of column labels
        rows:    list of row lists
    """
    headers = _require(data, "headers", "table spec")
    rows = _require(data, "rows", "table spec")

    if not isinstance(headers, list) or not headers:
        raise VisualError("table spec 'headers' must be a non-empty list")
    if not isinstance(rows, list) or not rows:
        raise VisualError("table spec 'rows' must be a non-empty list")

    for index, row in enumerate(rows):
        if not isinstance(row, list):
            raise VisualError(f"table row #{index + 1} must be a list")
        if len(row) != len(headers):
            raise VisualError(
                f"table row #{index + 1} has {len(row)} cells "
                f"but there are {len(headers)} headers"
            )

    head = "".join(f"<th scope=\"col\">{escape(str(h))}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f'<table class="visual-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


RENDERERS = {
    "gantt": render_gantt,
    "flow": render_flow,
    "table": render_table,
}


# Sample specs for every renderer, surfaced at /diagrams as living
# documentation for content authors. Deliberately generic -- this is renderer
# documentation, not course material, and no exam content belongs here.
EXAMPLES = [
    {
        "kind": "gantt",
        "blurb": (
            "Bars on a shared time axis. A duration of 0 renders as a milestone "
            "diamond, and depends_on draws dependency arrows between tasks."
        ),
        "title": "Sample schedule",
        "caption": "Sample data. Replace with the schedule from your content.",
        "data": {
            "unit": "week",
            "tasks": [
                {"name": "Requirements", "start": 0, "duration": 3},
                {"name": "Design", "start": 3, "duration": 2, "depends_on": ["Requirements"]},
                {"name": "Build", "start": 5, "duration": 6, "depends_on": ["Design"]},
                {"name": "Test", "start": 10, "duration": 3, "depends_on": ["Build"]},
                {"name": "Go live", "start": 13, "duration": 0, "depends_on": ["Test"]},
            ],
        },
    },
    {
        "kind": "flow",
        "blurb": "A left-to-right chain of numbered boxes. Each node takes a label and an optional note.",
        "title": "Sample process",
        "caption": "Sample data. Replace with the sequence from your content.",
        "data": {
            "nodes": [
                {"label": "Request", "note": "Someone asks for the work."},
                {"label": "Review", "note": "Decide whether to take it on."},
                {"label": "Approve", "note": "Commit budget and people."},
                {"label": "Deliver", "note": "Do the work."},
            ]
        },
    },
    {
        "kind": "table",
        "blurb": "A comparison table. Every row must have exactly as many cells as there are headers.",
        "title": "Sample comparison",
        "caption": "Sample data. Replace with the comparison from your content.",
        "data": {
            "headers": ["Option", "Cost", "Effort"],
            "rows": [
                ["Do nothing", "$0", "None"],
                ["Partial rollout", "$12,000", "Medium"],
                ["Full rollout", "$40,000", "High"],
            ],
        },
    },
]


def render(kind, data, title=""):
    """Dispatch to a renderer. Unknown kinds raise rather than render nothing,
    so a typo in content surfaces at load time instead of as a blank panel."""
    renderer = RENDERERS.get(kind)
    if renderer is None:
        known = ", ".join(sorted(RENDERERS))
        raise VisualError(f"unknown visual kind '{kind}' (known kinds: {known})")
    return renderer(data, title)
