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


class L2LearnController(object):
    P4_TABLE_DESTINATION_MATCH = 'MyIngress.ethernet_dst_match_table'
    P4_TABLE_SOURCE_MATCH = 'MyIngress.ethernet_src_match_table'
    P4_MATCH_DESTINATION_MATCH = 'hdr.ethernet.dst_addr'
    P4_MATCH_SOURCE_MATCH = 'hdr.ethernet.src_addr'
    P4_ACTION_DESTINATION_MATCH = 'MyIngress.to_port_action'
    P4_ACTION_SOURCE_MATCH = 'NoAction'

    P4_TABLE_BROADCAST = 'MyIngress.broadcast_table'
    P4_ACTION_BROADCAST = 'MyIngress.set_multicast_group'

    def __init__(self, *args, **kwargs):
        self.learned_mac_src_addresses = dict()

    # noinspection PyUnresolvedReferences
    def _run_l2_stuff(self):
        for p4switch in self.p4switch_configurations:
            self.learned_mac_src_addresses[p4switch] = dict()

        self._add_multicast_groups()

    # noinspection PyUnresolvedReferences
    def _add_multicast_groups(self):
        for sw, sw_config in self.p4switch_configurations.items():
            multicast_group_id = 1
            rid = 0

            sw_connection = self.p4switch_connections_thrift[sw]
            port_ids = [port_id for port_id in sw_config['ports']['data_links']]
            for port_id in port_ids:
                port_ids_ = [int(port_id_) for port_id_ in port_ids if port_id_ != port_id]

                sw_connection.do_mc_mgrp_create(multicast_group_id)

                mgrp_handle = sw_connection.do_mc_node_create(rid, port_ids_)

                sw_connection.do_mc_node_associate(multicast_group_id, mgrp_handle)

                sw_connection.do_table_add(self.P4_TABLE_BROADCAST, self.P4_ACTION_BROADCAST,
                                           [str(port_id)], [str(multicast_group_id)], show=False)

                multicast_group_id += 1
                rid += 1
