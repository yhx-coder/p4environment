# Copyright 2020-present Christoph Hardegen
#                        (christoph.hardegen@cs.hs-fulda.de)
#                        Fulda University of Applied Sciences
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import mininet.log as mn_log

from enum import Enum


class LogLevel(Enum):
    INFO = 'info'
    DEBUG = 'debug'
    WARNING = 'warning'
    CRITICAL = 'critical'
    ERROR = 'error'


LOG_LEVEL_DEFAULT = LogLevel.INFO.value
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(pathname)s - %(funcName)s:%(lineno)d - %(message)s'
LOG_FORMAT_MININET = '%(message)s'

log = None
file_handler = None
console_handler = None


def init_logger(name):
    global log, file_handler, console_handler
    log_level = mn_log.LEVELS[LOG_LEVEL_DEFAULT]

    log = logging.getLogger(name + '.log')

    log.setLevel(log_level)

    file_handler = logging.FileHandler(name + '.log')
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    formatter = logging.Formatter(LOG_FORMAT)

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    log.addHandler(file_handler)
    log.addHandler(console_handler)


class FileHandlerNoNewline(logging.FileHandler, mn_log.StreamHandlerNoNewline):

    def emit(self, record):
        if self.stream is None:
            self.stream = self._open()
        mn_log.StreamHandlerNoNewline.emit(self, record)


def customize_mininet_logger(name):
    mn_file_handler = FileHandlerNoNewline(name + '.log')

    mn_formatter = logging.Formatter(LOG_FORMAT_MININET)
    mn_file_handler.setFormatter(mn_formatter)
    mn_log.lg.handlers[0].setFormatter(mn_formatter)

    mn_log.lg.addHandler(mn_file_handler)

    mn_log.lg.setLogLevel(LOG_LEVEL_DEFAULT)


def change_log_level(log_level):
    global log, file_handler, console_handler

    mn_log.lg.setLogLevel(log_level)

    log_level = mn_log.LEVELS[log_level]

    log.setLevel(log_level)
    file_handler.setLevel(log_level)
    console_handler.setLevel(log_level)
