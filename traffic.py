#!/usr/bin/python

import re
import subprocess

import psycopg2

from bin.params import ParameterHandler

ph = ParameterHandler()


class Traffic:
    def __init__(self, timestamp, up, down):
        self.timestamp = timestamp
        self.download = down
        self.upload = up

    def __repr__(self):
        return 'TRAFFIC: {} {}Mbps {}Mbps'.format(self.timestamp, self.download, self.upload)


# For details: http://initd.org/psycopg/docs/module.html#psycopg2.connect
def insert_into_db(traffic_entry):
    with psycopg2.connect(database=ph.db_name,
                          user=ph.db_username,
                          password=ph.db_password,
                          host='0.0.0.0') as conn:
        # There is no need for transactions here, no risk of inconsistency etc
        conn.autocommit = True

        cursor = conn.cursor()

        sql_command = """
            INSERT INTO 
              traffic
              (upload, download)
            VALUES
              (%s, %s);
        """

        cursor.execute(sql_command, ('%.1f' % traffic_entry.upload, '%.1f' % traffic_entry.download))

        cursor.close()


# Do the traffics
with subprocess.Popen(['ifstat', '-i', ph.outbound_interface, '-t', '-b', '-w', '-n', '1', '60'],
                      stdout=subprocess.PIPE,
                      bufsize=1,
                      universal_newlines=True) as p:
    for line in p.stdout:
        line = line.strip()
        download = upload = None
        match_output = re.search(r'(\d\d:\d\d:\d\d)\s*(\d+\.\d+)\s*(\d+\.\d+)', ' '.join(line.split()))
        if match_output is not None:
            upload = float(match_output.group(2)) / 1000
            download = float(match_output.group(3)) / 1000

            insert_into_db(Traffic(timestamp=None, up=upload, down=download))
