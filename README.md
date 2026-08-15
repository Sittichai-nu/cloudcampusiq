# CloudCampusIQ — Cloud-Based Online Learning Platform

[![Azure](https://img.shields.io/badge/Microsoft_Azure-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/features/actions)

## Live Application
🌐 [https://cloudcampusiq.onrender.com](https://cloudcampusiq.onrender.com)

*Originally deployed on Azure App Service (architecture below). Currently mirrored on Render's free tier while the Azure student subscription is between credit cycles. Free-tier note: the app sleeps after ~15 min idle and may take 30–60s to wake on first load.*

---

## Project Overview

CloudCampusIQ is a deployed cloud-based learning platform. It serves structured
course content — courses, lessons, and topics — and makes that content navigable
from whichever direction a learner already knows: by course, by exam domain and
objective, by project life cycle phase, or by free-text search.

Course content lives as YAML in version control and is compiled into a queryable
database at deploy time. Topics carry their own relationships, procedures, and
diagrams, so a topic page can answer "where does this fit?" rather than being a
dead end.

---

## What it does

**Content is structured, not just formatted.** Every topic knows:

- which **lesson** and **course** it belongs to
- which **exam domain and objective** it satisfies, with the objective's own
  sub-point checklist so a reader can self-test
- which **project life cycle phase** it applies to
- what **kind** of thing it is — concept, tool, document, process, or formula
- which other topics **relate** to it — both hand-authored links and topics
  automatically cross-linked because they share an objective
- an ordered list of **steps**, where the topic describes a procedure
- an optional **diagram**, rendered as inline SVG from the topic's own data

**Ways to find something:**

| Route | What it does |
|---|---|
| `/courses` | Course catalog, rendered from `content/` |
| `/courses/<code>` | Lessons in a course |
| `/courses/<code>/lesson/<n>` | Topics in a lesson |
| `/topics` | Every topic, filterable by domain × phase × kind |
| `/topics/<slug>` | A topic, with its full "Where this fits" panel |
| `/domains`, `/domains/<code>` | Browse by exam domain and objective |
| `/phases`, `/phases/<slug>` | Browse by project life cycle phase |
| `/search?q=` | Site-wide search over topic text, titles, and objective codes |
| `/diagrams` | Diagram renderer catalog, for content authors |
| `/api/v1/…` | JSON API mirroring all of the above |

---

## Architecture
```
Students (Internet)
        ↓
   GitHub Actions (CI/CD)
        ↓
  Azure App Service (PaaS)
  ├── Flask Web Application
  │   ├── content/*.yaml  ── source of truth, in version control
  │   └── SQLite          ── disposable read cache, rebuilt at deploy
  ├── Azure Blob Storage (Course Materials)
  ├── Azure Active Directory (IAM)
  ├── Azure Monitor (Performance Alerts)
  └── Azure Cost Management (Spending Dashboard)
```

**Why SQLite is disposable:** neither deploy target keeps a local file across a
redeploy, so the database is rebuilt from YAML on every deploy rather than
treated as durable storage. Content changes ship through `git`, and the database
is never the thing being edited.

---

## Technologies Used

| Category | Technology |
|---|---|
| Cloud Provider | Microsoft Azure |
| Hosting | Azure App Service (PaaS) |
| Backend | Python 3.12 + Flask + SQLAlchemy |
| Content | YAML compiled to SQLite at deploy time |
| Frontend | HTML5, CSS3, JavaScript, server-rendered inline SVG |
| Storage | Azure Blob Storage |
| Security | Azure Active Directory + RBAC |
| Monitoring | Azure Monitor |
| Cost Management | Azure Cost Management |
| CI/CD | GitHub Actions |
| Testing | pytest |

No frontend framework and no charting library: diagrams are SVG generated on the
server, so pages render fully without JavaScript and without a CDN request.

---

## Local Development

```bash
git clone https://github.com/Sittichai-nu/cloudcampusiq.git
cd cloudcampusiq
```

Everything routine goes through one script:

| Command | Does |
|---|---|
| `.\dev.ps1` | rebuild content, serve on http://localhost:5000 |
| `.\dev.ps1 rebuild` | rebuild the content database from YAML |
| `.\dev.ps1 test` | run the test suite |
| `.\dev.ps1 check` | rebuild + test + banned-string scan |
| `.\dev.ps1 install` | install runtime and dev dependencies |

`dev.sh` is the POSIX equivalent with the same subcommands.

---

## Adding content

```
content/<course>/
├── course.yaml      code, title, description
├── domains.yaml     exam domains and objectives
├── phases.yaml      project life cycle phases
└── lesson_NN.yaml   one file per lesson
```

A new folder with a `course.yaml` appears in the catalog automatically — nothing
is hardcoded in a template. Only `title` and `body` are required on a topic;
every other field adds another way to find it later.

The loader validates strictly and fails the build on an unknown topic kind, an
undefined phase, a `related` slug pointing at nothing, a duplicate slug, or a
malformed diagram spec. Bad content breaks the build rather than rendering as a
blank panel.

See `.claude/skills/dev/SKILL.md` for the full authoring reference, or `/diagrams`
in the running app for the diagram catalog.

---

## Testing

```bash
.\dev.ps1 test
```

110 tests covering the content loader's validation rules, body formatting, each
diagram renderer, search ranking, every page route, and the JSON API contract.
Tests run against the real `content/` tree, so a schema change that breaks
published content fails the suite.

---

## Cloud Infrastructure (configured on Azure)

As part of the cloud-engineering deliverable for this project, the following were configured directly on Azure (independent of the Flask app's own code):

- Azure Active Directory app registration with Role-Based Access Control (RBAC)
- Azure Blob Storage container with private access — no anonymous access permitted
- HTTPS Only enforced on Azure App Service, TLS 1.2 minimum
- Azure Monitor alert rule (Http5xx > 5 in 5 minutes)
- Azure Cost Management spending dashboard

These demonstrate Azure identity, storage, and monitoring configuration; wiring the Flask app itself to consume them (e.g., enforcing AD login) is a planned next step, not yet implemented in code.

Note: the login page is a front-end demo — it is not yet wired to a backend authentication service.

---

## DevOps Pipeline

Every push to the `main` branch automatically:

1. Checks out the latest code
2. Sets up Python 3.12 environment
3. Installs all dependencies
4. Packages the application
5. Deploys to Azure App Service

```yaml
on:
  push:
    branches:
      - main
```

---

## Project Structure
```
cloudcampusiq/
├── app.py                  # App factory, page routes, Jinja filters
├── api.py                  # JSON API blueprint (/api/v1)
├── models.py               # Course, Lesson, Topic, Domain, Objective, Phase, Visual
├── content_loader.py       # YAML → database, with strict validation
├── visuals.py              # Diagram renderers (gantt, flow, table)
├── formatting.py           # Topic body → HTML
├── search.py               # Site-wide search
├── dev.ps1 / dev.sh        # Developer entry point
├── content/                # Course content — the source of truth
├── templates/
├── static/
├── tests/
└── .github/workflows/deploy.yml
```

---

## Monitoring and Cost Management

- **Azure Monitor** — HTTP server error alerts (Http5xx > 5 in 5 minutes)
- **Azure Cost Management** — Real-time spending dashboard
- **Current cost** — Less than $0.01/month (Azure for Students)

---

## Author

**Nu Chai**
WGU — D782 Network Architecture and Cloud Computing
April 2026

---

## License

This project is for educational purposes as part of WGU coursework.
