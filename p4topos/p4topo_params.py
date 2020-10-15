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

from p4env import P4Hosts
from p4env import P4Switches

from tools.log.log import log


class TopologyParameter(object):
    INITIALIZED = False

    @classmethod
    def get_topology_params(cls, tp_args=None,
                            p4switch_class=None, p4host_class=None,
                            p4monitor_class=None, p4controller_class=None):

        def init_topology_params(cls, tp_args,
                                 p4switch_class, p4host_class,
                                 p4monitor_class, p4controller_class):

            params_ = locals()
            params_.pop('tp_args')
            params_.update({tp_args_k: tp_args_v for tp_args_k, tp_args_v in vars(tp_args).items()})
            if None in [param_v for param_k, param_v in params_.items() if param_k not in ['p4controller',
                                                                                           'p4controller_class',
                                                                                           'switch_init',
                                                                                           'traffic_profile']]:
                none_params = [k for k, v in params_.items() if v is None]
                raise P4InitException('''topology params initialization failed: 
                                         required params are None ({})'''.format(none_params))

            cls.TOPOLOGY_DIR = 'p4topos'
            cls.TOPOLOGY_NAME = tp_args.topology
            cls.TOPOLOGY_PATH = os.path.join(cls.TOPOLOGY_DIR, cls.TOPOLOGY_NAME)
            cls.TOPOLOGY_FILE = 'topology.json'
            cls.TOPOLOGY_FILE_PATH = os.path.join(cls.TOPOLOGY_PATH, cls.TOPOLOGY_FILE)

            cls.INIT_DIR = 'p4init'
            cls.SWITCHES_CONFIG = 'switches.json'
            cls.SWITCHES_CONFIG_FILE = os.path.join(cls.INIT_DIR, cls.TOPOLOGY_NAME,
                                                    tp_args.p4program, cls.SWITCHES_CONFIG)
            cls.HOSTS_CONFIG = 'hosts.json'
            cls.HOSTS_CONFIG_FILE = os.path.join(cls.INIT_DIR, cls.TOPOLOGY_NAME,
                                                 tp_args.p4program, cls.HOSTS_CONFIG)

            cls.HOSTNAME = 'h{}'
            cls.SWITCHNAME = 's{}'

            if tp_args.host_network == 'shared':
                cls.HOST_IP = '10.0.{}.1/16'
                cls.HOST_MAC = 'CA:FE:BA:BE:00:{}'
                cls.HOST_NETWORK = '10.0.0.0/16'
                cls.HOST_GW = '10.0.0.254'
                cls.HOST_GW_MAC = 'BA:DE:AF:FE:00:00'
            else:  # elif host_network == 'individual':
                cls.HOST_IP = '10.0.{}.1/24'
                cls.HOST_MAC = 'CA:FE:BA:BE:00:{}'
                cls.HOST_NETWORK = '10.0.{}.0/24'
                cls.HOST_GW = '10.0.{}.254'
                cls.HOST_GW_MAC = 'BA:DE:AF:FE:00:{}'

            cls.LINKS_CONFIG_MODE = tp_args.link_config
            cls.LINKS_CONFIG = 'links_{}.json'.format(tp_args.link_config)
            cls.LINKS_CONFIG_FILE = os.path.join(cls.TOPOLOGY_PATH, cls.LINKS_CONFIG)
            cls.LINK_BANDWIDTH_HOSTS = 10
            cls.LINK_DELAY_HOSTS = 0
            cls.LINK_LOSS_HOSTS = 0
            cls.LINK_BANDWIDTH_SWITCHES = 1
            # only to analyze distribution of flows, not suitable for evaluating load effects such as high latencies
            cls.LINK_BANDWIDTH_SWITCHES_SCALING = 1.25
            cls.LINK_DELAY_SWITCHES = 0
            cls.LINK_LOSS_SWITCHES = 0

            cls.LINK_BANDWIDTH_VALID = range(1, 1001)
            cls.LINK_DELAY_VALID = range(0, 1001)
            cls.LINK_LOSS_VALID = range(0, 101)

            cls.LOG_DIR = 'logs'
            cls.LOG_DIR_PATH = os.path.join(cls.LOG_DIR, cls.TOPOLOGY_NAME, tp_args.p4program)

            cls.SWITCH_MANAGEMENT_IP = '10.199.199.{}/24'
            cls.SWITCH_MANAGEMENT_MAC = 'CA:FE:BA:BE:99:{}'
            cls.MANAGEMENT_SWITCH_NAME_SWITCHES = 'sroot'

            cls.MANAGEMENT_HOST_NAME = 'hroot'
            cls.MANAGEMENT_HOST_IP_SWITCHES = cls.SWITCH_MANAGEMENT_IP.format(254)
            cls.MANAGEMENT_HOST_MAC_SWITCHES = cls.SWITCH_MANAGEMENT_MAC.format('FF')

            cls.HOST_MANAGEMENT_IP = '172.16.0.{}/24'
            cls.HOST_MANAGEMENT_MAC = 'DE:AD:BE:EF:99:{}'
            cls.MANAGEMENT_SWITCH_NAME_HOSTS = 'srooth'

            cls.MANAGEMENT_HOST_IP_HOSTS = cls.HOST_MANAGEMENT_IP.format(254)
            cls.MANAGEMENT_HOST_MAC_HOSTS = cls.HOST_MANAGEMENT_MAC.format('FF')

            if p4host_class == P4Hosts.P4Host.value:
                cls.HOST_CLASS = P4Hosts.P4Host
            cls.HOST_INIT = tp_args.host_init

            if tp_args.switch_init is 'None':
                log.info('running p4 switch without initialization')

            if p4switch_class == P4Switches.P4Switch.value:
                cls.P4_SWITCH_CLASS = P4Switches.P4Switch
                cls.P4_BMV2_EXEC = 'simple_switch'
                cls.P4_BMV2_EXEC_PATH = subprocess.check_output('which {}'.format(cls.P4_BMV2_EXEC), shell=True).strip()

                if tp_args.switch_init not in ['p4runtime_CLI', 'None']:
                    raise P4InitException('unsupported initialization method'
                                          'for p4 switch ({})'.format(tp_args.switch_init))
            else:  # elif switch == P4Switches.P4RuntimeSwitch:
                cls.P4_SWITCH_CLASS = P4Switches.P4RuntimeSwitch
                cls.P4_BMV2_EXEC = 'simple_switch_grpc'
                cls.P4_BMV2_EXEC_PATH = subprocess.check_output('which {}'.format(cls.P4_BMV2_EXEC), shell=True).strip()

                if tp_args.switch_init not in ['p4runtime_CLI', 'p4runtime_API', 'hybrid', 'None']:
                    raise P4InitException('unsupported initialization method'
                                          'for p4runtime switch ({})'''.format(tp_args.switch_init))
            cls.SWITCH_INIT = tp_args.switch_init if tp_args.switch_init != 'None' else None

            cls.P4_THRIFT_BASE_PORT = 8000
            cls.P4_GRPC_BASE_PORT = 9000

            # cls.P4_CONTROLLER_IP = '127.0.0.1'
            # cls.P4_CONTROLLER_PORT = 4221

            cls.P4_CONTROLLER = p4controller_class if p4controller_class else None
            cls.P4_MONITOR = p4monitor_class

            cls.TRAFFIC_PROFILES_DIR = 'tools/traffic_profiles/profiles'
            cls.TRAFFIC_PROFILE = os.path.join(cls.TRAFFIC_PROFILES_DIR,
                                               tp_args.traffic_profile) if tp_args.traffic_profile else None

            cls.P4_BMV2_CLI = 'simple_switch_CLI'
            cls.P4_BMV2_CLI_PATH = subprocess.check_output('which {}'.format(cls.P4_BMV2_CLI), shell=True).strip()
            cls.P4_BMV2_CLI_LOG_FILE = '{}_cli_output.log'
            cls.P4_BMV2_CLI_LOG_FILE_PATH = os.path.join(cls.LOG_DIR_PATH, '{}', cls.P4_BMV2_CLI_LOG_FILE)
            cls.P4_PROGRAM_DIR = 'p4programs'
            cls.P4_PROGRAM = tp_args.p4program
            cls.P4_PROGRAM_PATH = os.path.join(cls.P4_PROGRAM_DIR, '{p4app}')
            cls.P4_BUILD_DIR = 'p4build'
            cls.P4_BUILD_DIR_PATH = os.path.join(cls.P4_PROGRAM_DIR, '{p4app}', cls.P4_BUILD_DIR)
            cls.P4_BMV2_JSON_FILE = '{p4app}.json'
            cls.P4_BMV2_JSON_FILE_PATH = os.path.join(cls.P4_PROGRAM_DIR, '{p4app}', cls.P4_BUILD_DIR,
                                                      cls.P4_BMV2_JSON_FILE)
            cls.P4_INFO_FILE = '{p4app}.p4info.txt'
            cls.P4_INFO_FILE_PATH = os.path.join(cls.P4_PROGRAM_DIR, '{p4app}', cls.P4_BUILD_DIR, cls.P4_INFO_FILE)
            cls.P4_RUNTIME_DIR = 'p4runtime'
            cls.P4_RUNTIME_DIR_PATH = os.path.join(cls.INIT_DIR, cls.TOPOLOGY_NAME, cls.P4_PROGRAM, cls.P4_RUNTIME_DIR)
            cls.P4_RUNTIME_FILE = '{}-p4runtime.json'
            cls.P4_RUNTIME_FILE_PATH = os.path.join(cls.P4_RUNTIME_DIR_PATH, cls.P4_RUNTIME_FILE)
            cls.P4_RUNTIME_GRPC_LOG_FILE = '{}_runtime_gRPC.log'
            cls.P4_RUNTIME_GRPC_LOG_FILE_PATH = os.path.join(cls.LOG_DIR_PATH, '{}', cls.P4_RUNTIME_GRPC_LOG_FILE)
            cls.P4_RUNTIME_THRIFT_LOG_FILE = '{}_runtime_thrift.log'
            cls.P4_RUNTIME_THRIFT_LOG_FILE_PATH = os.path.join(cls.LOG_DIR_PATH, '{}', cls.P4_RUNTIME_THRIFT_LOG_FILE)
            cls.P4_PCAP_DUMP = True
            cls.P4_PCAP_DIR = 'pcaps'
            cls.P4_PCAP_DIR_PATH = os.path.join(cls.P4_PCAP_DIR, cls.TOPOLOGY_NAME, tp_args.p4program)
            cls.P4_LOG_CONSOLE = False
            cls.P4_LOG_LEVEL = 'trace'  # 'trace', 'debug', 'info', 'warn', 'error', off'
            cls.P4_LOG_FLUSH = True
            cls.P4_NANOLOG = True
            cls.P4_NANOLOG_IPC = 'ipc:///tmp/bm-{}-log.ipc'
            cls.P4_NOTIFICATIONS = True
            cls.P4_NOTIFICATIONS_IPC = 'ipc:///tmp/bm-{}-notifications.ipc'

            if cls.P4_SWITCH_CLASS == P4Switches.P4RuntimeSwitch and cls.P4_NOTIFICATIONS:
                log.warn('p4runtime switch targets capture all notifications and '
                         'do not generate nanomsg messages')
                # raise P4InitException('p4runtime switch targets capture all notifications and'
                #                       'do not generate nanomsg messages')

            cls.INITIALIZED = True

            return cls

        if cls.INITIALIZED:
            return cls
        else:
            init_topology_params(cls,
                                 tp_args=tp_args,
                                 p4switch_class=p4switch_class,
                                 p4host_class=p4host_class,
                                 p4monitor_class=p4monitor_class,
                                 p4controller_class=p4controller_class)
            return cls


class P4InitException(Exception):

    def __init__(self, message):
        super(P4InitException, self).__init__(self.__class__.__name__ + ': ' + message)
