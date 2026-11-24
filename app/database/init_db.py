"""Initialize the local MySQL database for the project.

Run from the project root:

    python -m app.database.init_db            # create everything that is missing
    python -m app.database.init_db --reset    # drop the database and rebuild it

Steps:
  1. Connect as the MySQL admin (root) and create the project database and the
     app user from .env. The app user may read, add, update and delete rows
     (SELECT, INSERT, UPDATE, DELETE) but can't create, alter or drop tables.
  2. Create the tables by running sql/schema.sql (as root).
  3. Insert the dummy data by running sql/seed.sql (as root).
  4. With --reset, drop the database first so everything is rebuilt from scratch.

If the database already has tables, steps 2-3 are skipped so existing data is
never overwritten. Use --reset to rebuild.

How this file is organized:
  * Settings and constants
  * Errors                   SetupError
  * Reading .env             load_settings()
  * Connecting to MySQL      connect()
  * Running SQL files        split_sql(), run_sql_file()
  * Database and app user    create_database_and_user()   (steps 1 and 4)
  * Checking for tables      has_tables()                  (decides steps 2-3)
  * Command-line entry point main()
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

from app.database.mysql import get_settings


# =============================================================================
# Settings and constants
# =============================================================================

# Where the SQL files live, relative to the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "sql"
SCHEMA_FILE = SQL_DIR / "schema.sql"
SEED_FILE = SQL_DIR / "seed.sql"

# The app user is created for both host names, because depending on the MySQL
# configuration a connection to 127.0.0.1 is seen as either one.
APP_USER_HOSTS = ("localhost", "127.0.0.1")

# What the app user may do in the project database: work with rows, but not
# change the schema (no CREATE, ALTER or DROP). Schema and dummy data are
# loaded as root instead.
APP_USER_PRIVILEGES = "SELECT, INSERT, UPDATE, DELETE"

# Statements in the SQL files that would conflict with the database this
# script manages. They are skipped with a note.
MANAGED_STATEMENT = re.compile(
    r"^\s*(USE\s|CREATE\s+(DATABASE|SCHEMA)\s|DROP\s+(DATABASE|SCHEMA)\s)",
    re.IGNORECASE,
)


# =============================================================================
# Errors
# =============================================================================

class SetupError(Exception):
    """A problem the user can fix; printed without a traceback."""


# =============================================================================
# Reading .env
# =============================================================================

def load_settings() -> dict:
    """Read the connection settings from .env and check they are usable.

    The app's settings come from get_settings() (shared with the API); the
    admin login is added here. Returns a dict with host, port, user, password,
    database, root_user, root_password and app_is_root. Raises SetupError if
    .env is missing or a value is missing, empty or unsafe.
    """
    # Load .env into the environment.
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        raise SetupError(
            "No .env file found. Copy .env.example to .env and fill it in."
        )
    load_dotenv(env_file)

    # The app's settings (same as the API uses), plus the admin login.
    try:
        settings = get_settings()
    except KeyError as exc:
        raise SetupError(f"Set {exc.args[0]} in your .env file.") from exc
    except ValueError as exc:
        raise SetupError("MYSQL_PORT in .env must be a number.") from exc
    settings["root_user"] = os.getenv("MYSQL_ROOT_USER", "root")
    settings["root_password"] = os.getenv("MYSQL_ROOT_PASSWORD", "")

    # If the app logs in as the admin user itself, there is no separate app
    # user to create, and a blank password is fine (XAMPP's root has none).
    settings["app_is_root"] = settings["user"] == settings["root_user"]
    if settings["app_is_root"]:
        settings["password"] = settings["root_password"]

    # Make sure the required values are filled in.
    required = [("MYSQL_USER", "user"), ("MYSQL_DATABASE", "database")]
    if not settings["app_is_root"]:
        required.append(("MYSQL_PASSWORD", "password"))
    missing = [name for name, key in required if not settings[key]]
    if missing:
        raise SetupError(f"Set {', '.join(missing)} in your .env file.")

    # Database names can't be passed as query parameters, so only allow safe names.
    if not re.fullmatch(r"[A-Za-z0-9_]+", settings["database"]):
        raise SetupError(
            "MYSQL_DATABASE may only contain letters, numbers and underscores."
        )
    return settings


# =============================================================================
# Connecting to MySQL
# =============================================================================

def connect(settings: dict, *, as_root: bool, database: str | None = None):
    """Open a MySQL connection as root (as_root=True) or as the app user.

    Pass database to select it on connect. Common failures (MySQL not running,
    wrong password) are turned into SetupError with a hint on how to fix them.
    """
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
        # MySQL isn't running or can't be reached.
        if exc.errno in (errorcode.CR_CONNECTION_ERROR, errorcode.CR_CONN_HOST_ERROR):
            raise SetupError(
                f"Can't reach MySQL at {settings['host']}:{settings['port']}. "
                "Is MySQL started in the XAMPP Control Panel?"
            ) from exc
        # Wrong username or password.
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
        # Anything else is unexpected: show the full error.
        raise


# =============================================================================
# Running SQL files
# =============================================================================

def split_sql(script: str) -> list[str]:
    """Split a SQL script into statements.

    Statements end at a semicolon. Semicolons inside quotes and comments are
    ignored. A line like `DELIMITER //` switches the terminator (as in the mysql
    client and MySQL Workbench), so trigger bodies can contain semicolons;
    `DELIMITER ;` switches back.
    """
    statements = []  # finished statements
    current = []     # characters of the statement being read
    i = 0            # position in the script
    length = len(script)
    quote = None     # the quote character we're inside, if any
    delimiter = ";"  # what ends a statement right now
    delimiter_line = re.compile(r"DELIMITER[ \t]+(\S+)[^\n]*", re.IGNORECASE)

    while i < length:
        char = script[i]
        nxt = script[i + 1] if i + 1 < length else ""

        # Inside a quoted string or name: copy characters until it closes.
        if quote:
            current.append(char)
            if char == "\\" and quote != "`":  # backslash escape, e.g. \'
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

        # Between statements: a DELIMITER line changes the terminator.
        if not "".join(current).strip():
            match = delimiter_line.match(script, i)
            if match and (i == 0 or script[i - 1] == "\n"):
                delimiter = match.group(1)
                i = match.end()
                current = []
                continue

        # The terminator ends the current statement.
        if script.startswith(delimiter, i):
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += len(delimiter)
            continue

        if char in ("'", '"', "`"):
            # Start of a quoted string or name.
            quote = char
            current.append(char)
        elif char == "#" or (char == "-" and nxt == "-"):
            # Line comment (# or --): skip to the end of the line.
            end = script.find("\n", i)
            i = length if end == -1 else end
            continue
        elif char == "/" and nxt == "*":
            # Block comment /* ... */: skip past it.
            end = script.find("*/", i + 2)
            i = length if end == -1 else end + 2
            continue
        else:
            # Ordinary character: part of the statement.
            current.append(char)
        i += 1

    # The last statement doesn't need a terminator.
    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


def run_sql_file(connection, path: Path) -> int:
    """Run every statement in a SQL file and commit; return how many ran.

    A missing file is skipped. Statements that would switch or create
    databases are skipped (see MANAGED_STATEMENT). If a statement fails, the
    file's changes are rolled back and SetupError says which statement failed.
    """
    if not path.exists():
        print(f"  {path.relative_to(PROJECT_ROOT)} not found, skipping.")
        return 0

    statements = split_sql(path.read_text(encoding="utf-8-sig"))
    cursor = connection.cursor()
    count = 0
    try:
        for number, statement in enumerate(statements, start=1):
            # Skip USE / CREATE DATABASE / DROP DATABASE.
            if MANAGED_STATEMENT.match(statement):
                first_line = statement.splitlines()[0]
                print(f"  Skipping '{first_line}' (the script manages the database).")
                continue
            try:
                cursor.execute(statement)
                if cursor.with_rows:  # read any result so the next statement can run
                    cursor.fetchall()
            except mysql.connector.Error as exc:
                # Undo this file's inserts and report the failing statement.
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


# =============================================================================
# Database and app user (steps 1 and 4)
# =============================================================================

def create_database_and_user(settings: dict, *, reset: bool) -> None:
    """As root, create the project database and the app user.

    With reset=True the database is dropped first (step 4). The app user gets
    only APP_USER_PRIVILEGES on the project database. If MYSQL_USER is root
    itself, no app user is created.
    """
    database = settings["database"]
    connection = connect(settings, as_root=True)
    cursor = connection.cursor()
    try:
        # Step 4: start over.
        if reset:
            print(f"Dropping database '{database}'...")
            cursor.execute(f"DROP DATABASE IF EXISTS `{database}`")

        # Step 1a: the database.
        print(f"Creating database '{database}' (if needed)...")
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )

        # The app logs in as root: nothing more to set up.
        if settings["app_is_root"]:
            print(
                f"Note: MYSQL_USER is the admin user '{settings['user']}', so no app "
                "user is created.\n  The app will be able to drop and alter tables. "
                "Use a separate MYSQL_USER to prevent that."
            )
            return

        # Step 1b: the app user and its permissions.
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
    finally:
        cursor.close()
        connection.close()


# =============================================================================
# Checking for tables (decides whether steps 2-3 run)
# =============================================================================

def has_tables(connection) -> bool:
    """Return True if the connected database already contains any tables."""
    cursor = connection.cursor()
    try:
        cursor.execute("SHOW TABLES")
        return bool(cursor.fetchall())
    finally:
        cursor.close()


# =============================================================================
# Command-line entry point
# =============================================================================

def main(argv: list[str] | None = None) -> int:
    """Run the setup steps; return 0 on success and 1 on a fixable error."""
    # Command-line options: --reset and --yes.
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

        # Confirm before deleting everything.
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


# Run main() when started with `python -m app.database.init_db`.
if __name__ == "__main__":
    sys.exit(main())
