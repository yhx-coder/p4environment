# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
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
#################################################################################

from mininet.node import Host

import json
import requests

from tools.log.log import log


class P4Host(Host):
    IPERF_CLIENT_CMD = 'iperf -B {client_address}:{client_port} -c {server_address} -p {server_port} ' + \
                       '{protocol} -b {bandwidth}{bw_unit} -t {time}' + \
                       ' 2>&1 > /dev/null &'
    IPERF_SERVER_CMD = 'iperf -s -D -B {server_address} -p {server_port} {protocol}' + \
                       ' 2>&1 > /dev/null &'

    SSHD_START_CMD = '/usr/sbin/sshd -4 -o ListenAddress={server_address}:{port}'
    SSHD_STOP_CMD = ("ps -x | grep /usr/sbin/sshd | "
                     "grep 'ListenAddress={server_address}:{port}' | awk -F ' ' '{{print $1}}' | xargs kill -9")

    def __init__(self, *args, **params):
        super(P4Host, self).__init__(*args, **params)

        self.cmd('sysctl -w net.ipv6.conf.all.disable_ipv6=1')
        self.cmd('sysctl -w net.ipv6.conf.default.disable_ipv6=1')
        self.cmd('sysctl -w net.ipv6.conf.lo.disable_ipv6=1')

        # self.ip = params['ip']
        self.ip = params['ip'].split('/')[0]
        self.ip_with_prefix_len = params['ip']
        self.mac = params['mac']
        self.network = params['network']
        self.gw_ip = params['gw_ip']
        self.gw_mac = params['gw_mac']
        self.mgmt_ip = params['mgmt_ip'].split('/')[0]
        self.mgmt_ip_with_prefix_len = params['mgmt_ip']
        self.mgmt_mac = params['mgmt_mac']

        self.host_config = dict()
        self._build_host_config()

        self.ssh_server_started = False
        self.iperf_server_started = False

        self.disable_ipv6()

    def _build_host_config(self):
        if not self.host_config:
            self.host_config.update({'name': self.name,
                                     'type': 'host',
                                     'class': str(self.__class__.__name__),
                                     'ip': self.ip,
                                     'ip_': self.ip_with_prefix_len,
                                     'mac': self.mac,
                                     'network': self.network,
                                     'gw_ip': self.gw_ip,
                                     'gw_mac': self.gw_mac,
                                     'mgmt_ip': self.mgmt_ip,
                                     'mgmt_ip_': self.mgmt_ip_with_prefix_len,
                                     'mgmt_mac': self.mgmt_mac})

    def setARP(self, ip, mac):
        return self.cmd('arp', '-i', self.defaultIntf(), '-s', ip, mac)

    def configure(self):
        for x in ['rx', 'tx', 'sg']:
            cmd = '/sbin/ethtool --offload {} {} off'.format(self.defaultIntf().name, x)
            self.cmd(cmd)

        self.setARP(self.gw_ip, self.gw_mac)

        for command in self.params['cmd']:
            self.cmd(command)

        self._build_host_config()

    def describe(self):
        log.info('#' * 15)
        log.info('# hostname: ' + self.name)
        log.info('# host interface: ' + self.defaultIntf().name)
        log.info('# host addresses: ' + self.ip + ' | ' + self.mac)
        log.info('# gateway addresses: ' + self.gw_ip + ' | ' + self.gw_mac)
        log.info('#' * 15)

    def get_host_config(self):
        return self.host_config

    def start_services(self):
        self.start_ssh_server()

    def stop_services(self):
        self.stop_ssh_server()
        self.stop_iperf()

    def start_ssh_server(self):
        if not self.ssh_server_started:
            self.cmd(self.SSHD_START_CMD.format(server_address=self.mgmt_ip, port=22))

    def stop_ssh_server(self):
        self.cmd(self.SSHD_STOP_CMD.format(server_address=self.mgmt_ip, port=22))

    def start_iperf_client(self, client_address, client_port, server_address,
                           bandwidth, bw_unit, time, server_port=5001, protocol='-u'):
        # print(self.IPERF_CLIENT_CMD.format(client_address=client_address, client_port=client_port,
        #                                    server_address=server_address, server_port=server_port,
        #                                    protocol=protocol,
        #                                    bandwidth=bandwidth, bw_unit=bw_unit, time=time))
        self.cmd(self.IPERF_CLIENT_CMD.format(client_address=client_address, client_port=client_port,
                                              server_address=server_address, server_port=server_port,
                                              protocol=protocol,
                                              bandwidth=bandwidth, bw_unit=bw_unit, time=time))

    def start_iperf_server(self, server_address=None, server_port=5001, protocol='-u'):
        if not self.iperf_server_started:
            if not server_address:
                server_address = self.ip
            # print(self.IPERF_SERVER_CMD.format(server_address=server_address, server_port=server_port,
            #                                    protocol=protocol))
            self.cmd(self.IPERF_SERVER_CMD.format(server_address=server_address, server_port=server_port,
                                                  protocol=protocol))
            self.iperf_server_started = True

    def stop_iperf(self):
        self.cmd('pkill -9 iperf')

    def register_controller(self, controller_address):
        try:
            response = requests.post(url='http://{}/node'.format(controller_address),
                                     json=json.dumps(self.host_config))
            log.info('register host config ({}): {}\n'.format(self.name, response))
        except requests.exceptions.ConnectionError as ex:
            log.warn(ex)
            log.warn('unable to register host config ({})\n'.format(self.name))
            # raise P4ControllerRegisterException('unable to register host config ({})\n'.format(self.name))

    def disable_ipv6(self):
        for intf in [intf_ for intf_ in self.intfs.values()]:
            cmd = 'sysctl net.ipv6.conf.{intf}.disable_ipv6=1'.format(intf=intf)
            self.cmd(cmd)
