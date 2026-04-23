#!/usr/bin/env python3
"""
Database setup script - initializes PostgreSQL database and creates tables
"""

import os
import sys
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load .env explicitly
load_dotenv(dotenv_path=".env")

DATABASE_URL = os.getenv("DATABASE_URL")


def parse_database_url(db_url):
    parsed = urlparse(db_url)

    return {
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname,
        "port": parsed.port,
        "database": parsed.path.lstrip("/")
    }


def create_database(db_config):
    """Create the main database"""
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            user=db_config["user"],
            password=db_config["password"],
            port=db_config["port"],
            database="postgres"
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # Check if DB exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_config["database"],)
        )

        if cursor.fetchone():
            print(f"[v0] Database '{db_config['database']}' already exists")
        else:
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(db_config["database"])
                )
            )
            print(f"[v0] Database '{db_config['database']}' created successfully")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"[v0] Error creating database: {e}")
        return False


def init_tables():
    """Initialize database tables"""
    try:
        from app.database.connection import init_db
        init_db()
        print("[v0] All tables initialized successfully")
        return True

    except Exception as e:
        print(f"[v0] Error initializing tables: {e}")
        return False


def main():
    print("[v0] Starting database setup...")

    try:
        # Debug: confirm env loaded
        print("connected")
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL not found in .env")

        db_config = parse_database_url(DATABASE_URL)

        print(f"[v0] Database config: {db_config['host']}:{db_config['port']} - {db_config['database']}")

        # Create DB
        if not create_database(db_config):
            sys.exit(1)

        # Initialize tables
        if not init_tables():
            sys.exit(1)

        print("[v0] Database setup completed successfully!")

    except Exception as e:
        print(f"[v0] Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()