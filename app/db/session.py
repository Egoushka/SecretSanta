from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False)


def init_engine(database_url: str):
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    SessionLocal.configure(bind=engine)
    return engine


def _ensure_initialized() -> None:
    if SessionLocal.kw.get("bind") is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() before use.")


@contextmanager
def get_session():
    _ensure_initialized()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
