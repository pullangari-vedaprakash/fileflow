from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import get_settings

settings = get_settings()

# Neon URLs include sslmode / channel_binding that asyncpg rejects.
# Strip them and pass SSL through connect_args instead.
url = settings.database_url
connect_args = {}
if "ssl=" in url or "sslmode=" in url or "neon.tech" in url:
    base, _, query = url.partition("?")
    url = base
    connect_args["ssl"] = "require"

engine = create_async_engine(url, echo=settings.debug, connect_args=connect_args)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)