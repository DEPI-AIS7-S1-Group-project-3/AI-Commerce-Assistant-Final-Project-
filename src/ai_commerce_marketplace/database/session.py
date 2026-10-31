from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ai_commerce_marketplace.core.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session():
    with SessionLocal() as session:
        yield session