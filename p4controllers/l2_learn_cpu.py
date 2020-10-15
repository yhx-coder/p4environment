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
#
######################################################################################################
# adapted from nsg-ethz/p4-learning and P4 Tutorials                                                 #
# see https://github.com/nsg-ethz/p4-learning/tree/master/examples/04-L2_Learning                    #
# see https://github.com/p4lang/tutorials/blob/master/exercises/p4runtime/solution/mycontroller.py   #
######################################################################################################

from p4controllers.p4controller_cpu import P4ControllerCPU
from p4controllers.l2_learn_stuff import L2LearnController

from tools.log.log import log

from scapy.all import Packet, BitField
from scapy.layers.l2 import Ether


class CPUHeader(Packet):
    name = 'CPUPacket'
    fields_desc = [BitField('mac_addr', 0, 48), BitField('ingress_port', 0, 16)]


class L2LearnControllerCPU(P4ControllerCPU, L2LearnController):
    L2_LEARN_ETHERTYPE = 0x4221

    def __init__(self, *args, **kwargs):
        P4ControllerCPU.__init__(self, *args, **kwargs)
        L2LearnController.__init__(self, *args, **kwargs)

    def run_controller(self, *args, **kwargs):
        self._run_l2_stuff()
        self._run_cpu_port_handler(sniff_filter=None)

    def stop_controller(self, *args, **kwargs):
        self._stop_cpu_port_handler()

    def _handle_cpu_packet(self, cpu_packet):
        # cpu_packet.show2()

        packet = Ether(str(cpu_packet))

        if packet.type == self.L2_LEARN_ETHERTYPE:
            cpu_header = CPUHeader(str(packet.payload))
            p4switch = cpu_packet.sniffed_on.split('-')[1]
            self._process_cpu_packet([(cpu_header.mac_addr, cpu_header.ingress_port, p4switch)])

    def _process_cpu_packet(self, data):
        for mac_addr, ingress_port, sw in data:
            if mac_addr not in self.learned_mac_src_addresses[sw]:
                log.info('mac: %012X ingress_port: %s switch: %s' % (mac_addr, ingress_port, sw))

                # runtimeAPI (gRPC-API)
                str_mac_addr = hex(mac_addr)[2:]
                str_mac_addr = ':'.join(str_mac_addr[i:i + 2] for i in range(0, 12, 2))

                source_entry = dict()
                source_entry['table'] = self.P4_TABLE_SOURCE_MATCH
                source_entry['action_name'] = self.P4_ACTION_SOURCE_MATCH
                source_entry['match'] = dict()
                source_entry['match'][self.P4_MATCH_SOURCE_MATCH] = str_mac_addr
                source_entry['action_params'] = dict()

                self.insert_table_entry(sw, source_entry)

                destination_entry = dict()
                destination_entry['table'] = self.P4_TABLE_DESTINATION_MATCH
                destination_entry['action_name'] = self.P4_ACTION_DESTINATION_MATCH
                destination_entry['match'] = dict()
                destination_entry['match'][self.P4_MATCH_DESTINATION_MATCH] = str_mac_addr
                destination_entry['action_params'] = dict()
                destination_entry['action_params']['port'] = int(ingress_port)

                self.insert_table_entry(sw, destination_entry)

                # runtimeCLI (thrift-API)
                # self.p4switch_connections_thrift[sw].do_table_add(self.P4_TABLE_SOURCE_MATCH,
                #                                                   self.P4_ACTION_SOURCE_MATCH,
                #                                                   [str(mac_addr)],
                #                                                   show=False)
                # self.p4switch_connections_thrift[sw].do_table_add(self.P4_TABLE_DESTINATION_MATCH,
                #                                                   self.P4_ACTION_DESTINATION_MATCH,
                #                                                   [str(mac_addr)],
                #                                                   [str(ingress_port)],
                #                                                   show=False)

                self.learned_mac_src_addresses[sw][mac_addr] = ingress_port
            else:
                log.debug('mac: %012X already learned for port %s on %s' % (mac_addr, ingress_port, sw))
