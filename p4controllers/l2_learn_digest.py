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

from p4controllers.p4controller_digest import P4ControllerDigest
from p4controllers.l2_learn_stuff import L2LearnController

from tools.log.log import log

import struct


class L2LearnControllerDigest(P4ControllerDigest, L2LearnController):
    # https://docs.python.org/2.7/library/struct.html?highlight=unpack#struct.unpack
    DIGEST_SAMPLE_STRUCTURE = '>LHH'
    DIGEST_SAMPLE_LENGTH = 8  # bytes

    def __init__(self, *args, **kwargs):
        P4ControllerDigest.__init__(self, *args, **kwargs)
        L2LearnController.__init__(self, *args, **kwargs)

    def run_controller(self, *args, **kwargs):
        self._run_l2_stuff()
        self._run_digest_handler()

    def stop_controller(self, *args, **kwargs):
        self._stop_digest_handler()

    def _unpack_message_digest(self, p4switch, message, num_samples):
        digest = []
        sample_lower_limit = 0
        for sample in range(num_samples):
            sample_upper_limit = (sample + 1) * self.DIGEST_SAMPLE_LENGTH
            src_mac_part1, src_mac_part2, ingress_port = struct.unpack(self.DIGEST_SAMPLE_STRUCTURE,
                                                                       message[sample_lower_limit:sample_upper_limit])
            src_mac = (src_mac_part1 << 16) + src_mac_part2
            digest.append([src_mac, ingress_port, p4switch])
            log.info('digest contained mac_addr: {:012X}, ingress_port: {}, switch: {}'.format(src_mac, ingress_port,
                                                                                               p4switch))
            sample_lower_limit = sample_upper_limit

        return digest

    def _process_message_digest(self, message_data):
        for mac_addr, ingress_port, sw in message_data:
            if mac_addr not in self.learned_mac_src_addresses[sw]:
                log.info('mac: {:012X}, ingress_port: {} switch: {}'.format(mac_addr, ingress_port, sw))

                # runtimeCLI (thrift-API)
                self.p4switch_connections_thrift[sw].do_table_add(self.P4_TABLE_SOURCE_MATCH,
                                                                  self.P4_ACTION_SOURCE_MATCH,
                                                                  [str(mac_addr)],
                                                                  show=False)
                self.p4switch_connections_thrift[sw].do_table_add(self.P4_TABLE_DESTINATION_MATCH,
                                                                  self.P4_ACTION_DESTINATION_MATCH,
                                                                  [str(mac_addr)],
                                                                  [str(ingress_port)],
                                                                  show=False)

                self.learned_mac_src_addresses[sw][mac_addr] = ingress_port
            else:
                log.debug('mac: {:012X} already learned for port {} on {}'.format(mac_addr, ingress_port, sw))
