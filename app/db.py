from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_tables()


def ensure_runtime_tables() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            table.create(bind=engine, checkfirst=True)
    ensure_runtime_columns()


def ensure_runtime_columns() -> None:
    inspector = inspect(engine)
    if "meetings" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("meetings")}
    column_sql = {
        "meeting_type": "ALTER TABLE meetings ADD COLUMN meeting_type VARCHAR(48) DEFAULT 'progress_meeting' NOT NULL",
        "route_suggestion": "ALTER TABLE meetings ADD COLUMN route_suggestion VARCHAR(48)",
        "route_confidence": "ALTER TABLE meetings ADD COLUMN route_confidence VARCHAR(16)",
        "route_reason": "ALTER TABLE meetings ADD COLUMN route_reason TEXT",
    }
    with engine.begin() as connection:
        for column_name, ddl in column_sql.items():
            if column_name not in existing_columns:
                connection.execute(text(ddl))


def get_db() -> Generator[Session, None, None]:
    ensure_runtime_columns()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
