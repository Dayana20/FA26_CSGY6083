"""MySQL settings and connection helper, shared by the API and the setup script."""

import os

import mysql.connector


def get_settings() -> dict:
    """Read the app's MySQL connection settings from the environment (.env).

    MYSQL_HOST and MYSQL_PORT default to XAMPP's 127.0.0.1:3306. MYSQL_USER,
    MYSQL_PASSWORD and MYSQL_DATABASE are required: a KeyError is raised if
    one is missing, and a ValueError if MYSQL_PORT isn't a number. The keys
    match mysql.connector.connect()'s arguments.
    """
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
        "database": os.environ["MYSQL_DATABASE"],
    }


def get_connection():
    """Open a new MySQL connection using the settings from get_settings().

    The caller is responsible for closing the connection, e.g. with a `with`
    block.
    """
    return mysql.connector.connect(**get_settings())
