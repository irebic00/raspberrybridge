#!/usr/bin/python

import subprocess

import logger

destinations = ['www.google.de', 'www.amazon.de']


def is_connected(wlan_interface):
    logger.info('Checking availability of hosts (connection probe)')
    ping_results = []
    for destination in destinations:
        ping_result = subprocess.run(['ping', destination, '-c', '1', '-I', wlan_interface], stdout=subprocess.DEVNULL)\
            .returncode
        logger.info('Ping:', destination, ', host is', 'reachable' if ping_result is 0 else 'unreachable')
        ping_results.append(ping_result)

    for ping_result in ping_results:
        if ping_result == 0:
            logger.info('Success, one or more hosts are reachable')
            return True

    logger.warning('None of hosts is reachable')
    return False
