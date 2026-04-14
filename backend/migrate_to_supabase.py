#!/usr/bin/env python3
"""
Migration Script: SQLite to PostgreSQL (Supabase)

This script helps migrate data from SQLite to PostgreSQL.
Run this BEFORE switching your environment to PostgreSQL.

Usage:
    python migrate_to_supabase.py --source ./orchestrix.db --target "postgresql://..."

Options:
    --source     Path to SQLite database (default: ./orchestrix.db)
    --target     PostgreSQL connection string
    --dry-run    Show what would be migrated without making changes
"""

import argparse
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Migrate Orchestrix database to PostgreSQL"
    )
    parser.add_argument(
        "--source", default="./orchestrix.db", help="Path to SQLite database"
    )
    parser.add_argument(
        "--target", help="PostgreSQL connection string (or set SUPABASE_DB_URL env var)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show migration plan without executing"
    )
    return parser.parse_args()


def export_sqlite_data(db_path):
    """Export data from SQLite database."""
    try:
        from sqlalchemy import create_engine, inspect
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(f"sqlite:///{db_path}")
        Session = sessionmaker(bind=engine)
        session = Session()

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        data = {}
        for table in tables:
            if table == "sqlite_sequence":
                continue

            logger.info(f"Exporting table: {table}")
            result = session.execute(f"SELECT * FROM {table}")
            columns = result.keys()
            rows = result.fetchall()
            data[table] = {
                "columns": list(columns),
                "rows": [dict(zip(columns, row)) for row in rows],
            }
            logger.info(f"  - Exported {len(rows)} rows")

        session.close()
        engine.dispose()

        return data

    except Exception as e:
        logger.error(f"Error exporting SQLite data: {e}")
        return None


def create_postgresql_tables(target_url):
    """Create tables in PostgreSQL using SQLAlchemy models."""
    try:
        from sqlalchemy import create_engine
        from database import Base, init_db
        import os
        from dotenv import load_dotenv

        load_dotenv()

        original_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = target_url

        engine = create_engine(target_url)

        logger.info("Creating tables in PostgreSQL...")
        Base.metadata.create_all(engine)

        logger.info("Tables created successfully!")

        if original_url:
            os.environ["DATABASE_URL"] = original_url
        else:
            os.environ.pop("DATABASE_URL", None)

        engine.dispose()
        return True

    except Exception as e:
        logger.error(f"Error creating PostgreSQL tables: {e}")
        return False


def migrate_data(data, target_url):
    """Migrate data from SQLite to PostgreSQL."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models import (
            User,
            Session as SessionModel,
            Paper,
            Analysis,
            Summary,
            Synthesis,
            Citation,
            Note,
            Conflict,
            ScheduledDigest,
            DigestRun,
            Roadmap,
        )

        engine = create_engine(target_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        model_mapping = {
            "users": User,
            "sessions": SessionModel,
            "papers": Paper,
            "analyses": Analysis,
            "summaries": Summary,
            "syntheses": Synthesis,
            "citations": Citation,
            "notes": Note,
            "conflicts": Conflict,
            "scheduled_digests": ScheduledDigest,
            "digest_runs": DigestRun,
            "roadmaps": Roadmap,
        }

        for table_name, rows in data.items():
            if table_name not in model_mapping:
                logger.warning(f"No model for table: {table_name}, skipping...")
                continue

            model = model_mapping[table_name]
            logger.info(f"Migrating {table_name}...")

            for row_data in rows["rows"]:
                try:
                    obj = model(**row_data)
                    session.add(obj)
                except Exception as e:
                    logger.warning(f"Error adding row: {e}")

            session.commit()
            logger.info(f"  - Migrated {len(rows['rows'])} rows")

        session.close()
        engine.dispose()
        return True

    except Exception as e:
        logger.error(f"Error migrating data: {e}")
        return False


def main():
    args = parse_args()

    import os
    from dotenv import load_dotenv

    load_dotenv()

    target_url = (
        args.target
        or os.environ.get("SUPABASE_DB_URL")
        or os.environ.get("DATABASE_URL")
    )

    if not target_url:
        logger.error(
            "No target database URL provided. Use --target or set SUPABASE_DB_URL"
        )
        print(__doc__)
        sys.exit(1)

    if "sqlite" in target_url.lower():
        logger.error(
            "Target URL appears to be SQLite. Please provide a PostgreSQL URL."
        )
        sys.exit(1)

    logger.info(f"Source database: {args.source}")
    logger.info(f"Target database: {target_url[:50]}...")

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    logger.info("\n" + "=" * 50)
    logger.info("STEP 1: Exporting data from SQLite...")
    logger.info("=" * 50)

    data = export_sqlite_data(args.source)
    if not data:
        logger.error("Failed to export SQLite data")
        sys.exit(1)

    logger.info(f"\nTotal tables: {len(data)}")
    for table, info in data.items():
        logger.info(f"  - {table}: {len(info['rows'])} rows")

    logger.info("\n" + "=" * 50)
    logger.info("STEP 2: Creating PostgreSQL tables...")
    logger.info("=" * 50)

    if not args.dry_run:
        if not create_postgresql_tables(target_url):
            logger.error("Failed to create tables")
            sys.exit(1)
    else:
        logger.info("DRY RUN: Would create tables using SQLAlchemy models")

    logger.info("\n" + "=" * 50)
    logger.info("STEP 3: Migrating data...")
    logger.info("=" * 50)

    if not args.dry_run:
        if not migrate_data(data, target_url):
            logger.error("Failed to migrate data")
            sys.exit(1)
    else:
        logger.info("DRY RUN: Would migrate data")

    logger.info("\n" + "=" * 50)
    logger.info("MIGRATION COMPLETE!")
    logger.info("=" * 50)

    if not args.dry_run:
        logger.info("\nNext steps:")
        logger.info("1. Update your .env file to use PostgreSQL")
        logger.info("2. Restart the application")
        logger.info("3. Verify data integrity in Supabase dashboard")


if __name__ == "__main__":
    main()
