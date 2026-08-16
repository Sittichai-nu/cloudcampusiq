"""Turn a topic body into real HTML.

Topic bodies are plain text authored in YAML block scalars. They carry real
structure -- lead-in lines, bullet lists, numbered lists, a closing "Remember:"
note -- but dropping that text into a single <p> collapses every newline and
renders it as one unreadable block.

This converts that structure into markup. It is deliberately not a Markdown
parser: the content uses a small, consistent set of conventions, and a narrow
converter that fails visibly beats a general one that silently reinterprets
prose (a line starting with "#" is a heading in Markdown, but in this content
it is just a sentence).

Everything is escaped before any markup is added, so content can never inject
HTML.
"""

import re

from markupsafe import Markup

BULLET = re.compile(r"^-\s+(.*)$")
NUMBERED = re.compile(r"^(\d+)\.\s+(.*)$")
BLANK_LINE = re.compile(r"\n\s*\n")

# Paragraphs opening with one of these become a highlighted callout rather than
# ordinary body text. They are the author's own memory aids.
CALLOUT_PREFIXES = ("Remember:", "Note:", "Key point:")

# Deliberately NOT "Key exam point". These lines are study mnemonics written by
# the content author; nothing in the source says the exam asks them. Claims
# about exam scope belong in a topic's `exam_note`, which cites the objectives
# appendix. Labelling a mnemonic as an exam fact is a claim we cannot support.
CALLOUT_LABEL = "Recall"


def _escape(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _inline(text):
    """Escape. No typographic substitution happens here.

    This used to turn " -- " into an em dash. House style now bans dash
    punctuation outright, and content_loader rejects it at build time, so
    converting it here would have quietly manufactured the very character the
    content is not allowed to contain.
    """
    return _escape(text.strip())


def _join_wrapped(lines):
    """YAML block scalars hard-wrap at ~72 columns mid-sentence. Rejoining with
    a single space restores the author's actual sentence."""
    return " ".join(line.strip() for line in lines if line.strip())


def _collect_items(lines, pattern):
    """Group marker-prefixed lines into items, folding wrapped continuation
    lines into the item above them."""
    items = []
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            items.append([match.group(match.lastindex)])
        elif items and line.strip():
            items[-1].append(line)
        elif line.strip():
            # A continuation before any marker -- treat it as its own item
            # rather than dropping content on the floor.
            items.append([line])
    return [_join_wrapped(item) for item in items]


def _is_lead_in(line):
    stripped = line.strip()
    return (
        stripped.endswith(":")
        and not BULLET.match(stripped)
        and not NUMBERED.match(stripped)
        and len(stripped) <= 80
    )


def _render_paragraph(lines):
    text = _join_wrapped(lines)
    if not text:
        return ""

    for prefix in CALLOUT_PREFIXES:
        if text.startswith(prefix):
            rest = _inline(text[len(prefix):])
            return (
                '<div class="topic-callout">'
                f'<span class="topic-callout-label">{CALLOUT_LABEL}</span>'
                f"<p>{rest}</p></div>"
            )

    return f"<p>{_inline(text)}</p>"


def _render_block(block):
    lines = [line for line in block.split("\n") if line.strip()]
    if not lines:
        return ""

    head = ""
    if _is_lead_in(lines[0]) and len(lines) > 1:
        head = f'<h4 class="topic-subhead">{_inline(lines[0].rstrip(":"))}</h4>'
        lines = lines[1:]
    elif _is_lead_in(lines[0]) and len(lines) == 1:
        return f'<h4 class="topic-subhead">{_inline(lines[0].rstrip(":"))}</h4>'

    first = lines[0].strip()

    if BULLET.match(first):
        items = _collect_items(lines, BULLET)
        rendered = "".join(f"<li>{_inline(item)}</li>" for item in items)
        return f'{head}<ul class="topic-list">{rendered}</ul>'

    if NUMBERED.match(first):
        items = _collect_items(lines, NUMBERED)
        rendered = "".join(f"<li>{_inline(item)}</li>" for item in items)
        start = NUMBERED.match(first).group(1)
        return f'{head}<ol class="topic-list" start="{start}">{rendered}</ol>'

    return head + _render_paragraph(lines)


def format_body(text):
    """Render a topic body as HTML. Registered as the `format_body` Jinja
    filter in app.py."""
    if not text:
        return Markup("")

    blocks = BLANK_LINE.split(text.strip())
    return Markup("".join(_render_block(block) for block in blocks))


def plain_text(text):
    """Flatten a body to a single searchable/snippet-able line."""
    if not text:
        return ""
    collapsed = " ".join(line.strip() for line in text.split("\n"))
    return re.sub(r"\s+", " ", collapsed).strip()
