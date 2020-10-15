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
# Part of the publication "Prediction-based Flow Routing in Programmable Networks with P4" accepted as
# short paper and poster at the 16th International Conference on Network and Service Management (CNSM) 2020.

from time import sleep, time

from enum import Enum

from p4monitors.p4monitor import P4Monitor, DataSources, PathLinkData


class CounterDirection(Enum):
    RX_PORT_COUNTER = 'rx_port_counter'
    TX_PORT_COUNTER = 'tx_port_counter'


class CounterData(Enum):
    PACKET_COUNT = 'packet_count'
    BYTE_COUNT = 'byte_count'


class PortCounterMonitor(P4Monitor):
    PORT_COUNTER_INDEX_OFFSET = 1

    def __init__(self, *args, **kwargs):
        P4Monitor.__init__(self, *args, **kwargs)

        self.counter_collection_interval = kwargs['p4monitor_counter_interval']
        self.counter = CounterDirection(kwargs['p4monitor_counter_direction'])
        self.counter_data = CounterData(kwargs['p4monitor_counter_data'])

        self.port_counters = {}

    def run_monitor(self, *args, **kwargs):
        for sw in self.switches:
            # sw_conf = self.topology.nodes[sw]
            self.port_counters[sw] = dict()
            for edge in [x for x in self.topology.edges.data() if x[0] == sw and x[1] in self.switches]:
                # both counters are collected (tx and rx)
                self.port_counters[sw][edge[2]['port_id']] = dict()
                for counter in [counter.value for counter in CounterDirection]:
                    self.port_counters[sw][edge[2]['port_id']][counter] = list()

                # only the selected counter is collected (tx or rx)
                # self.port_counters[sw][edge[2]['port_id']] = list()

        if self.csv_output:
            self.init_csv_output(self.exp_id, DataSources.PORT_COUTER.value, self.exp_iter)

        monitoring_i = 0

        sleep(self.counter_collection_interval)
        while self.monitor_flag:
            for sw in self.switches:
                for edge in [x for x in self.topology.edges.data() if x[0] == sw and x[1] in self.switches]:
                    local_port_id = edge[2]['port_id']

                    for counter in [counter.value for counter in CounterDirection]:
                        # there is only one counter, consider index offset (port 0 not used)
                        counters = self.get_counters(sw, counter,
                                                     index=local_port_id - self.PORT_COUNTER_INDEX_OFFSET)[0]

                        byte_count = float(counters.data.byte_count)
                        # print('byte_count', byte_count)

                        packet_count = float(counters.data.packet_count)
                        # print('packet_count', packet_count)

                        if counter == self.counter.value:
                            if self.counter_data == CounterData.BYTE_COUNT:  # byte_count

                                if len(self.port_counters[sw][local_port_id][counter]) != 0:
                                    last_byte_count = self.port_counters[sw][local_port_id][counter][-1] \
                                        [CounterData.BYTE_COUNT]
                                else:
                                    last_byte_count = 0
                                # print('last_byte_count', last_byte_count)

                                byte_diff = byte_count - last_byte_count
                                # print('byte_diff', byte_diff)

                                link_load = byte_diff * 8
                                link_load /= self.counter_collection_interval
                                # print('link_load', link_load)

                                # link_capacity = 1.0 * self.TOPOLOGY_DATA_RATE
                                link_capacity = float(edge[2]['bw']) * self.TOPOLOGY_DATA_RATE.value
                                # print('link_capacity', link_capacity)

                                load_percentage = link_load / link_capacity
                                # print('load_percentage', load_percentage)
                                # if load_percentage > 0: print('load_percentage', load_percentage)

                                timestamp = int(round(time())) - self.timestamp_start
                                switch = edge[0]
                                switch_neighbor = edge[1]

                                # self.update_edge_weight(node1=edge[0], node2=edge[1],
                                #                         weight_key='load_port_counter', weight_value=load_percentage)
                                # self.update_edge_weight(node1=switch, node2=switch_neighbor,
                                #                         weight_value=load_percentage,
                                #                         weight_history=True,
                                #                         weight_timestamp=timestamp)
                                self.update_link_property(sw1=switch, sw2=switch_neighbor,
                                                          property_key=PathLinkData.LOAD_PORT_COUNTER,
                                                          property_value=load_percentage,
                                                          property_history=True,
                                                          property_value_timestamp=timestamp)

                                if self.csv_output:
                                    self.write_csv_output(switch_link='{}-{}'.format(switch, switch_neighbor),
                                                          timestamp=timestamp, load_percentage=load_percentage)

                            if self.counter_data == CounterData.PACKET_COUNT:  # packet_count
                                pass

                        self.port_counters[sw][local_port_id][counter].append({CounterData.PACKET_COUNT: packet_count,
                                                                               CounterData.BYTE_COUNT: byte_count})

            monitoring_i += 1

            self.traffic_generation_event.set()

            sleep(self.counter_collection_interval)
