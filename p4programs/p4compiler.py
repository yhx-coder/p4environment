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

import os

import subprocess

from tools.log.log import log


class P4Compiler(object):
    P4_TARGET = 'bmv2'
    P4_ARCHITECTURE = 'v1'
    P4_VERSION = 'p4-16'  # p4-14
    P4C = 'p4c-bm2-ss'
    P4C_ARGS = ' --target {} --std {} -o {} --p4runtime-files {} {}.p4'

    def __init__(self):
        pass

    @classmethod
    def compile_p4program(cls, build_dir_path, json_file_path, p4info_file_path, p4program_path, p4program):
        if not os.path.isdir(build_dir_path):
            os.makedirs(build_dir_path)

        p4c_command = cls.P4C + cls.P4C_ARGS.format(cls.P4_TARGET,
                                                    cls.P4_VERSION,
                                                    json_file_path,
                                                    p4info_file_path,
                                                    os.path.join(p4program_path, p4program))

        log.info('running {}'.format(p4c_command))
        try:
            subprocess.check_output(p4c_command, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as ex:
            raise P4CompilationException('unable to compile p4program\n'
                                         'p4c exitcode: {}\ncmd: {}\noutput:\n{}'.format(ex.returncode,
                                                                                         ex.cmd,
                                                                                         ex.output))


class P4CompilationException(Exception):

    def __init__(self, message):
        super(P4CompilationException, self).__init__(self.__class__.__name__ + ': ' + message)
