# CSGY6083 Project

## Team Members

- `da2410`
- `hc4288`
- `as23663`

## Database Design

The tables, columns, relationships and rules are documented in
[`docs/database.md`](docs/database.md), including an ER diagram.

## Local Setup

You only need to do steps 1–4 once per machine. After that, start MySQL in XAMPP
and run the API (step 5).

### 1. Start MySQL

Open the XAMPP Control Panel and click **Start** next to **MySQL**. Leave it
running while you work.

### 2. Install the Python dependencies

From the project root:

```bash
pip install -r requirements.txt
```

### 3. Create your `.env` file

Copy `.env.example` to a new file named `.env` in the project root:

```bash
cp .env.example .env        # macOS / Linux / Git Bash
copy .env.example .env      # Windows Command Prompt
```

Then open `.env` and fill it in:

| Setting               | What to put                                                                 |
| --------------------- | --------------------------------------------------------------------------- |
| `MYSQL_ROOT_USER`     | `root` (XAMPP's default admin).                                             |
| `MYSQL_ROOT_PASSWORD` | Leave blank. XAMPP's root has no password unless you set one yourself.      |
| `MYSQL_USER`          | Any username you like for the app. The setup script creates it.             |
| `MYSQL_PASSWORD`      | Any password you like for that user.                                        |
| `MYSQL_DATABASE`      | Keep `da2410hc4288as23663`.                                                 |

`MYSQL_HOST` and `MYSQL_PORT` default to `127.0.0.1:3306`, which is what XAMPP
uses. `.env` is ignored by git, so your passwords stay on your machine.

### 4. Set up the database

```bash
python -m app.database.init_db
```

This connects as root and:

1. creates the database and your app user. The app user can read, add and
   update rows but can't delete them (see [Deleting Data](docs/database.md#deleting-data)),
2. creates the tables from `sql/schema.sql`,
3. loads the dummy data from `sql/seed.sql`.

It's safe to run again. If the tables already exist, it leaves them and their
data alone.

To wipe the database and rebuild it from the SQL files (for example after the
schema or dummy data changes):

```bash
python -m app.database.init_db --reset
```

It asks for confirmation first; add `--yes` to skip the prompt.

### 5. Run the API

```bash
uvicorn main:app --reload
```

Then open <http://127.0.0.1:8000/health/mysql>. You should see
`{"status": "ok", "database": "da2410hc4288as23663"}`.

## Changing the Schema or Dummy Data

- Table definitions go in `sql/schema.sql` and inserts go in `sql/seed.sql`.
- Don't include `CREATE DATABASE` or `USE` statements. The setup script
  manages the database (it skips them if they're there).
- Order matters: create and fill parent tables before the tables that reference
  them with foreign keys.
- After editing either file, run `python -m app.database.init_db --reset`.

## Troubleshooting

| Error                                    | Fix                                                                                 |
| ---------------------------------------- | ----------------------------------------------------------------------------------- |
| `Can't reach MySQL at 127.0.0.1:3306`    | Start MySQL in the XAMPP Control Panel.                                             |
| `MySQL rejected the admin login for 'root'` | You've set a root password in XAMPP. Put it in `MYSQL_ROOT_PASSWORD`.            |
| `No .env file found`                     | Do step 3.                                                                          |
| `sql/seed.sql, statement N failed: ...`  | Fix that statement (the error shows it), then run with `--reset`. A failed seed is rolled back, so no partial data is left. |

## API Endpoints

- Interactive API documentation: <http://127.0.0.1:8000/docs>
- `GET /health`: confirms the API is running.
- `GET /health/mysql`: confirms the API can reach the database.
