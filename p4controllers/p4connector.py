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
################################################################################################
# adapted from P4 language tutorials                                                           #
# see https://github.com/p4lang/tutorials/blob/master/utils/p4runtime_lib/simple_controller.py #
################################################################################################

import threading

from p4runtime.runtimeAPI import helper as p4info_help, switch, runtime_API
from p4runtime.runtimeCLI import runtime_CLI
from p4runtime.runtimeCLI import simple_switch_API

from tools.log.log import log


class P4Connector(threading.Thread):

    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self)

        self.p4switch_configurations = dict()

        self.p4switch_connections_gRPC = dict()  # runtimeAPI
        self.p4switch_connections_thrift = dict()  # runtimeCLI
        self.p4switch_p4info_helper = dict()

    def add_switch_connection(self, sw, sw_conf):
        # runtimeCLI
        # p4switch_connection_thrift = runtime_CLI.RuntimeAPI(sw_conf['mgmt_ip'], sw_conf['thrift_port'])
        p4switch_connection_thrift = simple_switch_API.SimpleSwitchAPI(sw_conf['mgmt_ip'], sw_conf['thrift_port'],
                                                                       sw, sw_conf['runtime_thrift_log'])
        self.p4switch_connections_thrift[sw] = p4switch_connection_thrift

        p4switch_connection_grpc = None
        if sw_conf['class'] == 'P4RuntimeSwitch':  # runtimeAPI
            sw_grpc_server_addr = '{}:{}'.format(sw_conf['mgmt_ip'], sw_conf['grpc_port'])
            if sw not in self.p4switch_connections_gRPC:
                p4switch_connection_grpc = switch.Bmv2SwitchConnection(switch_addr=sw_grpc_server_addr,
                                                                       device_id=sw_conf['device_id'],
                                                                       runtime_gRPC_log=sw_conf['runtime_gRPC_log'],
                                                                       name=sw)
                self.p4switch_connections_gRPC[sw] = p4switch_connection_grpc
            if sw not in self.p4switch_p4info_helper:
                self.p4switch_p4info_helper[sw] = p4info_help.P4InfoHelper(sw_conf['bmv2_p4info'])

        return p4switch_connection_thrift, p4switch_connection_grpc

    def shutdown_switch_connections(self):
        for p4switch_connection in self.p4switch_connections_gRPC.values():
            p4switch_connection.shutdown()

    def insert_table_entry(self, p4switch_name, flow):
        runtime_API.insert_table_entry(self.p4switch_connections_gRPC[p4switch_name],
                                       self.p4switch_p4info_helper[p4switch_name], flow)

    def delete_table_entry(self, p4switch_name, flow):
        runtime_API.delete_table_entry(self.p4switch_connections_gRPC[p4switch_name],
                                       self.p4switch_p4info_helper[p4switch_name], flow)

    def insert_multicast_group_entry(self, p4switch_name, rule):
        runtime_API.insert_multicast_group_entry(self.p4switch_connections_gRPC[p4switch_name],
                                                 self.p4switch_p4info_helper[p4switch_name], rule)

    def delete_multicast_group_entry(self, p4switch_name, rule):
        runtime_API.delete_multicast_group_entry(self.p4switch_connections_gRPC[p4switch_name],
                                                 self.p4switch_p4info_helper[p4switch_name], rule)

    def get_table_entries(self, p4switch_name, table_name, show=False):
        table_entries = runtime_API.get_table_entries(self.p4switch_connections_gRPC[p4switch_name],
                                                      self.p4switch_p4info_helper[p4switch_name], table_name)
        if show:
            print(table_entries)
        return table_entries

    def get_counters(self, p4switch_name, counter_name, index=None, show=False):
        counters = runtime_API.get_counters(self.p4switch_connections_gRPC[p4switch_name],
                                            self.p4switch_p4info_helper[p4switch_name],
                                            counter_name, index)
        if show:
            print(counters)
        return counters
