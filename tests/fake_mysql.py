"""In-memory fake MySQL connection/cursor harness supporting prepared statements and transactions."""

from copy import deepcopy
from typing import Any


class FakePreparedCursor:
    def __init__(self, connection: "FakeMySQLConnection", prepared: bool = False) -> None:
        self._connection = connection
        self.prepared = prepared
        self.lastrowid: int | None = None
        self._rows: list[tuple[Any, ...]] = []
        self.closed = False

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        if not self.prepared:
            raise AssertionError("Expected cursor(prepared=True) for application queries.")

        normalized_sql = " ".join(sql.split()).upper()
        self._connection.db.executed_queries.append((sql, params, self.prepared))

        working_customers = self._connection._tx_customers
        working_users = self._connection._tx_users

        if normalized_sql == "SELECT USER_ID FROM ADH_USER WHERE EMAIL = %S":
            assert params is not None and len(params) == 1
            email = params[0]
            matches = [
                (user["USER_ID"],)
                for user in working_users.values()
                if user["EMAIL"] == email
            ]
            self._rows = matches
            return

        if normalized_sql.startswith(
            "INSERT INTO ADH_CUSTOMER (FIRST_NAME, LAST_NAME, PHONE, ADDRESS) VALUES (%S, %S, %S, %S)"
        ):
            assert params is not None and len(params) == 4
            customer_id = self._connection._next_customer_id
            self._connection._next_customer_id += 1
            working_customers[customer_id] = {
                "CUSTOMER_ID": customer_id,
                "FIRST_NAME": params[0],
                "LAST_NAME": params[1],
                "PHONE": params[2],
                "ADDRESS": params[3],
            }
            self.lastrowid = customer_id
            self._rows = []
            return

        if normalized_sql.startswith(
            "INSERT INTO ADH_USER (EMAIL, PASSWORD_HASH, ROLE, CUSTOMER_ID) VALUES (%S, %S, %S, %S)"
        ):
            assert params is not None and len(params) == 4
            email, password_hash, role, customer_id = params
            if any(u["EMAIL"] == email for u in working_users.values()):
                import mysql.connector

                raise mysql.connector.IntegrityError(
                    msg="Duplicate entry", errno=1062
                )
            user_id = self._connection._next_user_id
            self._connection._next_user_id += 1
            working_users[user_id] = {
                "USER_ID": user_id,
                "EMAIL": email,
                "PASSWORD_HASH": password_hash,
                "ROLE": role,
                "CUSTOMER_ID": customer_id,
            }
            self.lastrowid = user_id
            self._rows = []
            return

        if "FROM ADH_USER U LEFT JOIN ADH_CUSTOMER C ON U.CUSTOMER_ID = C.CUSTOMER_ID WHERE U.EMAIL = %S" in normalized_sql:
            assert params is not None and len(params) == 1
            email = params[0]
            matches = []
            for user in working_users.values():
                if user["EMAIL"] == email:
                    cust = (
                        working_customers.get(user["CUSTOMER_ID"])
                        if user["CUSTOMER_ID"] is not None
                        else None
                    )
                    matches.append(
                        (
                            user["USER_ID"],
                            user["EMAIL"],
                            user["PASSWORD_HASH"],
                            user["ROLE"],
                            user["CUSTOMER_ID"],
                            cust["FIRST_NAME"] if cust else None,
                            cust["LAST_NAME"] if cust else None,
                            cust["PHONE"] if cust else None,
                            cust["ADDRESS"] if cust else None,
                        )
                    )
            self._rows = matches
            return

        if "FROM ADH_USER U LEFT JOIN ADH_CUSTOMER C ON U.CUSTOMER_ID = C.CUSTOMER_ID WHERE U.USER_ID = %S" in normalized_sql:
            assert params is not None and len(params) == 1
            user = working_users.get(int(params[0]))
            if user is None:
                self._rows = []
            else:
                cust = (
                    working_customers.get(user["CUSTOMER_ID"])
                    if user["CUSTOMER_ID"] is not None
                    else None
                )
                self._rows = [
                    (
                        user["USER_ID"],
                        user["EMAIL"],
                        user["ROLE"],
                        user["CUSTOMER_ID"],
                        cust["FIRST_NAME"] if cust else None,
                        cust["LAST_NAME"] if cust else None,
                        cust["PHONE"] if cust else None,
                        cust["ADDRESS"] if cust else None,
                    )
                ]
            return

        raise AssertionError(f"Unexpected SQL executed in fake DB: {sql}")

    def fetchone(self) -> tuple[Any, ...] | None:
        if not self._rows:
            return None
        return self._rows.pop(0)

    def fetchall(self) -> list[tuple[Any, ...]]:
        rows = list(self._rows)
        self._rows.clear()
        return rows

    def close(self) -> None:
        self.closed = True


class FakeMySQLConnection:
    def __init__(self, db: "FakeAuthDatabase") -> None:
        self.db = db
        self.autocommit = True
        self.closed = False
        self._tx_customers = deepcopy(db.customers)
        self._tx_users = deepcopy(db.users)
        self._next_customer_id = db.next_customer_id
        self._next_user_id = db.next_user_id

    def cursor(self, prepared: bool = False) -> FakePreparedCursor:
        return FakePreparedCursor(self, prepared=prepared)

    def commit(self) -> None:
        self.db.customers = deepcopy(self._tx_customers)
        self.db.users = deepcopy(self._tx_users)
        self.db.next_customer_id = self._next_customer_id
        self.db.next_user_id = self._next_user_id
        self.db.commits += 1

    def rollback(self) -> None:
        self._tx_customers = deepcopy(self.db.customers)
        self._tx_users = deepcopy(self.db.users)
        self._next_customer_id = self.db.next_customer_id
        self._next_user_id = self.db.next_user_id
        self.db.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class FakeAuthDatabase:
    def __init__(self) -> None:
        self.customers: dict[int, dict[str, Any]] = {}
        self.users: dict[int, dict[str, Any]] = {}
        self.next_customer_id = 1
        self.next_user_id = 1
        self.commits = 0
        self.rollbacks = 0
        self.executed_queries: list[tuple[str, tuple[Any, ...] | None, bool]] = []

    def connect(self) -> FakeMySQLConnection:
        return FakeMySQLConnection(self)

    def seed_customer(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        address: str,
        password_hash: str,
    ) -> tuple[int, int]:
        customer_id = self.next_customer_id
        self.next_customer_id += 1
        self.customers[customer_id] = {
            "CUSTOMER_ID": customer_id,
            "FIRST_NAME": first_name,
            "LAST_NAME": last_name,
            "PHONE": phone,
            "ADDRESS": address,
        }
        user_id = self.next_user_id
        self.next_user_id += 1
        self.users[user_id] = {
            "USER_ID": user_id,
            "EMAIL": email.strip().lower(),
            "PASSWORD_HASH": password_hash,
            "ROLE": "C",
            "CUSTOMER_ID": customer_id,
        }
        return customer_id, user_id

    def seed_employee(self, *, email: str, password_hash: str) -> int:
        user_id = self.next_user_id
        self.next_user_id += 1
        self.users[user_id] = {
            "USER_ID": user_id,
            "EMAIL": email.strip().lower(),
            "PASSWORD_HASH": password_hash,
            "ROLE": "E",
            "CUSTOMER_ID": None,
        }
        return user_id
