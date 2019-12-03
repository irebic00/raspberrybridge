#!/usr/bin/python

import re
import subprocess
import sys

import psycopg2

from bin.params import ParameterHandler

ph = ParameterHandler()

# Usage: ping.py [host]
if len(sys.argv) != 2:
    print("Usage: ping.py [host]")
    exit(1)

host = sys.argv[1]


class Ping:
    def __init__(self, destination, ping_time, time_to_live, bytes_rcv):
        self.destination = destination
        self.ping_time = ping_time
        self.ttl = time_to_live
        self.bytes = bytes_rcv

    def __repr__(self):
        return 'PING: {} bytes to {} in {} ms, ttl: {}' \
            .format(self.bytes, self.destination, self.ping_time, self.ttl)


# For details: http://initd.org/psycopg/docs/module.html#psycopg2.connect
def insert_into_db(ping_entry):
    with psycopg2.connect(database=ph.db_name,
                          user=ph.db_username,
                          password=ph.db_password,
                          host='0.0.0.0') as conn:
        # There is no need for transactions here, no risk of inconsistency etc
        conn.autocommit = True

        cursor = conn.cursor()

        sql_command = """
            INSERT INTO 
              pings
              (destination, bytes_received, ttl, pingtime)
            VALUES
              (%s, %s, %s, %s);
        """

        cursor.execute(sql_command, (ping_entry.destination, ping_entry.bytes, ping_entry.ttl, ping_entry.ping_time))
        cursor.close()


# Do the pings
with subprocess.Popen(['ping', host, '-c', '60'],
                      stdout=subprocess.PIPE,
                      bufsize=1,
                      universal_newlines=True) as p:
    for line in p.stdout:
        line = line.strip()
        if 'PING' not in line and 'statistics' not in line and 'transmitted' not in line and 'rtt' not in line:
            parts = re.search(r'(\d+) bytes from .* ttl=(\d+) time=(\d+\.?\d*) ms', line)
            if parts:
                bytes_received = parts.group(1)
                ttl = parts.group(2)
                time = parts.group(3)

                ping = Ping(host, time, ttl, bytes_received)
                insert_into_db(ping)
            else:
                ping = Ping(host, None, None, None)
                insert_into_db(ping)
