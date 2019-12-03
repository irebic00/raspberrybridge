WiFi extender where raspberry pi is receiving WiFi signal and sharing it to eth interface which will pass it to router
Raspberry wlan0 to eth0 extender

Advice: install pgadmin3 for following steps or do it from terminal.

sudo -u postgres psql

CREATE ROLE pi WITH LOGIN PASSWORD 'Internet';
Important note! Make sure that the role in PostgreSQL has the same name as your Linux username, in this case 'pi'.
You might also want to substitute a better password.

Create a database:

CREATE DATABASE pi WITH OWNER pi;
