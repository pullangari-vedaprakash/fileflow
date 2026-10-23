from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
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

engine = create_async_engine(url, echo=False, connect_args=connect_args)
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


REQUIRED_INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_files_user_id ON files (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_files_user_created ON files (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_user_id ON jobs (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_file_id ON jobs (file_id)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs (status)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_user_created ON jobs (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_status_created ON jobs (status, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_jobs_priority_created ON jobs (priority, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_results_job_id ON results (job_id)",
    "CREATE INDEX IF NOT EXISTS ix_workers_heartbeat_status ON workers (last_heartbeat, status)",
]


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for idx_sql in REQUIRED_INDEXES:
            await conn.execute(text(idx_sql))
