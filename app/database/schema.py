"""Non-destructive schema inspection and safe initialization for auth tables."""

from dataclasses import dataclass, field
from typing import Any

from app.database.mysql import get_connection
from app.database.session import decode_db_value

CREATE_ADH_CUSTOMER_SQL = """
CREATE TABLE IF NOT EXISTS ADH_CUSTOMER (
    CUSTOMER_ID INT          NOT NULL AUTO_INCREMENT,
    FIRST_NAME  VARCHAR(100) NOT NULL,
    LAST_NAME   VARCHAR(100) NOT NULL,
    PHONE       VARCHAR(30)  NOT NULL,
    ADDRESS     VARCHAR(255) NOT NULL,
    CREATED_AT  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (CUSTOMER_ID)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
""".strip()

CREATE_ADH_USER_SQL = """
CREATE TABLE IF NOT EXISTS ADH_USER (
    USER_ID       INT          NOT NULL AUTO_INCREMENT,
    EMAIL         VARCHAR(255) NOT NULL,
    PASSWORD_HASH VARCHAR(255) NOT NULL,
    ROLE          CHAR(1)      NOT NULL,
    CUSTOMER_ID   INT          NULL,
    CREATED_DATE  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (USER_ID),
    UNIQUE KEY uq_adh_user_email (EMAIL),
    UNIQUE KEY uq_adh_user_customer_id (CUSTOMER_ID),
    CONSTRAINT chk_adh_user_role CHECK (ROLE IN ('C', 'E')),
    CONSTRAINT fk_adh_user_customer
        FOREIGN KEY (CUSTOMER_ID)
        REFERENCES ADH_CUSTOMER (CUSTOMER_ID)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
""".strip()

EXPECTED_CUSTOMER_COLUMNS = {
    "CUSTOMER_ID",
    "FIRST_NAME",
    "LAST_NAME",
    "PHONE",
    "ADDRESS",
    "CREATED_AT",
}

EXPECTED_USER_COLUMNS = {
    "USER_ID",
    "EMAIL",
    "PASSWORD_HASH",
    "ROLE",
    "CUSTOMER_ID",
    "CREATED_DATE",
}

INTEGER_TYPES = {"int", "integer", "bigint", "mediumint", "smallint"}


class SchemaConflictError(RuntimeError):
    """Raised when an existing table has an incompatible schema."""

    def __init__(self, conflicts: list[str]) -> None:
        self.conflicts = conflicts
        message = "Incompatible existing database schema detected:\n- " + "\n- ".join(
            conflicts
        )
        super().__init__(message)


@dataclass
class SchemaInspectionReport:
    database: str
    customer_table_exists: bool
    user_table_exists: bool
    conflicts: list[str] = field(default_factory=list)

    @property
    def is_compatible(self) -> bool:
        return len(self.conflicts) == 0


def _fetch_table_engine(cursor: Any, database: str, table_name: str) -> str | None:
    cursor.execute(
        """
        SELECT ENGINE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s AND UPPER(TABLE_NAME) = UPPER(%s)
        """,
        (database, table_name),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return str(decode_db_value(row[0]))


def _fetch_table_columns(
    cursor: Any, database: str, table_name: str
) -> dict[str, dict[str, Any]]:
    cursor.execute(
        """
        SELECT
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT,
            COLUMN_KEY,
            EXTRA
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND UPPER(TABLE_NAME) = UPPER(%s)
        """,
        (database, table_name),
    )
    columns: dict[str, dict[str, Any]] = {}
    for row in cursor.fetchall():
        col_name = str(decode_db_value(row[0])).upper()
        columns[col_name] = {
            "data_type": str(decode_db_value(row[1])).lower(),
            "is_nullable": str(decode_db_value(row[2])).upper(),
            "column_default": decode_db_value(row[3]),
            "column_key": str(decode_db_value(row[4])).upper(),
            "extra": str(decode_db_value(row[5])).lower(),
        }
    return columns


def _has_unique_constraint(
    cursor: Any, database: str, table_name: str, column_name: str
) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = %s
          AND UPPER(TABLE_NAME) = UPPER(%s)
          AND UPPER(COLUMN_NAME) = UPPER(%s)
          AND NON_UNIQUE = 0
        """,
        (database, table_name, column_name),
    )
    row = cursor.fetchone()
    return bool(row and int(row[0]) > 0)


def _has_foreign_key(
    cursor: Any,
    database: str,
    table_name: str,
    column_name: str,
    ref_table: str,
    ref_column: str,
) -> bool:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = %s
          AND UPPER(TABLE_NAME) = UPPER(%s)
          AND UPPER(COLUMN_NAME) = UPPER(%s)
          AND UPPER(REFERENCED_TABLE_NAME) = UPPER(%s)
          AND UPPER(REFERENCED_COLUMN_NAME) = UPPER(%s)
        """,
        (database, table_name, column_name, ref_table, ref_column),
    )
    row = cursor.fetchone()
    return bool(row and int(row[0]) > 0)


def _validate_customer_table(
    cursor: Any, database: str, engine: str, conflicts: list[str]
) -> None:
    if engine.upper() != "INNODB":
        conflicts.append(f"ADH_CUSTOMER uses engine '{engine}', expected 'InnoDB'.")

    columns = _fetch_table_columns(cursor, database, "ADH_CUSTOMER")
    missing = sorted(EXPECTED_CUSTOMER_COLUMNS - set(columns.keys()))
    if missing:
        conflicts.append(
            f"ADH_CUSTOMER is missing required columns: {', '.join(missing)}."
        )
        return

    pk_col = columns["CUSTOMER_ID"]
    if pk_col["column_key"] != "PRI" or pk_col["data_type"] not in INTEGER_TYPES:
        conflicts.append("ADH_CUSTOMER.CUSTOMER_ID must be an integer PRIMARY KEY.")
    if "auto_increment" not in pk_col["extra"]:
        conflicts.append("ADH_CUSTOMER.CUSTOMER_ID must be AUTO_INCREMENT.")

    for col_name, info in columns.items():
        if (
            col_name not in EXPECTED_CUSTOMER_COLUMNS
            and info["is_nullable"] == "NO"
            and info["column_default"] is None
            and "auto_increment" not in info["extra"]
        ):
            conflicts.append(
                f"ADH_CUSTOMER has unexpected NOT NULL column without default: {col_name}."
            )


def _validate_user_table(
    cursor: Any, database: str, engine: str, conflicts: list[str]
) -> None:
    if engine.upper() != "INNODB":
        conflicts.append(f"ADH_USER uses engine '{engine}', expected 'InnoDB'.")

    columns = _fetch_table_columns(cursor, database, "ADH_USER")
    missing = sorted(EXPECTED_USER_COLUMNS - set(columns.keys()))
    if missing:
        conflicts.append(f"ADH_USER is missing required columns: {', '.join(missing)}.")
        return

    pk_col = columns["USER_ID"]
    if pk_col["column_key"] != "PRI" or pk_col["data_type"] not in INTEGER_TYPES:
        conflicts.append("ADH_USER.USER_ID must be an integer PRIMARY KEY.")
    if "auto_increment" not in pk_col["extra"]:
        conflicts.append("ADH_USER.USER_ID must be AUTO_INCREMENT.")

    if columns["EMAIL"]["is_nullable"] != "NO":
        conflicts.append("ADH_USER.EMAIL must be NOT NULL.")
    if not _has_unique_constraint(cursor, database, "ADH_USER", "EMAIL"):
        conflicts.append("ADH_USER.EMAIL must have a UNIQUE constraint.")

    if columns["PASSWORD_HASH"]["is_nullable"] != "NO":
        conflicts.append("ADH_USER.PASSWORD_HASH must be NOT NULL.")

    if columns["ROLE"]["is_nullable"] != "NO":
        conflicts.append("ADH_USER.ROLE must be NOT NULL.")

    if columns["CUSTOMER_ID"]["is_nullable"] != "YES":
        conflicts.append(
            "ADH_USER.CUSTOMER_ID must be nullable to support Employee ('E') accounts."
        )
    if not _has_foreign_key(
        cursor, database, "ADH_USER", "CUSTOMER_ID", "ADH_CUSTOMER", "CUSTOMER_ID"
    ):
        conflicts.append(
            "ADH_USER.CUSTOMER_ID must have a FOREIGN KEY referencing ADH_CUSTOMER(CUSTOMER_ID)."
        )


def inspect_auth_schema(connection: Any | None = None) -> SchemaInspectionReport:
    """Inspect existing tables in the connected MySQL database without modifying anything."""
    owns_connection = connection is None
    cursor = None
    try:
        if owns_connection:
            connection = get_connection()
        cursor = connection.cursor(prepared=True)
        cursor.execute("SELECT DATABASE()")
        db_row = cursor.fetchone()
        database = str(decode_db_value(db_row[0])) if db_row and db_row[0] else ""
        if not database:
            raise RuntimeError("No MySQL database selected for schema inspection.")

        conflicts: list[str] = []
        customer_engine = _fetch_table_engine(cursor, database, "ADH_CUSTOMER")
        user_engine = _fetch_table_engine(cursor, database, "ADH_USER")

        if customer_engine is not None:
            _validate_customer_table(cursor, database, customer_engine, conflicts)
        if user_engine is not None:
            _validate_user_table(cursor, database, user_engine, conflicts)
            if customer_engine is None:
                conflicts.append(
                    "ADH_USER exists without ADH_CUSTOMER; cannot reconcile safely."
                )

        return SchemaInspectionReport(
            database=database,
            customer_table_exists=customer_engine is not None,
            user_table_exists=user_engine is not None,
            conflicts=conflicts,
        )
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            if owns_connection and connection is not None:
                connection.close()


def initialize_auth_schema(
    connection: Any | None = None,
) -> tuple[SchemaInspectionReport, list[str]]:
    """Inspect schema safely and create missing auth tables without destructive DDL."""
    owns_connection = connection is None
    ddl_cursor = None
    try:
        if owns_connection:
            connection = get_connection()

        report = inspect_auth_schema(connection=connection)
        if not report.is_compatible:
            raise SchemaConflictError(report.conflicts)

        created_tables: list[str] = []
        ddl_cursor = connection.cursor()
        if not report.customer_table_exists:
            ddl_cursor.execute(CREATE_ADH_CUSTOMER_SQL)
            created_tables.append("ADH_CUSTOMER")
        if not report.user_table_exists:
            ddl_cursor.execute(CREATE_ADH_USER_SQL)
            created_tables.append("ADH_USER")

        connection.commit()
        return report, created_tables
    finally:
        try:
            if ddl_cursor is not None:
                ddl_cursor.close()
        finally:
            if owns_connection and connection is not None:
                connection.close()
