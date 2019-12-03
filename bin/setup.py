#!/usr/bin/python
import subprocess

from crontab import CronTab

import logger
from params import ParameterHandler

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

ph = ParameterHandler()
cron = CronTab(user=ph.db_username)


cron_templates = [
    '1m|sudo python' + ph.python_version + ' ' + ph.project_path + '/bin/startup.py',
    '1m|python' + ph.python_version + ' ' + ph.project_path + '/ping.py www.amazon.de',
    '1m|python' + ph.python_version + ' ' + ph.project_path + '/traffic.py',
    '3h|psql --command="delete from traffic where traffic.recorded_at < now() - interval \'3 hours\';"',
    '3h|psql --command="delete from pings where pings.recorded_at < now() - interval \'3 hours\';"',
    'd4|sudo reboot']


def add_crontabs():
    existing_cron_commands = [c.command for c in cron.crons]
    for cron_template in cron_templates:
        cron_parts = cron_template.split('|')
        cron_to_add = None
        if cron_parts[1] not in existing_cron_commands:
            if 'm' in cron_parts[0]:
                cron_to_add = cron.new(user=ph.db_username, command=cron_parts[1])
                cron_to_add.minute.every(int(cron_parts[0].replace('m', '')))
            elif 'h' in cron_parts[0]:
                cron_to_add = cron.new(user=ph.db_username, command=cron_parts[1])
                cron_to_add.hour.every(int(cron_parts[0].replace('h', '')))
            else:
                cron_to_add = cron.new(user=ph.db_username, command=cron_parts[1])
                cron_to_add.hour.on(int(cron_parts[0].replace('d', '')))
                cron_to_add.minute.on(0)
        if cron_to_add is not None:
            cron.write()


def execute(cmd):
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True) as p:
        for line in p.stdout:
            logger.info(line)

    return p.returncode


def add_server_service():
    try:
        with open(ph.project_path + '/bin/analyze.service', 'r') as svc_template_file:
            analyze_service = svc_template_file.read().format(project_path=ph.project_path)
        with open('/etc/systemd/system/analyze.service', 'w+') as service_file:
            service_file.write(analyze_service)
            service_file.close()
    except IOError as err:
        logger.error('Failed to add service for statistics server. Reason: ' + str(err))
        return 1

    start_service = subprocess.Popen(['systemctl', 'start', 'analyze.service'])
    start_service.wait()
    if start_service.returncode is not 0:
        logger.warning('Failed to start statistics server service. Proceeding to next step anyway')
        logger.warning('Reason: ' + start_service.stderr.read().decode('utf-8'))

    add_service_auto = subprocess.Popen(['systemctl', 'enable', 'analyze.service'])
    add_service_auto.wait()
    if add_service_auto.returncode is not 0:
        logger.warning('Failed to setup statistics server service to start on boot. Proceeding to next step anyway')
        logger.warning('Reason: ' + add_service_auto.stderr.read().decode('utf-8'))


def install_requirements():
    return execute(['pip', 'install', '--user', '--requirement', './requirements.txt'])


def create_db():
    con = psycopg2.connect(dbname='postgres',
                           user='pi', host='',
                           password='pi')

    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    cur = con.cursor()

    # Create role and db
    with open(ph.project_path + '/bin/sql/create_database.sql', 'r') as add_db_template:
        sout = ''
        for line in add_db_template.readlines():
            sout.join(line.format(db_username=ph.db_username,
                                  db_password=ph.db_password,
                                  db_name=ph.db_name) + r'\n')
            # cur.execute(sql.SQL(line).format(db_username=ph.db_username,
            #                                  db_password=ph.db_password,
            #                                  db_name=ph.db_name))))
    print(sout)
    exit(0)


def main():
    # if install_requirements() is not 0:
    #     logger.error('Failed to install python' + ph.python_version + ' dependencies. Aborting with error')
    #     return 1
    # if add_server_service() is not 0:
    #     return 1
    # add_crontabs()
    # add_server_service()
    create_db()


if __name__ == '__main__':
    main()
