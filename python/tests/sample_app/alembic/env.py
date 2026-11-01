"""The sample application's Alembic environment, as an application writes it with jigkit.

``SAMPLE_PLAIN_ENV=1`` runs the migrations the way Alembic's stock template does instead,
with foreign keys left on, so the tests can show the checks catch what jigkit prevents.
"""

import os

from sample_schema import Base, Settings

if os.environ.get("SAMPLE_PLAIN_ENV"):
    import asyncio

    from alembic import context

    from jigkit.db import create_engine

    def _run(connection):
        context.configure(
            connection=connection, target_metadata=Base.metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()

    async def _main():
        engine = create_engine(Settings().resolved_database_url)
        async with engine.connect() as connection:
            await connection.run_sync(_run)
        await engine.dispose()

    asyncio.run(_main())
else:
    from jigkit.migrations import run_migrations

    run_migrations(Settings().resolved_database_url, Base.metadata)
