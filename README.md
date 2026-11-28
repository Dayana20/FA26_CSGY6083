# CSGY6083 Project

## Team Members

- `da2410 - Dayana Alejandro`
- `hc4288 - Hoi Cheng`
- `as23663 - Ahana Shaikh`

## Architecture and Database Design

- [`docs/project_Roadmap.html`](docs/project_Roadmap.html) charts every component:
  the pages, API endpoints, database queries and tables, how they connect, who
  owns each one, and whether it's built, being revised or not built yet. Open
  it in a browser (double-click it; no server needed). To update it, edit the
  DATA section at the top of its `<script>`: one entry per box and per arrow.
- [`docs/database.md`](docs/database.md) documents the tables, columns,
  relationships and rules, including an ER diagram.

## Local Setup

You only need to do steps 1–5 once per machine. After that, each time you work
on the project: start MySQL in XAMPP, activate the virtual environment (step 3)
and run the API (step 6).

### 1. Start MySQL

Open the XAMPP Control Panel and click **Start** next to **MySQL**. Leave it
running while you work. Note the number in its **Port(s)** column, usually
`3306` but sometimes `3307` (for example when another MySQL already uses
3306). You'll need it in step 4.

MySQL Workbench is only a viewer: having it open doesn't start the MySQL
server.

### 2. Check your Python

You need the standard Python 3.10 or newer from
[python.org](https://www.python.org/downloads/), 64-bit. On Windows, list the
versions you have with:

```powershell
py --list
```

Don't use the Python that comes with MSYS2 or Cygwin (`python` pointing into a
folder like `C:\msys64\...`): pip can't install `pydantic-core`, which FastAPI
needs, on those.

### 3. Create a virtual environment and install the dependencies

A virtual environment (`.venv`) is this project's own copy of Python and its
packages. From the project root on Windows (PowerShell), using a version from
`py --list`:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Your prompt now starts with `(.venv)`. Activate it again (the second line) in
every new terminal before running the project. If PowerShell says running
scripts is disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
once, then try again. `.venv` is ignored by git.

### 4. Create your `.env` file

Copy `.env.example` to a new file named `.env` in the project root:

```bash
cp .env.example .env        # macOS / Linux / Git Bash
copy .env.example .env      # Windows (PowerShell or Command Prompt)
```

Then open `.env` and check it:

| Setting               | What to put                                                                 |
| --------------------- | --------------------------------------------------------------------------- |
| `MYSQL_HOST`          | Keep `127.0.0.1`.                                                           |
| `MYSQL_PORT`          | The MySQL port from the XAMPP Control Panel (step 1), usually `3306`.       |
| `MYSQL_ROOT_USER`     | `root` (XAMPP's default admin).                                             |
| `MYSQL_ROOT_PASSWORD` | Leave blank. XAMPP's root has no password unless you set one yourself.      |
| `MYSQL_USER`          | `root` for local demos (the team default). Or any other name, and the setup script creates that user with no permission to drop or alter tables. |
| `MYSQL_PASSWORD`      | Blank when `MYSQL_USER` is `root`, unless your root has a password: then put it here too. Otherwise any password for your user. |
| `MYSQL_DATABASE`      | Keep `da2410hc4288as23663`.                                                 |

`.env` is ignored by git, so your settings stay on your machine. If you change
`.env` while the API is running, stop it and start it again (step 6): it only
reads `.env` when it starts.

### 5. Set up the database

```bash
python -m app.database.init_db
```

This connects as root and:

1. creates the database. If `MYSQL_USER` is a separate user rather than
   `root`, it also creates that user with permission to read, add, update and
   delete rows but not to change or drop tables (see
   [Deleting Data](docs/database.md#deleting-data)),
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

### 6. Run the API

With MySQL running and the virtual environment active (`(.venv)` in your
prompt):

```bash
uvicorn main:app --reload
```

When it prints `Uvicorn running on http://127.0.0.1:8000`, open
<http://127.0.0.1:8000/health/mysql>. You should see
`{"status": "ok", "database": "da2410hc4288as23663"}`. Leave the terminal open
while you work; press **Ctrl+C** in it to stop the server.

### Viewing the pages locally

With the server running, open the pages in your browser at
<http://127.0.0.1:8000/>, for example <http://127.0.0.1:8000/book-cruise>
(see [Application Pages](#application-pages)). `--reload` restarts the server
when you save a Python file. After editing HTML, CSS or JavaScript, refresh the
page.

You can also double-click a file in `app/static/` to see its layout without the
server, but data such as the trip list won't load: pages get their data from the
API, which only answers at `http://127.0.0.1:8000`.

## Changing the Schema or Dummy Data

- Table definitions go in `sql/schema.sql` and inserts go in `sql/seed.sql`.
- Don't include `CREATE DATABASE` or `USE` statements. The setup script
  manages the database (it skips them if they're there).
- Order matters: create and fill parent tables before the tables that reference
  them with foreign keys.
- Triggers (or anything else whose body contains `;`) go between
  `DELIMITER //` and `DELIMITER ;` lines, as at the end of `sql/schema.sql`.
- After editing either file, run `python -m app.database.init_db --reset`.
- To check row counts (e.g. for screenshots), run `sql/counts.sql` in MySQL
  Workbench.

## Demo Logins

The dummy data includes login accounts. Passwords are stored as bcrypt hashes.

| Who | Username | Password |
| --- | --- | --- |
| Any adult customer | `first.last`, e.g. `maria.gonzalez`, `liam.obrien` | `CruiseDemo2026!` |
| Admin | `admin` | `AdminDemo2026!` |

These are for the local demo only. Customers under 18 have no login.

## Troubleshooting

| Error                                    | Fix                                                                                 |
| ---------------------------------------- | ----------------------------------------------------------------------------------- |
| `Failed to build 'pydantic-core'` during `pip install` | Your Python isn't the standard python.org build (e.g. it's MSYS2's). Use steps 2–3: a virtual environment made with `py`. |
| `py`, `python` or `uvicorn` "is not recognized" | Activate the virtual environment (`.venv\Scripts\activate`), or run `python -m uvicorn main:app --reload`. If `py` itself is missing, install Python from python.org. |
| `running scripts is disabled on this system` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again. |
| `Can't reach MySQL at 127.0.0.1:3306`    | Start MySQL in the XAMPP Control Panel. If it's already running, check its port there and set `MYSQL_PORT` in `.env` to match (e.g. `3307`). |
| `MySQL rejected the admin login for 'root'` | You've set a root password. Put it in `MYSQL_ROOT_PASSWORD`, and in `MYSQL_PASSWORD` too while `MYSQL_USER` is `root`. |
| `No .env file found`                     | Do step 4.                                                                          |
| `/health/mysql` says "MySQL database unavailable", or a page says "Couldn't load trips" | The API can't reach MySQL. Stop the server, run `python -m app.database.init_db` to see the exact error and fix it as above, then start the server again (it only reads `.env` when it starts). |
| `Note: MYSQL_USER is the admin user 'root'` | Expected with the team default. The app can drop and alter tables when it logs in as root. Use a separate `MYSQL_USER` if you want that blocked. |
| `sql/seed.sql, statement N failed: ...`  | Fix that statement (the error shows it), then run with `--reset`. A failed seed is rolled back, so no partial data is left. |

## API Endpoints

- Interactive API documentation: <http://127.0.0.1:8000/docs>
- `GET /health`: confirms the API is running.
- `GET /health/mysql`: confirms the API can reach the database.

### Cruise ships

| Method | Route | Description |
| --- | --- | --- |
| `POST` | `/create_cruise` | Creates a ship. JSON body: `ship_name`, `no_of_floors`; MySQL generates `ship_id`. |
| `GET` | `/get_cruises` | Returns all ships with `SHIP_ID`, `SHIP_NAME`, and `NO_OF_FLOORS`. |
| `DELETE` | `/delete_cruise/{ship_id}` | Deletes a ship by ID. A ship referenced by a trip cannot be deleted. |

### Ports

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/current_ports` | Returns all ports ordered by `PORT_ID` in a `ports` list, with `PORT_ID`, `PORT_NAME`, `STREET`, `CITY`, `STATE`, `ZIPCODE`, `COUNTRY`, `NEAREST_AIRPORT`, and `PARKING_CAPACITY`. Returns an empty list when there are no ports. |
| `POST` | `/create_port` | Creates a port and returns its generated `port_id`. JSON body requires `port_name`, `street`, `city`, `country`, and `nearest_airport`; `port_name` cannot be blank. `state`, `zipcode`, and `parking_capacity` are optional. If provided, `state` must be two uppercase letters, `zipcode` a five-digit string, and `parking_capacity` an integer from 0 to 999. |
| `DELETE` | `/delete_port/{port_id}` | Deletes a port by ID. Returns 404 if it does not exist; a port referenced by a trip stop cannot be deleted (409). |

### Port stops

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/current_port_stops` | Returns all port stops in a `port_stops` list, ordered by `TRIP_ID` and `STOP_NO`, with `STOP_NO`, `PSTART_DATE`, `PEND_DATE`, `TRIP_ID`, and `PORT_ID`. Returns an empty list when there are no stops. |
| `POST` | `/create_port_stop` | Creates a stop. JSON body requires `stop_no`, `pstart_date`, `pend_date`, `trip_id`, and `port_id`; the trip and port must exist, and the stop number must be unique within the trip. Dates must have no time zone or fractional seconds, and departure must be on or after arrival. Returns `trip_id` and `stop_no`. |
| `DELETE` | `/delete_port_stop/{trip_id}/{stop_no}` | Deletes the stop identified by its trip ID and stop number. Returns 404 if it does not exist. |

### Trips

| Method | Route | Description |
| --- | --- | --- |
| `POST` | `/create_trip` | Creates a trip. JSON body: `start_date`, `end_date`, `ship_id`; MySQL generates `trip_id`. The end date must be after the start date, and the ship must exist. |
| `GET` | `/current_trips` | Returns all trips with `TRIP_ID`, `START_DATE`, `END_DATE`, and `SHIP_ID`. |
| `GET` | `/available_trips` | Returns trips starting today or later, soonest first, each with `TRIP_ID`, `START_DATE`, `END_DATE`, `NIGHTS`, `SHIP_ID`, `SHIP_NAME` and `PORT_STOPS` (in order, with port name, city, country, arrival and departure). Returns an empty list when nothing is scheduled. Used by the Book a cruise page. |
| `DELETE` | `/delete_trip/{trip_id}` | Deletes a trip by ID. |


## Application Pages

| Route | Page |
| --- | --- |
| `/` | Public home page |
| `/book-cruise` | Public list of upcoming trips (booking not built yet) |
| `/dashboard` | Regular-user dashboard |
| `/admin/dashboard` | Admin dashboard |
| `/admin/cruise-trips` | Admin cruise-trip management prototype |
