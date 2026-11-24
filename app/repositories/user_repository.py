"""User and customer database repository using MySQL prepared statements."""

from dataclasses import dataclass

import mysql.connector

from app.core.security import normalize_email
from app.database.session import db_cursor, db_transaction, decode_db_value

MYSQL_DUPLICATE_ENTRY_ERRNO = 1062


class DuplicateEmailError(Exception):
    """Raised when attempting to create an ADH_USER with an existing email."""


@dataclass(frozen=True)
class AuthenticatedUser:
    """Safe user representation exposed to routes/templates (never stores password_hash)."""

    user_id: int
    email: str
    role: str
    customer_id: int | None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    address: str | None = None

    @property
    def is_customer(self) -> bool:
        return self.role == "C"

    @property
    def is_employee(self) -> bool:
        return self.role == "E"

    @property
    def display_name(self) -> str:
        full_name = " ".join(
            part for part in (self.first_name, self.last_name) if part
        ).strip()
        return full_name or self.email


@dataclass(frozen=True)
class UserRecord:
    """Internal auth record containing bcrypt password hash for login verification."""

    user: AuthenticatedUser
    password_hash: str


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    return str(decode_db_value(value))


def get_user_by_email(email: str) -> UserRecord | None:
    """Look up a user and optional customer profile by email using a prepared query."""
    clean_email = normalize_email(email)
    sql = """
        SELECT
            u.USER_ID,
            u.EMAIL,
            u.PASSWORD_HASH,
            u.ROLE,
            u.CUSTOMER_ID,
            c.FIRST_NAME,
            c.LAST_NAME,
            c.PHONE,
            c.ADDRESS
        FROM ADH_USER u
        LEFT JOIN ADH_CUSTOMER c ON u.CUSTOMER_ID = c.CUSTOMER_ID
        WHERE u.EMAIL = %s
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (clean_email,))
        row = cursor.fetchone()

    if row is None:
        return None

    user = AuthenticatedUser(
        user_id=int(row[0]),
        email=str(decode_db_value(row[1])),
        role=str(decode_db_value(row[3])).upper(),
        customer_id=int(row[4]) if row[4] is not None else None,
        first_name=_opt_str(row[5]),
        last_name=_opt_str(row[6]),
        phone=_opt_str(row[7]),
        address=_opt_str(row[8]),
    )
    return UserRecord(user=user, password_hash=str(decode_db_value(row[2])))


def get_user_by_id(user_id: int) -> AuthenticatedUser | None:
    """Look up a non-sensitive user profile by USER_ID using a prepared query."""
    sql = """
        SELECT
            u.USER_ID,
            u.EMAIL,
            u.ROLE,
            u.CUSTOMER_ID,
            c.FIRST_NAME,
            c.LAST_NAME,
            c.PHONE,
            c.ADDRESS
        FROM ADH_USER u
        LEFT JOIN ADH_CUSTOMER c ON u.CUSTOMER_ID = c.CUSTOMER_ID
        WHERE u.USER_ID = %s
    """
    with db_cursor() as cursor:
        cursor.execute(sql, (int(user_id),))
        row = cursor.fetchone()

    if row is None:
        return None

    return AuthenticatedUser(
        user_id=int(row[0]),
        email=str(decode_db_value(row[1])),
        role=str(decode_db_value(row[2])).upper(),
        customer_id=int(row[3]) if row[3] is not None else None,
        first_name=_opt_str(row[4]),
        last_name=_opt_str(row[5]),
        phone=_opt_str(row[6]),
        address=_opt_str(row[7]),
    )


def register_customer(
    *,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    address: str,
    password_hash: str,
) -> AuthenticatedUser:
    """Create ADH_CUSTOMER and ADH_USER (role 'C') atomically in one transaction."""
    clean_email = normalize_email(email)

    check_email_sql = "SELECT USER_ID FROM ADH_USER WHERE EMAIL = %s"
    insert_customer_sql = """
        INSERT INTO ADH_CUSTOMER (FIRST_NAME, LAST_NAME, PHONE, ADDRESS)
        VALUES (%s, %s, %s, %s)
    """
    insert_user_sql = """
        INSERT INTO ADH_USER (EMAIL, PASSWORD_HASH, ROLE, CUSTOMER_ID)
        VALUES (%s, %s, %s, %s)
    """

    try:
        with db_transaction() as cursor:
            cursor.execute(check_email_sql, (clean_email,))
            if cursor.fetchone() is not None:
                raise DuplicateEmailError("An account with this email already exists.")

            cursor.execute(
                insert_customer_sql,
                (first_name, last_name, phone, address),
            )
            customer_id = int(cursor.lastrowid)

            cursor.execute(
                insert_user_sql,
                (clean_email, password_hash, "C", customer_id),
            )
            user_id = int(cursor.lastrowid)
    except mysql.connector.IntegrityError as exc:
        if getattr(exc, "errno", None) == MYSQL_DUPLICATE_ENTRY_ERRNO:
            raise DuplicateEmailError(
                "An account with this email already exists."
            ) from exc
        raise

    return AuthenticatedUser(
        user_id=user_id,
        email=clean_email,
        role="C",
        customer_id=customer_id,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        address=address,
    )


def create_employee(*, email: str, password_hash: str) -> AuthenticatedUser:
    """Create an Employee ADH_USER (role 'E', CUSTOMER_ID NULL) in a transaction."""
    clean_email = normalize_email(email)
    check_email_sql = "SELECT USER_ID FROM ADH_USER WHERE EMAIL = %s"
    insert_user_sql = """
        INSERT INTO ADH_USER (EMAIL, PASSWORD_HASH, ROLE, CUSTOMER_ID)
        VALUES (%s, %s, %s, %s)
    """
    try:
        with db_transaction() as cursor:
            cursor.execute(check_email_sql, (clean_email,))
            if cursor.fetchone() is not None:
                raise DuplicateEmailError("An account with this email already exists.")

            cursor.execute(
                insert_user_sql,
                (clean_email, password_hash, "E", None),
            )
            user_id = int(cursor.lastrowid)
    except mysql.connector.IntegrityError as exc:
        if getattr(exc, "errno", None) == MYSQL_DUPLICATE_ENTRY_ERRNO:
            raise DuplicateEmailError(
                "An account with this email already exists."
            ) from exc
        raise

    return AuthenticatedUser(
        user_id=user_id,
        email=clean_email,
        role="E",
        customer_id=None,
    )
