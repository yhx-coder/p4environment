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

from tools.log.log import log

from abc import abstractmethod

from p4controllers.p4connector import P4Connector


class P4Controller(P4Connector):

    def __init__(self, *args, **kwargs):
        P4Connector.__init__(self, *args, **kwargs)

        self.p4monitor = None

    def set_p4monitor(self, p4monitor):
        self.p4monitor = p4monitor

    @abstractmethod
    def run_controller(self, *args, **kwargs):
        pass

    def run(self, *args, **kwargs):
        # for p4switch in self.p4switch_configurations:
        #     self.p4switch_connections_thrift[p4switch].do_reset_state()

        self.run_controller(*args, **kwargs)

    @abstractmethod
    def stop_controller(self, *args, **kwargs):
        pass

    def add_switch_connection(self, sw, sw_conf):
        _, switch_connection_grpc = super(P4Controller, self).add_switch_connection(sw, sw_conf)
        if switch_connection_grpc:
            switch_connection_grpc.master_arbitration_update()

        self.p4switch_configurations[sw] = sw_conf
