from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Only create engine if database_url is configured
if settings.database_url:
    engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
else:
    engine = None
    AsyncSessionLocal = None


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    if AsyncSessionLocal is None:
        raise Exception("Database not configured. Set DATABASE_URL environment variable.")
    async with AsyncSessionLocal() as session:
        yield session
