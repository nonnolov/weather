#!/usr/bin/env python
"""
Wait for PostgreSQL to accept connections.
Used by the GitLab CI integrate job before running Alembic migrations.
Exits 0 when the database is ready, exits 1 after 30 attempts (60 seconds).
"""
import os
import sys
import time

import psycopg2

HOST = os.environ.get("PGHOST", "postgres")
DB = os.environ.get("PGDATABASE", "weather_test")
USER = os.environ.get("PGUSER", "weather")
PASSWORD = os.environ.get("PGPASSWORD", "weather")
MAX_ATTEMPTS = 30
SLEEP_SECONDS = 2

print(f"Waiting for PostgreSQL at {HOST}/{DB} ...", flush=True)
for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        conn = psycopg2.connect(
            host=HOST, dbname=DB, user=USER, password=PASSWORD, connect_timeout=3
        )
        conn.close()
        print(f"PostgreSQL ready after {attempt} attempt(s).", flush=True)
        sys.exit(0)
    except psycopg2.OperationalError as exc:
        print(f"  attempt {attempt}/{MAX_ATTEMPTS}: {exc}", flush=True)
        time.sleep(SLEEP_SECONDS)

print("ERROR: PostgreSQL did not become ready in time.", flush=True)
sys.exit(1)
