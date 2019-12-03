#!/usr/bin/python

import inspect
import logging
import os

from params import ParameterHandler

ph = ParameterHandler()
log_file_path = ph.project_path + '/sessions.log'

if not os.path.exists(log_file_path):
    os.mknod(log_file_path)
    os.chown(log_file_path, 1000, 1000)
elif (os.stat(log_file_path).st_size / 1024.0 / 1024.0) > 50.0:  # MB
    os.remove(log_file_path)


class _Logger(object):
    def __init__(self, logging_level=logging.DEBUG):
        logging.basicConfig(format='%(asctime)-s,%(msecs)-5d [%(levelname)-8s] %(message)s',
                            datefmt='%Y-%m-%d:%H:%M:%S',
                            level=logging_level,
                            filename=log_file_path)
        self.logger = logging.getLogger('startup')
        stdout_format = logging.StreamHandler()
        formatter = logging.Formatter(fmt='%(asctime)-s,%(msecs)-5d [%(levelname)-8s] %(message)s',
                                      datefmt='%Y-%m-%d:%H:%M:%S')
        stdout_format.setFormatter(formatter)
        self.logger.addHandler(stdout_format)

    @staticmethod
    def _caller_info():
        frame = inspect.stack()[4]
        return '[{:10s}:{:3s}]'.format(frame[1].split('/')[-1], str(frame[2]))

    def log(self, message, log):
        lines = list(str(message).splitlines())
        for line in lines:
            log(self._caller_info() + ''.ljust(4) + line)

    def info(self, message):
        self.log(message, self.logger.info)

    def warning(self, message):
        self.log(message, self.logger.warning)

    def error(self, message):
        self.log(message, self.logger.error)

    def critical(self, message):
        self.log(message, self.logger.critical)


_logger = _Logger(logging.DEBUG)


def info(*message):
    _logger.info(' '.join([str(m) for m in message]))


def warning(*message):
    _logger.warning(' '.join([str(m) for m in message]))


def error(*message):
    _logger.error(' '.join([str(m) for m in message]))


def critical(*message):
    _logger.critical(' '.join([str(m) for m in message]))
