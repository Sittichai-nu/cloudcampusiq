import sys
from pathlib import Path

import pytest

# The app modules live at the repo root, next to tests/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from content_loader import rebuild_database  # noqa: E402
from models import db  # noqa: E402


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    """One app, built against the real content/ tree in a throwaway database.

    Tests run against real content on purpose: the content files are part of
    the product, and a schema change that breaks them should fail here.
    """
    db_path = tmp_path_factory.mktemp("instance") / "test.db"
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path.as_posix()}",
            "AUTO_REBUILD_CONTENT": False,
        }
    )
    rebuild_database(application, db)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def ctx(app):
    """Push an app context so model queries work outside a request."""
    with app.app_context():
        yield
