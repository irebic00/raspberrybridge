sudo -u postgres psql

CREATE ROLE {db_username} WITH LOGIN PASSWORD {db_password};
CREATE DATABASE {db_name} WITH OWNER {db_username};