#!/usr/bin/python

import json
from collections import OrderedDict
from pathlib import Path


class ParameterHandler:
    def __init__(self):
        self._this_path = Path(__file__).absolute().parent
        self.project_path = self._this_path.parent
        self._config = json.loads(self._this_path.joinpath('config.json').read_text(),
                                  encoding='utf-8', object_hook=OrderedDict)

    @property
    def project_path(self):
        return str(self.__project_path)

    @project_path.setter
    def project_path(self, path):
        self.__project_path = path

    @property
    def inboud_interface(self):
        return self._config.get('INBOUND_TRAFFIC_INTERFACE')

    @property
    def outbound_interface(self):
        return self._config.get('OUTBOUND_TRAFFIC_INTERFACE')

    @property
    def db_name(self):
        return self._config.get('DB_NAME')

    @property
    def db_username(self):
        return self._config.get('DB_USERNAME')

    @property
    def db_password(self):
        return self._config.get('DB_PASSWORD')

    @property
    def max_download(self):
        return self._config.get('MAX_DOWNLOAD')

    @property
    def max_upload(self):
        return self._config.get('MAX_UPLOAD')

    @property
    def python_version(self):
        return self._config.get('PYTHON_VERSION')

    @property
    def preferred_ssids(self):
        return self._config.get('PREFERRED_SSIDS')
