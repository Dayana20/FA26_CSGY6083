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
   `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE` to match the MySQL user,
   password, and database you created. The default local connection uses
   `127.0.0.1:3306`.

## Run the API

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

Start the development server from the project root:

```bash
uvicorn main:app --reload
```

## API Endpoints

- Interactive API documentation: <http://127.0.0.1:8000/docs>
