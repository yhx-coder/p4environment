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
############################################################################################
# basic reference: https://github.com/p4lang/tutorials/blob/master/exercises/basic/send.py #
############################################################################################

import sys

import socket

from scapy.all import sendp

from sendrecv_utils import build_packet

from time import sleep

if __name__ == '__main__':
    # dst_ip = socket.gethostbyname(sys.argv[1])
    dst_ip = sys.argv[1]
    message = sys.argv[2]
    num_messages = int(sys.argv[3])

    packet, intf = build_packet(dst_ip, message)
    # packet.show2()
    sendp(packet, iface=intf, count=num_messages)

    # try:
    #     for i in range(num_messages):
    #         sendp(packet, iface=intf)
    #         sleep(1)
    # except KeyboardInterrupt:
    #     raise
