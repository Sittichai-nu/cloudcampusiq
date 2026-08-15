---
name: dev
description: Work on the CloudCampusIQ learning platform. Run it, add or edit course content (courses, lessons, topics, steps, diagrams), add a diagram renderer, run checks, and commit. Use whenever working in the cloudcampusiq repo.
---

# CloudCampusIQ

A Flask learning platform. Course content lives in YAML under `content/`, is
loaded into SQLite at boot, and is browsable by course, lesson, topic, exam
domain, and project life cycle phase, with site-wide search.

## The one rule that matters

**`content/**/*.yaml` is the source of truth. SQLite is a disposable cache.**

The database is dropped and rebuilt from YAML on every rebuild. Never write to
the database directly, never commit `instance/`, and never "fix" content by
editing the DB, because the change would vanish on the next boot.

## Commands

Always use the script rather than raw commands, so behaviour stays identical
for everyone:

| Command | Does |
|---|---|
| `.\dev.ps1` | rebuild content, serve on http://localhost:5000 |
| `.\dev.ps1 rebuild` | rebuild the content DB from YAML |
| `.\dev.ps1 test` | run the test suite |
| `.\dev.ps1 check` | rebuild + test + banned-string scan. **Run before every commit** |
| `.\dev.ps1 install` | install runtime + dev dependencies |

`dev.sh` is the POSIX mirror with identical subcommands.

## Content rules

1. **Never invent course facts.** Exam content comes only from the official
   course material the user names. If a fact is not in an existing verified
   source, ask for it. Do not fill the gap from general project management
   knowledge. Getting this wrong puts unverified material in front of someone
   studying for an exam.
2. `verified` and `source` are claims about provenance. Do not set
   `verified: true` on anything you have not been given a source for.
3. **`D324` is a banned string.** The project was renamed to `PM101`. `.\dev.ps1 check`
   fails the build if it reappears. Add new banned strings to `$BannedStrings`
   in `dev.ps1` and `BANNED_STRINGS` in `dev.sh`.
4. **No dash punctuation.** Em dashes and ` -- ` are banned in content. Write
   `Term: definition` or use a full stop. `content_loader` rejects them at build
   time (`BANNED_PUNCTUATION`), so a dash fails the build with the file and the
   offending excerpt named.

   The check is deliberately narrow and matches only em dash, en dash, and the
   double-hyphen separator. A plain hyphen is load-bearing and stays: inside
   words (`end-user`), in codes (`PK0-005`), in ranges (`3-5`), and as the minus
   sign in worked calculations (`$20,000 - $11,000 = $9,000`, `-5.3%`). Do not
   widen it to all hyphens; it would corrupt the arithmetic in the content.

## Layout

```
content/pm101/
├── course.yaml      code, title, description
├── domains.yaml     exam domains + objectives (titles are user-supplied)
├── phases.yaml      project life cycle phases
└── lesson_NN.yaml   one file per lesson
```

Adding a course = a new folder under `content/` with a `course.yaml`. It shows
up on `/courses` automatically; nothing is hardcoded.

## Adding a topic

Topics go in the `topics:` list of a `lesson_NN.yaml`. Only `title` and `body`
are required. Everything else adds a way to find the topic later.

```yaml
  - title: "Develop the Business Case"
    slug: "business-case"          # the URL: /topics/business-case. Must be unique.
    order: 2
    kind: "document"               # concept | tool | document | process | formula
    phase: "discovery"             # must match a slug in phases.yaml
    objectives: ["2.1", "4.1"]     # domain 2.0 and 4.0 are derived from the prefix
    summary: >
      One sentence. Shown on cards and in search results.
    related:
      - slug: "project-management-basics"
        note: "Why this edge exists"
    steps:                         # optional, numbered procedure
      - title: "Executive summary"
        body: "Write it last."
    visuals:                       # optional, see below. A list.
      - kind: "table"
        title: "..."
        caption: "..."
        data: { ... }
    body: |
      Plain text. Structure is preserved. See below.
```

Topics that share an objective are cross-linked automatically, so tagging
objectives is the cheapest way to build the graph. `related:` is for edges that
tagging cannot express.

### Body formatting

`formatting.py` converts bodies to HTML. It is not Markdown. It recognises
exactly these conventions:

- Blank line: starts a new block.
- `- item`: bullet list. Wrapped continuation lines fold into the item above.
- `1. item`: numbered list.
- A short line ending in `:` becomes a sub-heading for the block under it.
- A paragraph starting `Remember:`, `Note:`, or `Key point:` becomes a
  highlighted "🔑 Key exam point" callout.

No typographic substitution happens. The formatter never manufactures a dash.

Everything is escaped before markup is added; content cannot inject HTML.

## Diagrams

A topic can carry any number of diagrams. See `/diagrams` in the running app for a
live catalog of every renderer with its input shape.

```yaml
visuals:
  - kind: "gantt"      # gantt | flow | table
    title: "..."
    caption: "..."
    data:
      unit: "week"
      tasks:
        - { name: "Planning", start: 0, duration: 3 }
        - { name: "Approval", start: 3, duration: 0, depends_on: ["Planning"] }
  - kind: "table"
    title: "..."
    data:
      headers: ["A", "B"]
      rows: [["1", "2"]]
```

A dense topic usually has more than one thing worth comparing. Prefer several
small tables over one long prose list: a comparison reads far better as a table
than as nested bullets. `visual:` (singular) is still accepted for a single
diagram.

- `gantt`: bars on a time axis. `duration: 0` renders a milestone diamond.
  `depends_on` names draw dependency arrows.
- `flow`: a left-to-right chain of numbered boxes. `nodes: [{label, note}]`.
- `table`: a comparison table. `headers` + `rows`, row length must match.

Diagrams are server-rendered inline SVG using the site's CSS custom properties,
so they need no JavaScript and match the palette automatically. **Do not add a
chart library or a CDN dependency.**

**Adding a renderer:** write a pure `render_x(data, title="") -> str` in
`visuals.py`, add it to `RENDERERS`, add an entry to `EXAMPLES` (which is what
`/diagrams` documents), and add a test. Specs are rendered once at content-load
time, so a malformed spec fails the build rather than showing a blank panel.

## Architecture notes

- `create_app()` in `app.py` is the factory; `app = create_app()` at module
  level is what gunicorn imports (`app:app`).
- Content is rebuilt at boot **only if the database is empty**. Deploys run
  `flask --app app.py rebuild-content` explicitly first (`startup.sh`,
  `Procfile`). Do not restore an unconditional rebuild at import time, because under
  gunicorn every worker would race the others dropping the same SQLite file.
- `visuals.py`, `formatting.py`, and `search.py` have no Flask imports on
  purpose, so they are testable without an app context.
- Search is deliberately plain substring matching in `search.py`. The corpus is
  small; do not add an index or a search dependency without a reason.
- `content_loader.py` validates strictly and raises `ContentError` naming the
  file and item. Keep it that way, because bad content should break the build.

## Before committing

1. `.\dev.ps1 check` must pass.
2. Confirm `instance/` and `*.db` are not staged.
3. Pushing to `main` triggers `.github/workflows/deploy.yml`, which deploys to
   Azure App Service. Confirm with the user before pushing.
