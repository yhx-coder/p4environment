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

from mininet.node import OVSSwitch
from mininet.topo import Topo
from mininet.link import TCIntf

from p4nodes.p4host import P4Host
from p4nodes.p4switch import P4Switch, P4RuntimeSwitch

from p4programs.p4compiler import P4Compiler
from p4topos.p4topo_params import TopologyParameter


class P4Topo(Topo):

    def __init__(self, topology_json, *args, **params):
        Topo.__init__(self, *args, **params)

        root_host = self.addHost(topology_json['management']['host']['name'],
                                 inNamespace=False, ip=None, mac=None)
        root_switch_switches = self.addSwitch(topology_json['management']['switch']['switches']['name'],
                                              dpid='254', cls=OVSSwitch)
        root_switch_hosts = self.addSwitch(topology_json['management']['switch']['hosts']['name'],
                                           dpid='253', cls=OVSSwitch)

        self.addLink(root_host, root_switch_switches,
                     intfName1=root_host + '-' + root_switch_switches,
                     intfName2=root_switch_switches + '-' + root_host,
                     addr1=topology_json['management']['host']['mac_switches'],
                     params1={'ip': topology_json['management']['host']['ip_switches']})

        self.addLink(root_host, root_switch_hosts,
                     intfName1=root_host + '-' + root_switch_hosts,
                     intfName2=root_switch_hosts + '-' + root_host,
                     addr1=topology_json['management']['host']['mac_hosts'],
                     params1={'ip': topology_json['management']['host']['ip_hosts']})

        host_class = eval(topology_json['host_class'])
        for host, hparams in topology_json['hosts'].items():
            self.addHost(host,
                         cls=host_class,
                         ip=hparams['ip'],
                         mac=hparams['mac'],
                         network=hparams['network'],
                         gw_ip=hparams['gw_ip'],
                         gw_mac=hparams['gw_mac'],
                         defaultRoute='via ' + hparams['gw_ip'].format(hparams['num']),
                         mgmt_ip=hparams['mgmt_ip'],
                         mgmt_mac=hparams['mgmt_mac'],
                         cmd=hparams['cmd'])

            self.addLink(host, root_switch_hosts,
                         intfName1=host + '-' + root_switch_hosts,
                         intfName2=root_switch_hosts + '-' + host,
                         port1=2,
                         addr1=hparams['mgmt_mac'],
                         params1={'ip': hparams['mgmt_ip']})

        switch_class = eval(topology_json['switch_class'])
        tp = TopologyParameter.get_topology_params()
        for switch, switch_params in topology_json['switches'].items():
            p4app = switch_params['p4program']
            if p4app != tp.P4_PROGRAM:
                P4Compiler.compile_p4program(tp.P4_BUILD_DIR_PATH.format(p4app=p4app),
                                             tp.P4_BMV2_JSON_FILE_PATH.format(p4app=p4app),
                                             tp.P4_INFO_FILE_PATH.format(p4app=p4app),
                                             tp.P4_PROGRAM_PATH.format(p4app=p4app),
                                             p4app)

            self.addSwitch(switch,
                           cls=switch_class,
                           dpid=str(switch_params['num']),
                           inNamespace=True,
                           switch_params=switch_params)

            self.addLink(switch, root_switch_switches,
                         port1=9999,
                         intfName1=switch + '-' + root_switch_switches,
                         intfName2=root_switch_switches + '-' + switch)

        for hlink in topology_json['links']['host_links']:
            host_name = hlink['host']
            switch_name = hlink['switch']['name']

            self.addLink(host_name, switch_name,
                         cls1=TCIntf,
                         cls2=TCIntf,
                         intfName1=host_name + '-' + switch_name,
                         intfName2=switch_name + '-' + host_name,
                         addr1=self.g.node[host_name]['mac'],
                         port1=1,
                         port2=hlink['switch']['port'],
                         bw=hlink['bw'],
                         delay=hlink['delay'],
                         loss=hlink['loss'],
                         params1={'ip': self.g.node[host_name]['ip']})

            for i, cmd in enumerate(self.g.node[hlink['host']]['cmd']):
                self.g.node[hlink['host']]['cmd'][i] = cmd.format(intf=hlink['host'] + '-' + hlink['switch']['name'])

        for slink in topology_json['links']['switch_links']:
            switch1_name = slink['switch1']['name']
            switch2_name = slink['switch2']['name']
            self.addLink(switch1_name, switch2_name,
                         cls1=TCIntf,
                         cls2=TCIntf,
                         intfName1=switch1_name + '-' + switch2_name,
                         intfName2=switch2_name + '-' + switch1_name,
                         port1=slink['switch1']['port'],
                         port2=slink['switch2']['port'],
                         bw=slink['bw'],
                         bw_scale=slink['bw_scale'],
                         delay=slink['delay'],
                         loss=slink['loss'])
