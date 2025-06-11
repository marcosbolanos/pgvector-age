### Manual installation

The `csv-loader.py` file contains code that loads the files into an Apache AGE graph. The extension must be installed inside of Postgresql 16, by following [these instructions](https://age.apache.org/getstarted/quickstart). You then create a database named `fpkg0_1` : 

`psql`

`CREATE DATABASE fpkg0_1`

The extension has to be loaded once inside the database :

`psql fpkg0_1`

`CREATE EXTENSION age`

Afterwards, the database is ready to be used. You may set your Postgres login credentials in the code, or as environment variables PGUSER and PGPASSWORD.

Optionally, create a viritual environment :

`python -m venv .venv`

`source .venv/bin/activate`

Install the requirements, load the cs_loader and enjoy !

`pip install -r requirements.txt`

`python csv_loader.py`
