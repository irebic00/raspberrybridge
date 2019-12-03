#!/usr/bin/python

import subprocess

import pynmcli

import logger
import ping
from params import ParameterHandler

ph = ParameterHandler()

ssids = ph.preferred_ssids
wlan_interface = ph.inboud_interface


def check_connection_priority(wlan_probe):
    ssid_in_use = None
    available_ssid = None
    available_ssid_priority = len(list(ssids))
    for available_wlan in wlan_probe:
        is_connected = available_wlan.get('IN-USE') == '*'
        if is_connected:
            ssid_in_use = available_wlan.get('SSID')
        try:
            available_wlan_priority = list(ssids).index(available_wlan.get('SSID'))
        except ValueError:
            available_wlan_priority = len(list(ssids))
        if available_ssid_priority > available_wlan_priority:
            available_ssid_priority = available_wlan_priority
            available_ssid = available_wlan.get('SSID')

    ssid_in_use_priority = -1
    if ssid_in_use is None:
        return ssid_in_use, ssid_in_use_priority, available_ssid_priority, available_ssid

    for ssid in ssids.keys():
        ssid_in_use_priority += 1
        if ssid == ssid_in_use:
            return ssid_in_use, ssid_in_use_priority, available_ssid_priority, available_ssid
    return ssid_in_use, ssid_in_use_priority, available_ssid_priority, available_ssid


def available_profile_uuid(profile):
    available_profiles = pynmcli.get_data(pynmcli.NetworkManager.Connection().show().execute())
    for available_profile in available_profiles:
        if available_profile.get('NAME') == profile:
            return available_profile.get('UUID')
    return None


def connect(ssid):
    if available_profile_uuid(ssid) is not None:
        logger.info('Profile for', ssid, 'already exists, reusing it')
        # sudo nmcli connection up 360506a6-3a7f-41ad-bcb1-87fdd7c30a6d
        nmcli_result = pynmcli.NetworkManager.Connection().up(available_profile_uuid(ssid)).execute()
        logger.info(nmcli_result)
    else:
        logger.info('Profile for', ssid, 'does not exist, creating it')
        # nmcli device wifi connect SSID-Name password wireless-password
        nmcli_result = pynmcli.NetworkManager.Device().wifi().connect(ssid + ' password ' + ssids.get(ssid)).execute()
        logger.info(nmcli_result)


def start_vnc():
    vnc_already_running = 'Error: A VNC or X Server is already running as :1 [DisplayInUse]'
    new_vnc_server_started = ''
    start_vnc_cmd = subprocess.Popen(['su', 'pi', '-c', "vncserver :1 -geometry 1600x900 -depth 24"],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
    start_vnc_cmd.wait()
    start_vnc_err = start_vnc_cmd.stderr.read().decode("utf-8").strip()
    start_vnc_ret = start_vnc_cmd.returncode
    if start_vnc_err == vnc_already_running and start_vnc_ret == 1:
        logger.info('VNC server is already running on raspberrypi:1')
    elif start_vnc_err == new_vnc_server_started and start_vnc_ret == 0:
        logger.info('Started new VNC server on raspberrypi:1')
    else:
        logger.warning('Unknown status of VNC Server')


def main():
    logger.info(' ')
    logger.info('NEW EXECUTION Printing ' + wlan_interface + ' probe:')
    wlan_probe = pynmcli.get_data(pynmcli.NetworkManager.Device().wifi().execute())
    ssid_in_use, ssid_in_use_priority, available_ssid_priority, available_ssid = check_connection_priority(wlan_probe)
    logger.info(pynmcli.NetworkManager.Device().wifi().execute())

    if ssid_in_use is None and available_ssid is None:
        logger.critical('None of requested ssids is available:', ' '.join(list(ssids)))
        exit(1)

    if ping.is_connected(wlan_interface):
        logger.info('Already connected to:', ssid_in_use, 'that has priority:', ssid_in_use_priority)
        if available_ssid_priority < ssid_in_use_priority:
            logger.info('Found more preferred wlan available:', available_ssid, 'that has priority',
                        available_ssid_priority)
            logger.info('Reconnecting...')
            connect(available_ssid)
        else:
            logger.info('Already connected to the best available wlan.', 'Nothing to do...')
    else:
        connect(available_ssid)
        logger.info('Connected to', available_ssid, 'that has priority', available_ssid_priority)

    subprocess.run(['iwconfig', wlan_interface, 'power', 'off'])
    start_vnc()


if __name__ == '__main__':
    main()
