"""Migration automatique légère pour SQLite (développement).

`db.create_all()` crée les tables manquantes mais ne modifie jamais les
tables existantes. Cette fonction ajoute les colonnes introduites au fil
des sprints, de façon idempotente. Pour une montée de version en production
(PostgreSQL notamment), préférer Alembic.
"""

import logging

from sqlalchemy import inspect, text

logger = logging.getLogger("chatbot-vocal")

# table -> {colonne: définition SQL complet après ADD COLUMN}
EXPECTED_COLUMNS = {
    "users": {
        "role": "TEXT NOT NULL DEFAULT 'user'",
        "monthly_quota_minutes": "INTEGER",
    },
    "transcriptions": {
        "diarized": "BOOLEAN NOT NULL DEFAULT 0",
        "speakers": "JSON",
        "summary": "TEXT",
        "action_items": "JSON",
        "keywords": "JSON",
        "sentiment": "JSON",
        "insights_engine": "VARCHAR(20)",
    },
    "jobs": {
        "diarize": "BOOLEAN NOT NULL DEFAULT 0",
    },
}


def ensure_sqlite_schema(db):
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    with db.engine.begin() as connection:
        for table, columns in EXPECTED_COLUMNS.items():
            if table not in existing_tables:
                continue  # sera créée par create_all()
            present = {column["name"] for column in inspector.get_columns(table)}
            for column, definition in columns.items():
                if column not in present:
                    connection.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    )
                    logger.info("Migration SQLite : colonne %s ajoutée à %s", column, table)
