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

import re
import subprocess

from scapy.all import get_if_list, get_if_addr, get_if_hwaddr, hexdump
from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, IPOption, ICMP, UDP
from scapy.layers.inet import _IPOption_HDR

from scapy.all import Packet, FieldLenField, ShortField, PacketListField, BitField


def get_arp_table(interface):
    arp_table = {}

    arp_output = subprocess.check_output(['arp -n -i {}'.format(interface) + " | awk '{print $1,$3}'"], shell=True)
    arp_output = arp_output.split('\n')[1:-1]  # skip head and bottom line

    for entry in arp_output:
        ip, mac = entry.split(' ', 1)
        arp_table[ip] = mac

    return arp_table


def get_host_interface():
    intfs = get_if_list()

    for intf in intfs:
        if re.match('h[0-9]+-s[0-9]+', intf):
            return intf


def build_packet(dst_ip, message):
    intf = get_host_interface()
    arp_table = get_arp_table(intf)

    packet = Ether(src=get_if_hwaddr(intf), dst=arp_table[dst_ip])
    packet = packet / IP(src=get_if_addr(intf), dst=dst_ip) / UDP(dport=42, sport=21) / message

    # packet.show2()
    # hexdump(packet)

    return packet, intf


def build_icmp_packet(intf, dst_mac, dst_ip, type):
    icmp_packet = Ether(src=get_if_hwaddr(intf), dst=dst_mac)
    icmp_packet = icmp_packet / IP(src=get_if_addr(intf), dst=dst_ip) / ICMP(type=type)

    # icmp_packet.show2()
    # hexdump(icmp_packet)

    return icmp_packet


class INTData(Packet):
    name = 'INTData'
    fields_desc = [BitField('switch_id', 0, 8),
                   BitField('egress_port', 0, 8),
                   BitField('timestamp', 0, 48)]


class IPOptionINT(IPOption):
    name = "INT"
    option = 31
    fields_desc = [_IPOption_HDR,
                   FieldLenField('length', None, fmt='B',
                                 length_of='int_headers',
                                 adjust=lambda pkt, l: l * 2 + 4),
                   ShortField('count', 0),
                   PacketListField('int_headers',
                                   [],
                                   INTData,
                                   count_from=lambda pkt: (pkt.count * 1))]


def build_INT_packet(intf, dst_mac, dst_ip, message):
    INT_packet = Ether(src=get_if_hwaddr(intf), dst=dst_mac)
    INT_packet = INT_packet / IP(src=get_if_addr(intf), dst=dst_ip, options=IPOptionINT(count=0, int_headers=[]))
    INT_packet = INT_packet / UDP(dport=42, sport=21) / message

    # INT_packet.show2()
    # hexdump(INT_packet)

    return INT_packet
