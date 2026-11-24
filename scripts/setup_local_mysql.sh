#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

MYSQL_BIN="/usr/local/mysql/bin/mysql"
DB_NAME="da2410hc4288as23663"
APP_USER="adh_app"

if [[ ! -x "$MYSQL_BIN" ]]; then
  MYSQL_BIN="$(command -v mysql || true)"
fi

if [[ -z "$MYSQL_BIN" || ! -x "$MYSQL_BIN" ]]; then
  echo "ERROR: MySQL client binary not found." >&2
  exit 1
fi

echo "=== ADH Cruises Local MySQL Setup & Verification ==="
echo "Project root: $PROJECT_ROOT"
echo "Git branch:   $(git branch --show-current)"
echo "MySQL client: $("$MYSQL_BIN" --version)"

if ! git check-ignore -q .env; then
  echo "ERROR: .env is not ignored by .gitignore. Aborting for safety." >&2
  exit 1
fi

# Secure temporary option file so the root password never appears in process args or logs.
ROOT_CNF="$(mktemp)"
chmod 600 "$ROOT_CNF"
cleanup() {
  rm -f "$ROOT_CNF"
}
trap cleanup EXIT

printf "Enter your local MySQL root password (input hidden): "
IFS= read -r -s ROOT_PASS
echo ""

cat > "$ROOT_CNF" <<EOF
[client]
user=root
password=${ROOT_PASS}
host=127.0.0.1
port=3306
EOF
unset ROOT_PASS

if ! "$MYSQL_BIN" --defaults-extra-file="$ROOT_CNF" -e "SELECT VERSION();" >/dev/null 2>&1; then
  # Fallback to local Unix socket if TCP root login is restricted
  cat > "$ROOT_CNF" <<EOF
[client]
user=root
socket=/tmp/mysql.sock
EOF
  echo "ERROR: Unable to authenticate to MySQL as root on 127.0.0.1:3306. Please verify your root password and try again." >&2
  exit 1
fi

echo "1. Authenticated to MySQL root successfully."

# Create independent project database (non-destructive)
"$MYSQL_BIN" --defaults-extra-file="$ROOT_CNF" <<SQL
CREATE DATABASE IF NOT EXISTS ${DB_NAME}
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
SQL
echo "2. Verified/created database '${DB_NAME}' (utf8mb4_unicode_ci)."

# Check if adh_app already exists before creating or modifying it
EXISTING_HOSTS="$("$MYSQL_BIN" --defaults-extra-file="$ROOT_CNF" -N -B -e "SELECT Host FROM mysql.user WHERE User = '${APP_USER}';")"

APP_PASSWORD=""
if [[ -n "$EXISTING_HOSTS" ]]; then
  echo "3. Existing MySQL user '${APP_USER}' detected for host(s): $(echo "$EXISTING_HOSTS" | tr '\n' ' ')"
  echo "   Preserving existing user password and unrelated database grants."
  for host in $EXISTING_HOSTS; do
    "$MYSQL_BIN" --defaults-extra-file="$ROOT_CNF" -e "SHOW GRANTS FOR '${APP_USER}'@'${host}';" >/dev/null
    "$MYSQL_BIN" --defaults-extra-file="$ROOT_CNF" -e \
      "GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER, REFERENCES ON ${DB_NAME}.* TO '${APP_USER}'@'${host}';"
  done
  "$MYSQL_BIN" --defaults-extra-file="$ROOT_CNF" -e "FLUSH PRIVILEGES;"

  if [[ -f .env ]]; then
    APP_PASSWORD="$(.venv/bin/python -c 'from dotenv import dotenv_values; print(dotenv_values(".env").get("MYSQL_PASSWORD", ""))')"
  fi
  if [[ -z "$APP_PASSWORD" ]]; then
    echo "   Existing '${APP_USER}' user has no MYSQL_PASSWORD in .env."
    printf "   Enter existing password for '${APP_USER}' (input hidden): "
    IFS= read -r -s APP_PASSWORD
    echo ""
  fi
else
  APP_PASSWORD="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(24))')"
  "$MYSQL_BIN" --defaults-extra-file="$ROOT_CNF" <<SQL
CREATE USER '${APP_USER}'@'localhost' IDENTIFIED BY '${APP_PASSWORD}';
CREATE USER '${APP_USER}'@'127.0.0.1' IDENTIFIED BY '${APP_PASSWORD}';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER, REFERENCES
  ON ${DB_NAME}.* TO '${APP_USER}'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER, REFERENCES
  ON ${DB_NAME}.* TO '${APP_USER}'@'127.0.0.1';

FLUSH PRIVILEGES;
SQL
  echo "3. Created least-privilege MySQL user '${APP_USER}' for localhost and 127.0.0.1."
fi

# Safely create or update .env preserving unrelated existing variables
APP_PASSWORD_ENV="$APP_PASSWORD" .venv/bin/python - <<'PY'
import os
import secrets
from pathlib import Path

env_path = Path(".env")
existing_lines = []
existing_map = {}

if env_path.exists():
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        existing_lines.append(raw_line)
        stripped = raw_line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, v = stripped.split("=", 1)
            existing_map[k.strip()] = v.strip()

session_secret = existing_map.get("SESSION_SECRET_KEY") or secrets.token_urlsafe(48)

desired = {
    "MYSQL_HOST": "127.0.0.1",
    "MYSQL_PORT": "3306",
    "MYSQL_USER": "adh_app",
    "MYSQL_PASSWORD": os.environ["APP_PASSWORD_ENV"],
    "MYSQL_DATABASE": "da2410hc4288as23663",
    "APP_ENV": existing_map.get("APP_ENV") or "development",
    "SESSION_SECRET_KEY": session_secret,
    "SESSION_HTTPS_ONLY": existing_map.get("SESSION_HTTPS_ONLY") or "false",
    "SESSION_MAX_AGE": existing_map.get("SESSION_MAX_AGE") or "3600",
}

updated_lines = []
seen = set()
for raw_line in existing_lines:
    stripped = raw_line.strip()
    if stripped and not stripped.startswith("#") and "=" in stripped:
        k = stripped.split("=", 1)[0].strip()
        if k in desired:
            updated_lines.append(f"{k}={desired[k]}")
            seen.add(k)
            continue
    updated_lines.append(raw_line)

for k, v in desired.items():
    if k not in seen:
        updated_lines.append(f"{k}={v}")

env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
os.chmod(env_path, 0o600)
PY
unset APP_PASSWORD

echo "4. Configured .env with chmod 600 (secrets hidden)."

echo "5. Running non-destructive schema initialization..."
.venv/bin/python scripts/init_auth_schema.py

echo "6. Verifying tables and constraints via INFORMATION_SCHEMA..."
PROJECT_ROOT="$PROJECT_ROOT" .venv/bin/python - <<'PY'
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(os.environ["PROJECT_ROOT"]).resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

env_path = project_root / ".env"
if not env_path.is_file():
    raise FileNotFoundError(f"Expected .env file not found at {env_path}")

load_dotenv(dotenv_path=env_path)
from app.database.mysql import get_connection

conn = get_connection()
cur = conn.cursor()
try:
    cur.execute("SHOW TABLES")
    print("   Tables:", [r[0] for r in cur.fetchall()])
    for tbl in ("ADH_CUSTOMER", "ADH_USER"):
        cur.execute(f"DESCRIBE {tbl}")
        print(f"   {tbl}:")
        for row in cur.fetchall():
            print("    ", row)
    cur.execute(
        """
        SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME IN ('ADH_CUSTOMER', 'ADH_USER')
        ORDER BY TABLE_NAME, CONSTRAINT_TYPE, CONSTRAINT_NAME
        """
    )
    print("   Table Constraints (PK / UNIQUE / FK / CHECK):")
    for row in cur.fetchall():
        print("    ", row)
    cur.execute(
        """
        SELECT CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME IN ('ADH_CUSTOMER', 'ADH_USER')
        ORDER BY TABLE_NAME, CONSTRAINT_NAME
        """
    )
    print("   Key/FK Column Usage:")
    for row in cur.fetchall():
        print("    ", row)
    cur.execute(
        """
        SELECT CONSTRAINT_NAME, CHECK_CLAUSE
        FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE()
        ORDER BY CONSTRAINT_NAME
        """
    )
    print("   Check Constraints (Role C/E):")
    for row in cur.fetchall():
        print("    ", row)
finally:
    cur.close()
    conn.close()
PY

echo "7. Running live MySQL & HTTP integration verification..."
.venv/bin/python scripts/verify_live_auth.py

echo "8. Running full pytest regression suite..."
.venv/bin/pytest -v

echo "=== All local setup, schema, live integration, and regression checks PASSED ==="
