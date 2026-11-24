# CSGY6083 Project

## Team Members

- `da2410`
- `hc4288`
- `as23663`

## Local MySQL Setup

1. Start the MySQL server in XAMPP.
2. Connect to the local server with MySQL Workbench.
3. Create the project database and a local user:

   ```sql
   CREATE DATABASE IF NOT EXISTS da2410hc4288as23663;
   CREATE USER IF NOT EXISTS 'username'@'localhost' IDENTIFIED BY 'password';
   GRANT ALL PRIVILEGES ON da2410hc4288as23663.* TO 'username'@'localhost';
   FLUSH PRIVILEGES;
   ```

4. Create a `.env` file in the project root using `.env.example` as a template. Set
   `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, and a strong random
   `SESSION_SECRET_KEY`. The default local connection uses `127.0.0.1:3306`.

5. Initialize the authentication tables (`ADH_CUSTOMER` and `ADH_USER`) safely after
   configuring `.env` and starting your local MySQL server:

   ```bash
   python scripts/init_auth_schema.py
   ```

   You can also inspect or run the non-destructive SQL script directly in MySQL Workbench:
   `sql/001_create_auth_tables.sql`.

## Run the API

Create and activate a project virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Start the development server from the project root:

```bash
uvicorn main:app --reload
```

## Run Tests

```bash
pytest -v
```

## API Endpoints

- Home page: <http://127.0.0.1:8000/>
- Registration: <http://127.0.0.1:8000/register>
- Login: <http://127.0.0.1:8000/login>
- Customer Account (Role `C`): <http://127.0.0.1:8000/account>
- Employee Portal (Role `E`): <http://127.0.0.1:8000/employee>
- Interactive API documentation: <http://127.0.0.1:8000/docs>
