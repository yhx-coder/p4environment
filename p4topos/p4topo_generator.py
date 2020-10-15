# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Adapted by Robert MacDavid (macdavid@cs.princeton.edu) from scripts found in
# the p4app repository (https://github.com/p4lang/p4app)
#
#
# modified by Christoph Hardegen
#             (christoph.hardegen@cs.hs-fulda.de)
#             Fulda University of Applied Sciences
#
#############################################################################
# based on P4 language tutorials                                            #
# see https://github.com/p4lang/tutorials/blob/master/utils/run_exercise.py #
#############################################################################

import os
import json

from p4programs.p4compiler import P4Compiler

from p4env import P4Switches

from tools.log.log import log


class TopologyGenerator(object):

    @staticmethod
    def build_topology_json(tp_params):
        def _check_link_config(link):
            if 'bw' in link:
                if type(link['bw']) != int or link['bw'] not in tp_params.LINK_BANDWIDTH_VALID:
                    return False
            if 'delay' in link:
                if type(link['delay']) != int or link['delay'] not in tp_params.LINK_DELAY_VALID:
                    return False
            if 'loss' in link:
                if type(link['loss']) != int or link['loss'] not in tp_params.LINK_LOSS_VALID:
                    return False
            return True

        def _prepare_switch_ports(links):
            links['host_links'] = sorted(links['host_links'], key=lambda x: list([x['host'], x['switch']]))
            links['switch_links'] = sorted(links['switch_links'], key=lambda x: list([x['switch1'], x['switch2']]))

            switches = set()
            for switch_pair in links['switch_links']:
                switches.add(switch_pair['switch1'])
                switches.add(switch_pair['switch2'])
            for switch in [hlink['switch'] for hlink in links['host_links']]:
                switches.add(switch)
            switch_ports = [1 for _ in range(len(switches))]

            for hlink in links['host_links']:
                sw = hlink['switch']
                hlink['switch_port'] = switch_ports[sw - 1]
                switch_ports[sw - 1] += 1

            for slink in links['switch_links']:
                sw1 = slink['switch1']
                sw2 = slink['switch2']
                slink['switch1_port'] = switch_ports[sw1 - 1]
                slink['switch2_port'] = switch_ports[sw2 - 1]
                switch_ports[sw1 - 1] += 1
                switch_ports[sw2 - 1] += 1

            return links

        p4programs = [tp_params.P4_PROGRAM]

        topo_dict = {'management': {},
                     'hosts': {},
                     'switches': {},
                     'links': {'host_links': [],
                               'switch_links': []}}

        if tp_params.SWITCH_INIT:
            log.info('loading switches config...')
            assert tp_params.SWITCHES_CONFIG_FILE
            if not os.path.isfile(tp_params.SWITCHES_CONFIG_FILE):
                raise TopologyConfigException('missing switches config file '
                                              'for topology ({})'.format(tp_params.TOPOLOGY_NAME))

            switches_config = None
            with open(tp_params.SWITCHES_CONFIG_FILE, 'r') as switches_config_file:
                switches_config = json.load(switches_config_file)

        if tp_params.HOST_INIT:
            log.debug('loading hosts config...')
            assert tp_params.HOSTS_CONFIG_FILE
            if not os.path.isfile(tp_params.HOSTS_CONFIG_FILE):
                raise TopologyConfigException('missing hosts config file '
                                              'for topology ({})'.format(tp_params.TOPOLOGY_NAME))

            hosts_config = None
            with open(tp_params.HOSTS_CONFIG_FILE, 'r') as hosts_config_file:
                hosts_config = json.load(hosts_config_file)

        log.debug('checking log dir...')
        assert tp_params.LOG_DIR_PATH
        if not os.path.isdir(tp_params.LOG_DIR):
            os.makedirs(tp_params.LOG_DIR)

        if tp_params.P4_PCAP_DUMP:
            log.debug('checking pcap dir...')
            assert tp_params.P4_PCAP_DIR_PATH
            if not os.path.isdir(tp_params.P4_PCAP_DIR):
                os.makedirs(tp_params.P4_PCAP_DIR)

        log.info('loading links config...')
        assert tp_params.LINKS_CONFIG_FILE
        if not os.path.isfile(tp_params.LINKS_CONFIG_FILE):
            raise TopologyConfigException('missing links file for topology ({})'.format(tp_params.TOPOLOGY_NAME))

        with open(tp_params.LINKS_CONFIG_FILE, 'r') as topo_links_file:
            topo_links = json.load(topo_links_file)

        if tp_params.LINKS_CONFIG_MODE == 'auto':
            topo_links = _prepare_switch_ports(topo_links)

        topo_dict['host_class'] = tp_params.HOST_CLASS.value.__name__

        log.info('creating topology...')
        for hlink in topo_links['host_links']:
            host_num = hlink['host']
            hostname = tp_params.HOSTNAME.format(host_num)
            host_cmds = hosts_config[str(host_num)][
                'commands'] if tp_params.HOST_INIT and host_num in hosts_config else []
            topo_dict['hosts'][hostname] = {'num': host_num,
                                            'ip': tp_params.HOST_IP.format(host_num),
                                            'mac': tp_params.HOST_MAC.format(str(host_num).zfill(2)),
                                            'network': tp_params.HOST_NETWORK.format(host_num),
                                            'gw_ip': tp_params.HOST_GW.format(host_num),
                                            'gw_mac': tp_params.HOST_GW_MAC.format(host_num),
                                            'mgmt_ip': tp_params.HOST_MANAGEMENT_IP.format(host_num),
                                            'mgmt_mac': tp_params.HOST_MANAGEMENT_MAC.format(str(host_num).zfill(2)),
                                            'cmd': host_cmds}

            sw = {'name': tp_params.SWITCHNAME.format(hlink['switch']),
                  'port': hlink['switch_port']}

            if not _check_link_config(hlink):
                raise TopologyConfigException('invalid host link configuration ({},{})'.format(hostname,
                                                                                               sw['name']))

            topo_dict['links']['host_links'].append({'host': hostname,
                                                     'switch': sw,
                                                     'bw': hlink.get('bw', tp_params.LINK_BANDWIDTH_HOSTS),
                                                     'delay': hlink.get('delay', tp_params.LINK_DELAY_HOSTS),
                                                     'loss': hlink.get('loss', tp_params.LINK_LOSS_HOSTS)})

        topo_dict['management']['host'] = {'name': tp_params.MANAGEMENT_HOST_NAME,
                                           'ip_switches': tp_params.MANAGEMENT_HOST_IP_SWITCHES,
                                           'mac_switches': tp_params.MANAGEMENT_HOST_MAC_SWITCHES,
                                           'ip_hosts': tp_params.MANAGEMENT_HOST_IP_HOSTS,
                                           'mac_hosts': tp_params.MANAGEMENT_HOST_MAC_HOSTS}
        topo_dict['management']['switch'] = {'switches': {'name': tp_params.MANAGEMENT_SWITCH_NAME_SWITCHES},
                                             'hosts': {'name': tp_params.MANAGEMENT_SWITCH_NAME_HOSTS}}
        topo_dict['management']['links'] = {'bw': tp_params.LINK_BANDWIDTH_HOSTS,
                                            'delay': tp_params.LINK_DELAY_HOSTS,
                                            'loss': tp_params.LINK_LOSS_HOSTS}

        topo_dict['switch_class'] = tp_params.P4_SWITCH_CLASS.value.__name__
        # topo_dict['controller_ip'] = tp_params.CONTROLLER_IP
        # topo_dict['controller_port'] = tp_params.CONTROLLER_PORT
        topo_dict['monitor_class'] = tp_params.P4_MONITOR.__name__
        topo_dict['controller_class'] = tp_params.P4_CONTROLLER.__name__ if tp_params.P4_CONTROLLER else None

        topo_dict['traffic_profile'] = tp_params.TRAFFIC_PROFILE
        if tp_params.TRAFFIC_PROFILE:
            if not os.path.isdir(tp_params.TRAFFIC_PROFILES_DIR):
                os.makedirs(tp_params.TRAFFIC_PROFILES_DIR)

        thrift_port = tp_params.P4_THRIFT_BASE_PORT
        if tp_params.P4_SWITCH_CLASS == P4Switches.P4RuntimeSwitch:
            grpc_port = tp_params.P4_GRPC_BASE_PORT
        else:
            grpc_port = None

        def _prepare_switches(sw):
            log_path = os.path.join(tp_params.LOG_DIR_PATH, sw)
            if not os.path.isdir(log_path):
                os.makedirs(log_path)

            if tp_params.P4_PCAP_DUMP:
                pcap_path = os.path.join(tp_params.P4_PCAP_DIR_PATH, sw)
                if not os.path.isdir(pcap_path):
                    os.makedirs(pcap_path)

            sw_num = int(sw[len(tp_params.SWITCHNAME[:-2]):])
            switch_cmds = []
            if tp_params.SWITCH_INIT in ['p4runtime_CLI', 'hybrid']:
                try:
                    switch_cmds = switches_config[str(sw_num)]['cli_commands']
                except KeyError:
                    pass

            topo_dict['switches'][sw] = {'num': sw_num,
                                         'mgmt_ip': tp_params.SWITCH_MANAGEMENT_IP.format(sw_num),
                                         'mgmt_mac': tp_params.SWITCH_MANAGEMENT_MAC.format(str(sw_num).zfill(2)),
                                         'thrift_port': thrift_port + int(sw_num),
                                         'grpc_port': grpc_port + int(sw_num) if grpc_port else grpc_port,
                                         'cmd': switch_cmds,
                                         'bmv2_exec': tp_params.P4_BMV2_EXEC_PATH,
                                         'bmv2_cli': tp_params.P4_BMV2_CLI_PATH,
                                         'p4init': tp_params.SWITCH_INIT,
                                         'pcap_dump': tp_params.P4_PCAP_DUMP,
                                         'pcap_dir': tp_params.P4_PCAP_DIR_PATH.format(sw),
                                         'nanolog': tp_params.P4_NANOLOG,
                                         'nanolog_ipc': tp_params.P4_NANOLOG_IPC.format(sw),
                                         'notifications': tp_params.P4_NOTIFICATIONS,
                                         'notifications_ipc': tp_params.P4_NOTIFICATIONS_IPC.format(sw),
                                         'log_dir': tp_params.LOG_DIR_PATH,
                                         'log_level': tp_params.P4_LOG_LEVEL,
                                         'runtime_thrift_log': tp_params.P4_RUNTIME_THRIFT_LOG_FILE_PATH.format(sw, sw),
                                         'runtime_gRPC_log': tp_params.P4_RUNTIME_GRPC_LOG_FILE_PATH.format(sw, sw),
                                         'bmv2_cli_log': tp_params.P4_BMV2_CLI_LOG_FILE_PATH.format(sw, sw),
                                         'log_console': tp_params.P4_LOG_CONSOLE,
                                         'log_flush': tp_params.P4_LOG_FLUSH}

            p4program = tp_params.P4_PROGRAM
            if tp_params.SWITCH_INIT and sw_num in switches_config:
                try:
                    p4program_ = switches_config[str(sw_num)]['p4program']
                    if p4program_ != '' and p4program_ not in p4programs:
                        p4programs.append(p4program_)
                        p4program = p4program_
                except KeyError:
                    pass

            topo_dict['switches'][sw].update({'p4program': p4program,
                                              'bmv2_json': tp_params.P4_BMV2_JSON_FILE_PATH.format(p4app=p4program),
                                              'bmv2_info': tp_params.P4_INFO_FILE_PATH.format(p4app=p4program),
                                              'runtime_json': tp_params.P4_RUNTIME_FILE_PATH.format(sw)})

        if not topo_links['switch_links']:
            for sw in [hlink['switch'] for hlink in topo_links['host_links']]:
                sw = tp_params.SWITCHNAME.format(sw)
                if sw not in topo_dict['switches']:
                    _prepare_switches(sw)
        else:
            for slink in topo_links['switch_links']:
                sw1 = {'name': tp_params.SWITCHNAME.format(slink['switch1']),
                       'port': slink['switch1_port']}
                sw2 = {'name': tp_params.SWITCHNAME.format(slink['switch2']),
                       'port': slink['switch2_port']}

                for sw in [sw1['name'], sw2['name']]:
                    if sw not in topo_dict['switches']:
                        _prepare_switches(sw)

                if not _check_link_config(slink):
                    raise TopologyConfigException('invalid switch link configuration ({},{})'.format(sw1['name'],
                                                                                                     sw2['name']))

                bw = slink.get('bw', tp_params.LINK_BANDWIDTH_SWITCHES)
                bw_scale = slink.get('bw_scale', tp_params.LINK_BANDWIDTH_SWITCHES_SCALING)
                scaled_link_bw = bw * bw_scale
                topo_dict['links']['switch_links'].append({'switch1': sw1,
                                                           'switch2': sw2,
                                                           'bw': scaled_link_bw,
                                                           'bw_scale': bw_scale,
                                                           'delay': slink.get('delay', tp_params.LINK_DELAY_SWITCHES),
                                                           'loss': slink.get('loss', tp_params.LINK_LOSS_SWITCHES)})

        log.info('compiling P4 program(s)...')
        for p4program in p4programs:
            P4Compiler.compile_p4program(tp_params.P4_BUILD_DIR_PATH.format(p4app=p4program),
                                         tp_params.P4_BMV2_JSON_FILE_PATH.format(p4app=p4program),
                                         tp_params.P4_INFO_FILE_PATH.format(p4app=p4program),
                                         tp_params.P4_PROGRAM_PATH.format(p4app=p4program),
                                         p4program)

        if tp_params.P4_SWITCH_CLASS == P4Switches.P4RuntimeSwitch:
            log.debug('checking P4 runtime dir...')
            assert tp_params.P4_RUNTIME_DIR_PATH
            if not os.path.isdir(tp_params.P4_RUNTIME_DIR_PATH):
                os.makedirs(tp_params.P4_RUNTIME_DIR_PATH)

            log.debug('creating P4 runtime config(s)...')
            for sw in topo_dict['switches']:
                # default runtime json
                p4_runtime_sw_config = {
                    'target': 'bmv2',
                    'bmv2_json': topo_dict['switches'][sw]['bmv2_json'],
                    'p4info': topo_dict['switches'][sw]['bmv2_info'],
                    'table_entries': [],
                }

                assert tp_params.P4_RUNTIME_FILE_PATH
                runtime_file = tp_params.P4_RUNTIME_FILE_PATH.format(sw)
                if not os.path.isfile(runtime_file):
                    with open(runtime_file, 'w') as switch_config_file:
                        json.dump(p4_runtime_sw_config, switch_config_file, indent=4)

        log.info('saving topology file...')
        with open(tp_params.TOPOLOGY_FILE_PATH, 'w') as topo_file:
            json.dump(topo_dict, topo_file, indent=4)


class TopologyConfigException(Exception):

    def __init__(self, message):
        super(TopologyConfigException, self).__init__(self.__class__.__name__ + ': ' + message)
