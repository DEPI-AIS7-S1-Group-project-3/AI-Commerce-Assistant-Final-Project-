import os
from contextlib import contextmanager
from pathlib import Path

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://app:app_dev_password@localhost:5432/ai_commerce_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from ai_commerce_marketplace.database.session import engine  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# حماية: الاختبارات بتعمل downgrade كامل، فممنوع تشتغل على DB حقيقية
assert make_url(TEST_DATABASE_URL).database.endswith("_test"), (
    "اسم الـ DB للاختبارات لازم ينتهي بـ _test"
)


@pytest.fixture(scope="session")
def migrated_db():
    """يبني الـ schema من الصفر عن طريق الـ migrations (بيختبرها كمان)."""
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture
def session(migrated_db):
    """session لكل اختبار، وكل اللي بيتعمل فيه بيتلغي في الآخر."""
    with engine.connect() as conn:
        outer = conn.begin()
        s = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield s
        finally:
            s.close()
            outer.rollback()


@pytest.fixture
def rejected(session):
    """with rejected(): ...  ← الكود اللي جواها لازم الـ DB ترفضه (IntegrityError)."""

    @contextmanager
    def _rejected():
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                yield

    return _rejected