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
###############################################################################################
# basic reference: https://github.com/p4lang/tutorials/blob/master/exercises/basic/receive.py #
###############################################################################################

import sys

from scapy.all import sniff, sendp
from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, ICMP

from sendrecv_utils import get_host_interface, build_icmp_packet


def handle_icmp_packet(packet, intf):
    if ICMP in packet and packet[ICMP].type == 8:
        icmp_packet = build_icmp_packet(intf, packet[Ether].src, packet[IP].src, type=0)

        # packet.show()
        packet.show2()
        # hexdump(packet)
        sys.stdout.flush()

        sendp(icmp_packet, iface=intf)


if __name__ == '__main__':
    intf = get_host_interface()
    sniff(iface=intf, prn=lambda packet: handle_icmp_packet(packet, intf))
