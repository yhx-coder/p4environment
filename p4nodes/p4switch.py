# Copyright 2017-present Barefoot Networks, Inc.
# Copyright 2017-present Open Networking Foundation
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
# modified by Christoph Hardegen
#             (christoph.hardegen@cs.hs-fulda.de)
#             Fulda University of Applied Sciences
#
#################################################################################
# adapted from P4 language tutorials                                            #
# see https://github.com/p4lang/tutorials/blob/master/utils/p4_mininet.py       #
# see https://github.com/p4lang/tutorials/blob/master/utils/p4runtime_switch.py #
# see https://github.com/p4lang/tutorials/blob/master/utils/netstat.py          #
#################################################################################

from mininet.node import Switch
from mininet.link import TCIntf
from mininet.moduledeps import pathCheck

import os
import psutil
import tempfile
from time import sleep
import json
import requests

from tools.log.log import log

import subprocess

import time


class P4Switch(Switch):
    CPU_PORT_ID = 510
    DROP_PORT_ID = 511

    WAIT_STARTED_LIMIT = 10

    MANAGEMENT_PORT_ID = 9999

    NETSTAT_CHECK_CMD = ''' netstat -tln | grep -E ":{port}" | awk -F ' +' '{{print $6}}' '''

    SSHD_START_CMD = '/usr/sbin/sshd -4 -o ListenAddress={server_address}:{port}'
    SSHD_STOP_CMD = ("ps -x | grep /usr/sbin/sshd | "
                     "grep 'ListenAddress={server_address}:{port}' | awk -F ' ' '{{print $1}}' | xargs kill -9")

    def __init__(self, *args, **params):
        super(P4Switch, self).__init__(*args, **params)

        self.sw_pid = None

        self.device_id = params['dpid']

        switch_params = params['switch_params']

        self.p4init = switch_params['p4init']

        self.bmv2_exec = switch_params['bmv2_exec']
        assert self.bmv2_exec
        pathCheck(self.bmv2_exec)

        self.p4program = switch_params['p4program']

        self.bmv2_json = switch_params['bmv2_json']
        assert self.bmv2_json
        if not os.path.isfile(self.bmv2_json):
            raise P4ConfigException('p4 json file ({}) for switch {} not available'.format(self.bmv2_json, self.name))

        self.bmv2_info = switch_params['bmv2_info']

        self.mgmt_ip = switch_params['mgmt_ip'].split('/')[0]
        self.mgmt_ip_with_prefix_len = switch_params['mgmt_ip']
        self.mgmt_mac = switch_params['mgmt_mac']

        self.thrift_port = switch_params['thrift_port']

        log_file = os.path.join(switch_params['log_dir'], self.name, self.name + '_startup.log')
        self.log_file_startup = open(log_file, 'a')
        self.log_file_runtime = os.path.join(switch_params['log_dir'], self.name, self.name + '.log')
        self.log_console = switch_params['log_console']
        self.log_level = switch_params['log_level']
        self.log_flush = switch_params['log_flush']

        self.runtime_thrift_log = switch_params['runtime_thrift_log'].format(self.name, self.name)

        self.pcap_dir = os.path.join(switch_params['pcap_dir'], self.name) if switch_params['pcap_dump'] else None

        self.nanolog = switch_params['nanolog_ipc'].format(self.name) if switch_params['nanolog'] else None

        if switch_params['notifications']:
            self.notifications = switch_params['notifications_ipc'].format(self.name)
        else:
            self.notifications = None

        self.startup_cli_commands = switch_params['cmd']

        self.bmv2_cli = switch_params['bmv2_cli']
        self.bmv2_cli_log = switch_params['bmv2_cli_log'].format(self.name, self.name)

        self.start_cmd = None
        self.timestamp_started = None

        def _add_cpu_port():
            commands = ['ip link set dev {intf} up', 'ip link set {intf} mtu 9500',
                        'sysctl net.ipv6.conf.{intf}.disable_ipv6=1']

            self.cmd('ip link add name {sname}-cpu type veth peer name cpu-{sname}'.format(sname=self.name))
            for cmd in commands:
                for intf in ['{sname}-cpu'.format(sname=self.name), 'cpu-{sname}'.format(sname=self.name)]:
                    self.cmd(cmd.format(intf=intf))
            self.cmd('ip link set {intf} netns 1'.format(intf='cpu-{sname}'.format(sname=self.name)))
            devnull_ = open(os.devnull, 'w')
            subprocess.call('sysctl net.ipv6.conf.{}.disable_ipv6=1'.format('cpu-{}'.format(self.name)),
                            shell=True, stdout=devnull_, stderr=devnull_)
            subprocess.call('ip link set dev {intf} up'.format(intf='cpu-{sname}'.format(sname=self.name)),
                            shell=True, stdout=devnull_, stderr=devnull_)

            return self.name + '-cpu'

        self.cpu_port = _add_cpu_port()

        self.switch_config = dict()

    def wait_switch_started(self):
        for x in range(P4Switch.WAIT_STARTED_LIMIT):
            if not os.path.exists('/proc/' + str(self.sw_pid)) or not self.check_listening_on_port(self.thrift_port):
                sleep(1)
                continue
            return True
        return False

    def build_start_cmd(self):
        cmd = '{} '.format(self.bmv2_exec)
        for port, intf in self.intfs.items():
            if port not in [0, P4Switch.MANAGEMENT_PORT_ID]:
                cmd += '-i {}@{} '.format(port, intf.name)

        cmd += '-i {}@{} '.format(P4Switch.CPU_PORT_ID, self.cpu_port)

        cmd += '--thrift-port {} '.format(self.thrift_port)

        cmd += '--device-id {} '.format(self.device_id)

        cmd += '--log-file {} '.format(self.log_file_runtime)

        cmd += '--log-level {} '.format(self.log_level)

        if self.log_flush:
            cmd += '--log-flush '

        if self.log_console:
            cmd += '--log-console '

        if self.pcap_dir:
            cmd += '--pcap {} '.format(self.pcap_dir)

        if self.nanolog:
            cmd += '--nanolog {} '.format(self.nanolog)

        if self.notifications:
            cmd += '--notifications-addr {} '.format(self.notifications)

        if not isinstance(self, P4RuntimeSwitch):
            cmd += '{} '.format(self.bmv2_json)
        else:
            cmd += '{} '.format('--no-p4')

        cmd += '-- '  # target specific options

        cmd += '--drop-port {} '.format(P4Switch.DROP_PORT_ID)

        # cmd += '--cpu-port {} '.format(P4RuntimeSwitch.CPU_PORT)

        return cmd

    def start(self, _):
        self.intfs[P4Switch.MANAGEMENT_PORT_ID].setMAC(self.mgmt_mac)  # dirty for now
        self.intfs[P4Switch.MANAGEMENT_PORT_ID].setIP(self.mgmt_ip_with_prefix_len)  # dirty for now

        self.start_cmd = self.build_start_cmd()

        with tempfile.NamedTemporaryFile() as tmp:
            self.cmd(self.start_cmd + ' >' + self.log_file_startup.name + ' 2>&1 & echo $! >> ' + tmp.name)
            self.sw_pid = int(tmp.read())

        if not self.wait_switch_started():
            raise P4SwitchNotStartedException('p4 switch {} not started\n ({})'.format(self.name, self.cmd))

        self.timestamp_started = int(round(time.time() * 1000))

        log.info('p4 switch {} has been started'.format(self.name))

        self._build_switch_config()

        self.disable_ipv6()
        # self.disable_offloading()

    def stop(self, delete_intfs=True):
        self.log_file_startup.flush()
        self.log_file_startup.close()
        self.cmd('kill -9 {}'.format(self.sw_pid))
        self.cmd('wait')
        if delete_intfs:
            self.deleteIntfs()

    def _build_switch_config(self):
        if not self.switch_config:
            self.switch_config.update({
                'name': self.name,
                'type': 'switch',
                'class': str(self.__class__.__name__),
                'device_id': self.device_id,
                'mgmt_ip': self.mgmt_ip,
                'mgmt_mac': self.mgmt_mac,
                'thrift_port': self.thrift_port,
                'p4program': self.p4program,
                'p4init': self.p4init,
                'bmv2_p4json': self.bmv2_json,
                'bmv2_p4info': self.bmv2_info,
                'ports': {'mgmt_port': self.MANAGEMENT_PORT_ID,
                          'cpu_port': self.CPU_PORT_ID,
                          'data_links': {port_id: {  # MANAGEMENT and CPU port are no TCIntfs
                              'name': intf.name,
                              'peer': intf.name.split('-')[1],
                              'bw': intf.params['bw'] if 'bw_scale' not in intf.params \
                                  else intf.params['bw'] / intf.params['bw_scale'],
                              'delay': intf.params['delay'],
                              'loss': intf.params['loss']} for port_id, intf in self.intfs.items() \
                              if isinstance(intf, TCIntf)}},
                'nanolog_ipc': self.nanolog,
                'notifications_ipc': self.notifications,
                'runtime_thrift_log': self.runtime_thrift_log,
                'timestamp_started': self.timestamp_started})

    def configure(self):
        with open(self.bmv2_cli_log, 'a') as cli_log_file:
            for command in self.startup_cli_commands:
                switch_cli = self.bmv2_cli + ' --thrift-ip ' + self.mgmt_ip + ' --thrift-port ' + str(self.thrift_port)
                cmd = "echo '" + command + "' | " + switch_cli
                log.info(cmd)
                cli_log_file.write(cmd + '\n')
                cli_log_file.flush()
                self.cmd(cmd)

        for intf in self.intfs.values():
            self.cmd('sysctl -w net.ipv6.conf.{}.disable_ipv6=1'.format(intf.name))

    def describe(self):
        log.info('#' * 15)
        log.info('# switch name: ' + self.name)
        log.info('# switch management addresses: ' + self.mgmt_ip + ' | ' + self.mgmt_mac)
        log.info('# start command: ' + self.start_cmd)
        log.info('#' * 15)

    def register_controller(self, controller_address):
        try:
            response = requests.post(url='http://{}/node'.format(controller_address),
                                     json=json.dumps(self.switch_config))
            log.info('register switch config ({}): {}\n'.format(self.name, response))
        except requests.exceptions.ConnectionError as ex:
            log.warn(ex)
            log.warn('unable to register switch config ({})\n'.format(self.name))
            # raise P4ControllerRegisterException('unable to register switch config ({})\n'.format(self.name))

    def get_switch_config(self):
        return self.switch_config

    def check_listening_on_port(self, port):
        if self.cmd(self.NETSTAT_CHECK_CMD.format(host=self.mgmt_ip, port=port)).rstrip() == 'LISTEN':
            return True
        return False

    def start_services(self):
        self.start_ssh_server()

    def stop_services(self):
        self.stop_ssh_server()

    def start_ssh_server(self):
        self.cmd(self.SSHD_START_CMD.format(server_address=self.mgmt_ip, port=22))

    def stop_ssh_server(self):
        self.cmd(self.SSHD_STOP_CMD.format(server_address=self.mgmt_ip, port=22))

    def disable_offloading(self):
        for intf in [intf_ for intf_ in self.intfs.values() if isinstance(intf_, TCIntf)]:
            for x in ['']:
                cmd = '/sbin/ethtool --offload {} {} off'.format(intf.name, x)
                self.cmd(cmd)

    def disable_ipv6(self):
        for intf in [intf_ for intf_ in self.intfs.values()]:
            cmd = 'sysctl net.ipv6.conf.{intf}.disable_ipv6=1'.format(intf=intf)
            self.cmd(cmd)


class P4RuntimeSwitch(P4Switch):

    RUNTIME_STARTUP_DELAY = 5

    def __init__(self, *args, **params):
        super(P4RuntimeSwitch, self).__init__(*args, **params)

        switch_params = params['switch_params']

        self.grpc_port = switch_params['grpc_port']

        self.runtime_file = switch_params['runtime_json'].format(self.name)

        assert self.runtime_file
        if not os.path.isfile(self.runtime_file):
            raise P4ConfigException('p4runtime file ({}) for switch {} not available'.format(self.runtime_file,
                                                                                             self.name))

        self.runtime_gRPC_log = switch_params['runtime_gRPC_log'].format(self.name, self.name)

    def wait_switch_started(self):
        for x in range(P4Switch.WAIT_STARTED_LIMIT):
            if not os.path.exists('/proc/' + str(self.sw_pid)) \
                    or not self.check_listening_on_port(self.thrift_port) \
                    or not self.check_listening_on_port(self.grpc_port):
                sleep(1)
                continue
            return True
        return False

    def build_start_cmd(self):
        cmd = super(P4RuntimeSwitch, self).build_start_cmd()

        cmd += '--grpc-server-addr {}:{} '.format(self.mgmt_ip, self.grpc_port)

        return cmd

    def configure(self):
        from p4runtime.runtimeAPI import runtime_API  # dirty for now

        sleep(P4RuntimeSwitch.RUNTIME_STARTUP_DELAY)

        with open(self.runtime_file, 'r') as runtime_conf_file:
            runtime_API.program_switch(switch_name=self.name,
                                       switch_addr='{}:{}'.format(self.mgmt_ip, self.grpc_port),
                                       device_id=self.device_id,
                                       runtime_conf_file=runtime_conf_file,
                                       p4init=self.p4init,
                                       work_dir=os.getcwd(),
                                       runtime_gRPC_log=self.runtime_gRPC_log)

        if self.p4init in ['p4runtime_CLI', 'hybrid']:
            super(P4RuntimeSwitch, self).configure()

    def _build_switch_config(self):
        super(P4RuntimeSwitch, self)._build_switch_config()
        self.switch_config.update({'runtime_json': self.runtime_file,
                                   'grpc_port': self.grpc_port,
                                   'runtime_gRPC_log': self.runtime_gRPC_log})


def check_listening_on_port(port):
    for connection in psutil.net_connections(kind='inet'):
        if connection.status == 'LISTEN' and connection.laddr[1] == port:
            return True
    return False


class P4SwitchNotStartedException(Exception):

    def __init__(self, message):
        super(P4SwitchNotStartedException, self).__init__(self.__class__.__name__ + ': ' + message)


class P4ConfigException(Exception):

    def __init__(self, message):
        super(P4ConfigException, self).__init__(self.__class__.__name__ + ': ' + message)


class P4ControllerRegisterException(Exception):

    def __init__(self, message):
        super(P4ControllerRegisterException, self).__init__(self.__class__.__name__ + ': ' + message)
