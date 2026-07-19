import pytest
from typing import Generator, AsyncGenerator, Any
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.session import get_db, get_async_db
from app.models.base import Base

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class AsyncSessionWrapper:
    """Mock/wrapper class that delegates AsyncSession calls to a sync session for testing."""
    def __init__(self, sync_session: Session):
        self.sync_session = sync_session

    async def execute(self, statement, *args, **kwargs):
        return self.sync_session.execute(statement, *args, **kwargs)

    def add(self, instance, *args, **kwargs):
        return self.sync_session.add(instance, *args, **kwargs)

    async def commit(self):
        self.sync_session.commit()

    async def refresh(self, instance, *args, **kwargs):
        self.sync_session.refresh(instance, *args, **kwargs)

    async def close(self):
        self.sync_session.close()


@pytest.fixture(scope="session", autouse=True)
def sanitize_test_settings() -> None:
    """Ensure tests run with valid cryptographic keys even if .env has placeholders."""
    from app.core.settings import settings
    if not settings.ONDC_SIGNING_PRIVATE_KEY or "INSERT_" in settings.ONDC_SIGNING_PRIVATE_KEY:
        settings.ONDC_SIGNING_PRIVATE_KEY = "MC4CAQAwBQYDK2VwBCIEINT3ZlYyE8tLgU7w1+J9wLzC2e+Y019V8B0V05YkR7m5"
    if not settings.ONDC_SIGNING_PUBLIC_KEY or "INSERT_" in settings.ONDC_SIGNING_PUBLIC_KEY:
        settings.ONDC_SIGNING_PUBLIC_KEY = "MCowBQYDK2VwAyEAWIQTxIJjgQ+BHrEIwnEioCMxtXBLswKuUayrWP5e0xk="
    if not settings.ONDC_ENC_PRIVATE_KEY or "INSERT_" in settings.ONDC_ENC_PRIVATE_KEY:
        settings.ONDC_ENC_PRIVATE_KEY = "MC4CAQAwBQYDK2VwBCIEINT3ZlYyE8tLgU7w1+J9wLzC2e+Y019V8B0V05YkR7m5"
    if not settings.ONDC_ENC_PUBLIC_KEY or "INSERT_" in settings.ONDC_ENC_PUBLIC_KEY:
        settings.ONDC_ENC_PUBLIC_KEY = "MCowBQYDK2VwAyEAWIQTxIJjgQ+BHrEIwnEioCMxtXBLswKuUayrWP5e0xk="


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> Generator[None, None, None]:
    """Create all tables in the testing database before starting tests."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a clean database session for each test case, wrapping in a transaction."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with database session dependencies overridden."""
    def _get_test_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    async def _get_test_async_db() -> AsyncGenerator[Any, None]:
        try:
            yield AsyncSessionWrapper(db_session)
        finally:
            pass

    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_async_db] = _get_test_async_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

