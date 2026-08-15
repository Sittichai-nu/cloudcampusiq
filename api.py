from flask import Blueprint, jsonify, request

from models import Course, Domain, Lesson, Phase, Topic
from search import search_all, total_hits

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


@api_bp.errorhandler(404)
def api_not_found(error):
    return jsonify({"error": "not found"}), 404


@api_bp.route("/courses")
def list_courses():
    courses = Course.query.order_by(Course.code).all()
    return jsonify([course.to_dict() for course in courses])


@api_bp.route("/courses/<course_code>")
def get_course(course_code):
    course = Course.query.filter_by(code=course_code.upper()).first_or_404()
    return jsonify(course.to_dict(include_lessons=True))


@api_bp.route("/courses/<course_code>/lessons/<int:number>")
def get_lesson(course_code, number):
    course = Course.query.filter_by(code=course_code.upper()).first_or_404()
    lesson = Lesson.query.filter_by(course_id=course.id, number=number).first_or_404()
    return jsonify(lesson.to_dict(include_topics=True))


@api_bp.route("/topics")
def list_topics():
    """Supports the same narrowing as the /topics page: ?domain=, ?phase=, ?kind=."""
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

    return jsonify([topic.to_dict(include_body=False) for topic in topics])


@api_bp.route("/topics/<slug>")
def get_topic(slug):
    topic = Topic.query.filter_by(slug=slug).first_or_404()
    return jsonify(topic.to_dict())


@api_bp.route("/domains")
def list_domains():
    domains = Domain.query.order_by(Domain.order).all()
    return jsonify([domain.to_dict(include_objectives=True) for domain in domains])


@api_bp.route("/domains/<code>")
def get_domain(code):
    domain = Domain.query.filter_by(code=code).first_or_404()
    data = domain.to_dict(include_objectives=True)
    data["topics"] = [topic.to_dict(include_body=False) for topic in domain.topics()]
    return jsonify(data)


@api_bp.route("/phases")
def list_phases():
    phases = Phase.query.order_by(Phase.order).all()
    return jsonify([phase.to_dict() for phase in phases])


@api_bp.route("/phases/<slug>")
def get_phase(slug):
    phase = Phase.query.filter_by(slug=slug).first_or_404()
    data = phase.to_dict()
    data["topics"] = [topic.to_dict(include_body=False) for topic in phase.topics]
    return jsonify(data)


@api_bp.route("/search")
def search():
    query = request.args.get("q", "")
    results = search_all(query)
    return jsonify(
        {
            "query": query,
            "total": total_hits(results),
            "results": {
                kind: [hit.to_dict() for hit in hits] for kind, hits in results.items()
            },
        }
    )
