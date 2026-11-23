"""Initialize the local MySQL database for the project.

Run from the project root:

    python -m app.database.init_db            # create everything that is missing
    python -m app.database.init_db --reset    # drop the database and rebuild it

Steps:
  1. Connect as the MySQL admin (root) and create the project database and the
     app user from .env. The app user may only read, add and update rows
     (SELECT, INSERT, UPDATE): it can't delete rows or change the tables.
  2. Create the tables by running sql/schema.sql (as root).
  3. Insert the dummy data by running sql/seed.sql (as root).
  4. With --reset, drop the database first so everything is rebuilt from scratch.

If the database already has tables, steps 2-3 are skipped so existing data is
never overwritten. Use --reset to rebuild.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import errorcode

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "sql"
SCHEMA_FILE = SQL_DIR / "schema.sql"
SEED_FILE = SQL_DIR / "seed.sql"

# The app user is created for both host names, because depending on the MySQL
# configuration a connection to 127.0.0.1 is seen as either one.
APP_USER_HOSTS = ("localhost", "127.0.0.1")

# What the app user may do in the project database. No DELETE, so rows can't
# be deleted through the app, and no DROP/ALTER/CREATE, so it can't change the
# schema. Schema and dummy data are loaded as root instead.
APP_USER_PRIVILEGES = "SELECT, INSERT, UPDATE"

# Statements in the SQL files that would conflict with the database this
# script manages. They are skipped with a note.
MANAGED_STATEMENT = re.compile(
    r"^\s*(USE\s|CREATE\s+(DATABASE|SCHEMA)\s|DROP\s+(DATABASE|SCHEMA)\s)",
    re.IGNORECASE,
)


class SetupError(Exception):
    """A problem the user can fix; printed without a traceback."""


def load_settings() -> dict:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        raise SetupError(
            "No .env file found. Copy .env.example to .env and fill it in."
        )
    load_dotenv(env_file)

    settings = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "root_user": os.getenv("MYSQL_ROOT_USER", "root"),
        "root_password": os.getenv("MYSQL_ROOT_PASSWORD", ""),
        "user": os.getenv("MYSQL_USER", ""),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", ""),
    }

    missing = [
        name
        for name, key in (
            ("MYSQL_USER", "user"),
            ("MYSQL_PASSWORD", "password"),
            ("MYSQL_DATABASE", "database"),
        )
        if not settings[key]
    ]
    if missing:
        raise SetupError(f"Set {', '.join(missing)} in your .env file.")

    # Database names can't be passed as query parameters, so only allow safe names.
    if not re.fullmatch(r"[A-Za-z0-9_]+", settings["database"]):
        raise SetupError(
            "MYSQL_DATABASE may only contain letters, numbers and underscores."
        )
    return settings


def connect(settings: dict, *, as_root: bool, database: str | None = None):
    user = settings["root_user"] if as_root else settings["user"]
    password = settings["root_password"] if as_root else settings["password"]
    try:
        return mysql.connector.connect(
            host=settings["host"],
            port=settings["port"],
            user=user,
            password=password,
            database=database,
        )
    except mysql.connector.Error as exc:
        if exc.errno in (errorcode.CR_CONNECTION_ERROR, errorcode.CR_CONN_HOST_ERROR):
            raise SetupError(
                f"Can't reach MySQL at {settings['host']}:{settings['port']}. "
                "Is MySQL started in the XAMPP Control Panel?"
            ) from exc
        if exc.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            if as_root:
                raise SetupError(
                    f"MySQL rejected the admin login for '{user}'. If you set a "
                    "root password in XAMPP, put it in MYSQL_ROOT_PASSWORD in .env."
                ) from exc
            raise SetupError(
                f"MySQL rejected the login for '{user}'. Check MYSQL_USER and "
                "MYSQL_PASSWORD in .env."
            ) from exc
        raise


def split_sql(script: str) -> list[str]:
    """Split a SQL script into statements on semicolons.

    Semicolons inside quotes and comments are ignored. DELIMITER blocks
    (stored procedures, triggers) are not supported.
    """
    statements = []
    current = []
    i = 0
    length = len(script)
    quote = None

    while i < length:
        char = script[i]
        nxt = script[i + 1] if i + 1 < length else ""

        if quote:
            current.append(char)
            if char == "\\" and quote != "`":
                current.append(nxt)
                i += 2
                continue
            if char == quote:
                if nxt == quote:  # doubled quote inside a string
                    current.append(nxt)
                    i += 2
                    continue
                quote = None
            i += 1
            continue

        if char in ("'", '"', "`"):
            quote = char
            current.append(char)
        elif char == "#" or (char == "-" and nxt == "-"):
            end = script.find("\n", i)
            i = length if end == -1 else end
            continue
        elif char == "/" and nxt == "*":
            end = script.find("*/", i + 2)
            i = length if end == -1 else end + 2
            continue
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        i += 1

    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


def run_sql_file(connection, path: Path) -> int:
    if not path.exists():
        print(f"  {path.relative_to(PROJECT_ROOT)} not found, skipping.")
        return 0

    statements = split_sql(path.read_text(encoding="utf-8-sig"))
    cursor = connection.cursor()
    count = 0
    try:
        for number, statement in enumerate(statements, start=1):
            if MANAGED_STATEMENT.match(statement):
                first_line = statement.splitlines()[0]
                print(f"  Skipping '{first_line}' (the script manages the database).")
                continue
            try:
                cursor.execute(statement)
                if cursor.with_rows:
                    cursor.fetchall()
            except mysql.connector.Error as exc:
                connection.rollback()
                preview = " ".join(statement.split())[:200]
                raise SetupError(
                    f"{path.relative_to(PROJECT_ROOT)}, statement {number} failed: "
                    f"{exc.msg}\n    {preview}\n"
                    "Fix the file, then run again with --reset."
                ) from exc
            count += 1
        connection.commit()
    finally:
        cursor.close()
    return count


def create_database_and_user(settings: dict, *, reset: bool) -> None:
    database = settings["database"]
    connection = connect(settings, as_root=True)
    cursor = connection.cursor()
    try:
        if reset:
            print(f"Dropping database '{database}'...")
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")

        print(f"Creating database '{database}' (if needed)...")
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )

        print(f"Creating user '{settings['user']}' (if needed)...")
        for host in APP_USER_HOSTS:
            account = (settings["user"], host)
            cursor.execute(
                "CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s",
                (*account, settings["password"]),
            )
            # Keep the password in sync with .env if the user already existed.
            cursor.execute(
                "ALTER USER %s@%s IDENTIFIED BY %s",
                (*account, settings["password"]),
            )
            # Remove any broader access granted earlier (e.g. GRANT ALL from the
            # old manual setup), then grant only what the app needs.
            try:
                cursor.execute(
                    f"REVOKE ALL PRIVILEGES ON `{database}`.* FROM %s@%s", account
                )
            except mysql.connector.Error as exc:
                if exc.errno != errorcode.ER_NONEXISTING_GRANT:
                    raise
            cursor.execute(
                f"GRANT {APP_USER_PRIVILEGES} ON `{database}`.* TO %s@%s", account
            )
        cursor.execute("FLUSH PRIVILEGES")
    finally:
        cursor.close()
        connection.close()


def has_tables(connection) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute("SHOW TABLES")
        return bool(cursor.fetchall())
    finally:
        cursor.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Set up the local MySQL database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="drop the database and rebuild it from sql/schema.sql and sql/seed.sql",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="don't ask before --reset"
    )
    args = parser.parse_args(argv)

    try:
        settings = load_settings()

        if args.reset and not args.yes:
            answer = input(
                f"This deletes all data in '{settings['database']}'. Continue? [y/N] "
            )
            if answer.strip().lower() not in ("y", "yes"):
                print("Cancelled.")
                return 1

        # Step 1 (and step 4 when --reset): database and user, as root.
        create_database_and_user(settings, reset=args.reset)

        # Steps 2-3: tables and data, as root (the app user can't create tables).
        connection = connect(settings, as_root=True, database=settings["database"])
        try:
            if has_tables(connection):
                print(
                    "Tables already exist, leaving schema and data as they are. "
                    "Run with --reset to rebuild."
                )
            else:
                print("Creating tables from sql/schema.sql...")
                count = run_sql_file(connection, SCHEMA_FILE)
                print(f"  {count} statement(s) run.")
                print("Inserting dummy data from sql/seed.sql...")
                count = run_sql_file(connection, SEED_FILE)
                print(f"  {count} statement(s) run.")
        finally:
            connection.close()

        # Make sure the app can log in with the credentials in .env.
        connect(settings, as_root=False, database=settings["database"]).close()
    except SetupError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Database is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
