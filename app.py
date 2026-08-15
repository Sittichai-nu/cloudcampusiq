import os

from flask import Blueprint, Flask, jsonify, render_template, request
from markupsafe import Markup

from api import api_bp
from content_loader import format_stats, rebuild_database
from formatting import format_body
from models import (
    Course,
    Domain,
    Lesson,
    Phase,
    Topic,
    TOPIC_KINDS,
    db,
)
from search import highlight, search_all, total_hits
from visuals import EXAMPLES, render as render_visual

pages = Blueprint("pages", __name__)


def visual_markup(kind, data, title=""):
    """Renderers emit trusted markup they built themselves (all interpolated
    content is escaped inside visuals.py), so it is marked safe here rather
    than being escaped a second time into visible angle brackets."""
    return Markup(render_visual(kind, data, title))


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@pages.route("/")
def home():
    return render_template("index.html", courses=Course.query.order_by(Course.code).all())


@pages.route("/courses")
def courses():
    return render_template("courses.html", courses=Course.query.order_by(Course.code).all())


@pages.route("/courses/<course_code>")
def course_detail(course_code):
    course = Course.query.filter_by(code=course_code.upper()).first_or_404()
    return render_template("course_detail.html", course=course)


@pages.route("/courses/<course_code>/lesson/<int:number>")
def lesson_detail(course_code, number):
    course = Course.query.filter_by(code=course_code.upper()).first_or_404()
    lesson = Lesson.query.filter_by(course_id=course.id, number=number).first_or_404()
    return render_template("lesson_detail.html", course=course, lesson=lesson)


@pages.route("/topics")
def topics_index():
    """Every topic in one place, narrowed by the three axes a reader is likely
    to already know: exam domain, life cycle phase, or what kind of thing it is."""
    domain_code = request.args.get("domain", "").strip()
    phase_slug = request.args.get("phase", "").strip()
    kind = request.args.get("kind", "").strip()

    topics = Topic.query.order_by(Topic.title).all()

    if domain_code:
        topics = [t for t in topics if any(d.code == domain_code for d in t.domains())]
    if phase_slug:
        topics = [t for t in topics if t.phase and t.phase.slug == phase_slug]
    if kind:
        topics = [t for t in topics if t.kind == kind]

    return render_template(
        "topics_index.html",
        topics=topics,
        domains=Domain.query.order_by(Domain.order).all(),
        phases=Phase.query.order_by(Phase.order).all(),
        kinds=TOPIC_KINDS,
        active={"domain": domain_code, "phase": phase_slug, "kind": kind},
    )


@pages.route("/topics/<slug>")
def topic_detail(slug):
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    return render_template("topic_detail.html", topic=topic)


@pages.route("/domains")
def domains_index():
    return render_template("domains_index.html", domains=Domain.query.order_by(Domain.order).all())


@pages.route("/domains/<code>")
def domain_detail(code):
    domain = Domain.query.filter_by(code=code).first_or_404()
    return render_template("domain_detail.html", domain=domain)


@pages.route("/phases")
def phases_index():
    return render_template("phases_index.html", phases=Phase.query.order_by(Phase.order).all())


@pages.route("/phases/<slug>")
def phase_detail(slug):
    phase = Phase.query.filter_by(slug=slug).first_or_404()
    return render_template(
        "phase_detail.html",
        phase=phase,
        phases=Phase.query.order_by(Phase.order).all(),
    )


@pages.route("/search")
def search():
    query = request.args.get("q", "")
    results = search_all(query)
    return render_template(
        "search_results.html",
        query=query,
        results=results,
        total=total_hits(results),
    )


@pages.route("/diagrams")
def diagrams():
    """The renderer catalog: every diagram type the platform can draw, with the
    YAML that produces it. Sample data only -- this page is documentation for
    content authors, not course material."""
    return render_template("diagrams.html", examples=EXAMPLES)


@pages.route("/login")
def login():
    return render_template("login.html")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
        app.instance_path, "course_content.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Deploys run `flask rebuild-content` before starting the server. This flag
    # covers local runs and any boot that finds an empty database.
    app.config["AUTO_REBUILD_CONTENT"] = True

    if config:
        app.config.update(config)

    db.init_app(app)
    app.register_blueprint(pages)
    app.register_blueprint(api_bp)

    app.jinja_env.filters["format_body"] = format_body
    app.jinja_env.filters["highlight"] = highlight
    app.jinja_env.globals["render_visual"] = visual_markup

    @app.errorhandler(404)
    def not_found(error):
        # Without this, an unmatched /api/v1/* URL returns the HTML error page
        # to a client that asked for JSON.
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found", "path": request.path}), 404
        return render_template("404.html"), 404

    @app.cli.command("rebuild-content")
    def rebuild_content_command():
        """Rebuild the content database from content/*.yaml."""
        stats = rebuild_database(app, db)
        print(f"Rebuilt content DB: {format_stats(stats)}")

    if app.config["AUTO_REBUILD_CONTENT"]:
        ensure_content(app)

    return app


def ensure_content(app):
    """Populate the database if it is empty.

    The previous version rebuilt unconditionally at import time, which meant
    every gunicorn worker raced the others running drop_all() against the same
    SQLite file -- requests landing mid-rebuild saw a half-built database.
    Rebuilding only when there is nothing there makes extra workers no-ops.
    """
    with app.app_context():
        db.create_all()
        already_loaded = Course.query.count() > 0

    if already_loaded:
        return

    stats = rebuild_database(app, db)
    print(f"Rebuilt content DB: {format_stats(stats)}")


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
