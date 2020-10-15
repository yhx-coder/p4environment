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

from abc import abstractmethod

import networkx as nx

from p4controllers.p4connector import P4Connector

from tools.log.log import log

import time

from collections import OrderedDict

import os
import shutil
import csv

from p4topos.p4topo_traffic import TrafficManager

from enum import Enum


class DataRates(Enum):
    KILOBIT = 10 ** 3
    # KIBIBIT = 2 ** 10
    MEGABIT = 10 ** 6
    # MEBIBIT = 2 ** 20
    GIGABIT = 10 ** 9
    # GIBIBIT = 2 ** 30


class TimeScales(Enum):
    SECOND = 1
    MILLISECOND = 10 ** 3
    MICROSECOND = 10 ** 6
    NANOSECOND = 10 ** 9


class PathLinkData(Enum):
    LOAD_PORT_COUNTER = 'load_port_counter'
    LOAD_PROBING = 'load_probing'
    LATENCY_PROBING = 'latency_probing'


class PathLinkCriteriaMode(Enum):
    MIN = 'min'
    MAX = 'max'


class DataSources(Enum):
    PORT_COUTER = 'port_counter'
    PROBING = 'probing'


class P4Monitor(P4Connector):
    TOPOLOGY_DATA_RATE = DataRates.MEGABIT

    P4_SWITCH_ID_TABLE = 'FlowForwardingEgress.switch_id_update_table'
    P4_SWITCH_ID_TABLE_ACTION = 'FlowForwardingEgress.write_switch_id_action'
    P4_SWITCH_ID_TABLE_ACTION_PARAM = 'switch_id'
    P4_SWITCH_ID_RULE_PATTERN = {
        'table': P4_SWITCH_ID_TABLE,
        'default_action': True,
        'action_name': P4_SWITCH_ID_TABLE_ACTION,
        'action_params': {
            P4_SWITCH_ID_TABLE_ACTION_PARAM: None
        }
    }

    def __init__(self, *args, **kwargs):
        P4Connector.__init__(self, *args, **kwargs)

        self.p4controller = None

        self.topology = nx.DiGraph()

        self.switches = list()
        self.hosts = list()

        self.monitor_flag = True

        self.timestamp_start = None

        if 'exp' in kwargs:
            self.csv_output = True
            self.exp_id = kwargs['exp']
            self.exp_iter = kwargs['exp_iter']

            self.output_files = {}
            self.csv_writer = {}
        else:
            self.csv_output = False

        self.traffic_generation_event = TrafficManager.traffic_generation_event

    def set_p4controller(self, p4controller):
        self.p4controller = p4controller

    @abstractmethod
    def run_monitor(self, *args, **kwargs):
        pass

    def stop_monitor(self):
        self.monitor_flag = False

        if self.csv_output:
            for output_file in self.output_files.values():
                output_file.close()

    def run(self, *args, **kwargs):
        self.timestamp_start = int(round(time.time()))

        self.run_monitor()

    def add_switch_connection(self, sw, sw_conf):
        super(P4Monitor, self).add_switch_connection(sw, sw_conf)
        self.add_node(sw_conf)

    def build_topology(self):
        # def _draw_topology_graph(topology):
        #     import matplotlib.pyplot as plt
        #     try:
        #         fig = plt.figure()
        #         nx.draw(topology, ax=fig.add_subplot(111), with_labels=True)
        #         fig.savefig('graph.png')
        #     except Exception as ex:
        #         print(ex)

        for sw in self.switches:
            sw_conf = self.topology.nodes[sw]
            ports = sw_conf['ports']['data_links']
            for id_, port in ports.items():
                peer = port['peer']
                if peer not in self.topology[sw]:
                    props = {'name': '{}-{}'.format(sw, peer),
                             'port_id': id_,
                             'capacity': 1.0,
                             'weight': 0.0,
                             'weight_history': OrderedDict(),
                             'load_port_counter': 0.0,
                             'load_port_counter_history': OrderedDict(),
                             'load_probing': 0.0,
                             'load_probing_history': OrderedDict(),
                             'latency_probing': 0.0,
                             'latency_probing_history': OrderedDict()}
                    props.update({x: port[x] for x in ['bw', 'delay', 'loss']})
                    self.topology.add_edge(sw, peer, **props)
                    if self.topology.nodes[peer]['type'] == 'host':
                        self.topology.add_edge(peer, sw, **props)

        # _draw_topology_graph(self.topology)

    def get_topology_graph(self):
        return self.topology

    def get_topology_graph_switches(self):
        return self.topology.subgraph(self.get_switches().keys())

    def add_node(self, node):
        node_name = node['name']
        self.topology.add_node(node_name, **node)
        if node['type'] == 'switch':
            self.switches.append(node_name)
        if node['type'] == 'host':
            self.hosts.append(node_name)

    def get_all_nodes(self):
        return self.topology.nodes.data()

    def get_node(self, node):
        return self.topology.nodes[node]

    def get_node_properties(self, node):
        return self.topology.nodes[node].keys()

    def get_node_property(self, node, node_property):
        return self.topology.nodes[node][node_property]

    def set_node_property(self, node, node_property, value):
        self.topology.nodes[node][node_property] = value

    def set_node_properties(self, node, node_properties):
        for node_property, value in node_properties.items():
            self.topology.nodes[node][node_property] = value

    def get_switch(self, switch):
        return self.get_node(switch)

    def get_switch_by_id(self, device_id):
        for switch, switch_config in self.get_switches().items():
            if int(switch_config['device_id']) == device_id:
                return switch
        return None

    def get_switches(self):
        return {switch: switch_config for switch, switch_config in self.get_all_nodes() if switch in self.switches}

    def get_switch_properties(self, switch):
        return self.get_node_properties(switch)

    def get_switch_property(self, switch, switch_property):
        return self.get_node_property(switch, switch_property)

    def set_switch_property(self, switch, switch_property, value):
        self.set_node_property(switch, switch_property, value)

    def set_switch_properties(self, switch, switch_properties):
        self.set_node_properties(switch, switch_properties)

    def get_host(self, host):
        return self.get_node(host)

    def get_hosts(self):
        return {host: host_config for host, host_config in self.get_all_nodes() if host in self.hosts}

    def get_host_properties(self, host):
        return self.get_node_properties(host)

    def get_host_property(self, host, host_property):
        return self.get_node_property(host, host_property)

    def set_host_property(self, host, host_property, value):
        self.set_node_property(host, host_property, value)

    def set_host_properties(self, host, host_properties):
        self.set_node_properties(host, host_properties)

    def add_edge(self, node1, node2, properties):
        self.topology.add_edge(node1, node2, **properties)

    def get_all_edges(self):
        return self.topology.edges.data()

    def get_all_switch_edges(self):
        return [(edge[0], edge[1], edge[2]) for edge in self.topology.edges.data()
                if edge[0] in self.switches and edge[1] in self.switches]

    def get_all_host_edges(self):
        return [(edge[0], edge[1], edge[2]) for edge in self.topology.edges.data()
                if edge[0] in self.hosts and edge[1] in self.hosts]

    def get_edges_by_node(self, node):
        return self.topology[node]

    def get_edge_by_nodes(self, node1, node2):
        return self.topology[node1][node2]

    def get_edge_property(self, node1, node2, edge_property):
        return self.topology.edges[node1, node2][edge_property]

    def get_edge_properties(self, node1, node2):
        return self.topology.edges[node1, node2]

    def set_edge_property(self, node1, node2, edge_property, value):
        self.topology[node1][node2][edge_property] = value

    def set_edge_properties(self, node1, node2, edge_properties):
        for edge_property, value in edge_properties.items():
            self.topology[node1][node2][edge_property] = value

    def update_edge_weight(self, node1, node2,
                           weight_value, weight_key=None,
                           weight_history=False, weight_timestamp=None):
        if weight_key is None:
            weight_key = 'weight'

        self.topology.edges[node1, node2][weight_key] = weight_value

        if weight_history:
            self.topology.edges[node1, node2]['weight_history'][weight_timestamp] = weight_value

    def get_edge_weight(self, node1, node2, weight_key=None, weight_history=False):
        if weight_history:
            return self.topology.edges[node1, node2]['weight_history']

        if weight_key is None:
            weight_key = 'weight'

        return self.topology.edges[node1, node2][weight_key]

    def get_edges_weight(self, weight_key=None, weight_history=False):
        if weight_history:
            return {edge[2]['name']: edge[2]['weight_history'] for edge in self.topology.edges.data()}

        if weight_key is None:
            weight_key = 'weight'

        return {edge[2]['name']: edge[2][weight_key] for edge in self.topology.edges.data()}

    def get_switch_edges_weight(self, weight_key=None, weight_history=False):
        if weight_history:
            return {edge[2]['name']: edge[2]['weight_history'] for edge in self.topology.edges.data()
                    if edge[0] in self.switches and edge[1] in self.switches}

        if weight_key is None:
            weight_key = 'weight'

        return {edge[2]['name']: edge[2][weight_key] for edge in self.topology.edges.data()
                if edge[0] in self.switches and edge[1] in self.switches}

    def update_link_property(self, sw1, sw2,
                             property_key, property_value,
                             property_history=False, property_value_timestamp=None):

        if property_key not in PathLinkData:
            return None

        property_key = property_key.value

        self.set_edge_property(sw1, sw2, property_key, property_value)

        if property_history:
            history = '{}_history'.format(property_key)
            self.topology.edges[sw1, sw2][history][property_value_timestamp] = property_value

    # get_edge_property(self, node1, node2, edge_property):
    def get_link_property(self, sw1, sw2,
                          property_key,
                          property_history=False):

        if property_key not in PathLinkData:
            return None

        property_key = property_key.value

        if property_history:
            history = '{}_history'.format(property_key)
            return self.topology.edges[sw1, sw2][history]

        return self.get_edge_property(sw1, sw2, property_key)

    def get_links_property(self, property_key, property_history=False):
        if property_history:
            history = '{}_history'.format(property_key)
            return {edge[2]['name']: edge[2][history] for edge in self.topology.edges.data()}

        return {edge[2]['name']: edge[2][property_key] for edge in self.topology.edges.data()}

    def check_neighbors(self, node1, node2):
        return node1 in self.topology[node2]

    def get_neighbors(self, node):
        return self.topology[node].keys()

    def dijkstra_path(self, node1, node2):
        return nx.dijkstra_path(self.topology, node1, node2)

    def get_shortest_path_hops(self, node1, node2):
        return nx.shortest_path(G=self.topology,
                                source=node1, target=node2,
                                weight=None,
                                method='dijkstra')

    def get_shortest_path_weight(self, node1, node2):
        return nx.shortest_path(G=self.topology,
                                source=node1, target=node2,
                                weight='weight',
                                method='dijkstra')

    def get_all_shortest_paths_hops(self, node1, node2):
        return list(nx.all_shortest_paths(G=self.topology,
                                          source=node1, target=node2,
                                          weight=None,
                                          method='dijkstra'))

    def get_shortest_path_property(self, sw1, sw2, path_property):
        if path_property not in [link_property.value for link_property in PathLinkData]:
            return None

        return nx.shortest_path(G=self.topology,
                                source=sw1, target=sw2,
                                weight=path_property,
                                method='dijkstra')

    def get_all_shortest_paths_weight(self, node1, node2):
        return list(nx.all_shortest_paths(G=self.topology,
                                          source=node1, target=node2,
                                          weight='weight',
                                          method='dijkstra'))

    def get_all_shortest_paths_property(self, sw1, sw2, path_property):
        if path_property not in [link_property.value for link_property in PathLinkData]:
            return None

        return list(nx.all_shortest_paths(G=self.topology,
                                          source=sw1, target=sw2,
                                          weight=path_property,
                                          method='dijkstra'))

    def get_all_simple_paths(self, node1, node2, depth=None):
        return list(nx.all_simple_paths(G=self.topology,
                                        source=node1, target=node2,
                                        cutoff=depth))

    def get_path_criteria(self, path, criteria, link_criteria_mode):
        path_criteria = None
        for i, sw in enumerate(path[:-1]):
            link_criteria = float(self.get_edge_property(sw, path[i + 1], criteria))
            if path_criteria is None:
                path_criteria = link_criteria
            elif link_criteria_mode == PathLinkCriteriaMode.MAX:
                if path_criteria < link_criteria:
                    path_criteria = link_criteria
            elif link_criteria_mode == PathLinkCriteriaMode.MIN:
                if path_criteria > link_criteria:
                    path_criteria = link_criteria
        return path_criteria

    def get_path_less_loaded(self, node1, node2, path_load_property):
        if path_load_property not in PathLinkData:
            return None

        paths = self.get_all_simple_paths(node1, node2)

        path_selected = None
        path_selected_load = None
        for path in paths:
            path_load = self.get_path_criteria(path[1:-1], path_load_property.value,
                                               link_criteria_mode=PathLinkCriteriaMode.MAX)
            # print('path_load', path_load)
            if path_selected is None or path_load < path_selected_load:
                path_selected = path
                path_selected_load = path_load
        return path_selected

    def get_path_pfr(self, node1, node2, path_load_property, flow_throughput, flow_throughput_unit):
        if path_load_property not in PathLinkData:
            return None

        paths = self.get_all_simple_paths(node1, node2)
        # print('paths', paths)

        path_loads = []
        path_capacities_remaining = []
        path_flow_loads = []
        feasible_paths = []

        for path in paths:
            path_capacity = self.get_path_criteria(path[1:-1], 'capacity',
                                                   link_criteria_mode=PathLinkCriteriaMode.MIN)
            # print('path_capacity', path_capacity)

            path_load = self.get_path_criteria(path[1:-1], path_load_property.value,
                                               link_criteria_mode=PathLinkCriteriaMode.MAX)
            # print('path_load', path_load)
            path_loads.append(path_load)

            path_capacity_remaining = path_capacity - path_load
            # print('path_capacity_remaining', path_capacity_remaining)
            path_capacities_remaining.append(path_capacity_remaining)

            path_bandwidth = self.get_path_criteria(path[1:-1], 'bw',
                                                    link_criteria_mode=PathLinkCriteriaMode.MIN)
            # print('path_bandwidth', path_bandwidth)

            flow_throughput_unit = getattr(DataRates, flow_throughput_unit.name)

            path_flow_load = (flow_throughput * flow_throughput_unit.value) / \
                             (path_bandwidth * self.TOPOLOGY_DATA_RATE.value)
            # print('path_flow_load', path_flow_load)
            path_flow_loads.append(path_flow_load)

            if path_flow_load < path_capacity_remaining:
                # feasible_paths.append((path, path_load))
                feasible_paths.append((path, path_capacity_remaining, path_flow_load))

        if not feasible_paths:
            max_path_capacity_remaining = max(path_capacities_remaining)
            max_path_capacity_remaining_i = path_capacities_remaining.index(max_path_capacity_remaining)
            feasible_paths.append((paths[max_path_capacity_remaining_i],
                                   path_capacities_remaining[max_path_capacity_remaining_i],
                                   path_flow_loads[max_path_capacity_remaining_i]))

            # min_load = min(path_loads)
            # min_load_i = path_loads.index(min_load)
            # feasible_paths.append((paths[min_load_i],
            #                        path_capacities_remaining[min_load_i],
            #                        path_flow_loads[min_load_i]))
        # print('feasible_paths', feasible_paths)

        feasible_paths_capacity_remaining = [path[1] for path in feasible_paths]
        max_capacity_remaining = max(feasible_paths_capacity_remaining)
        max_capacity_remaining_i = feasible_paths_capacity_remaining.index(max_capacity_remaining)
        return feasible_paths[max_capacity_remaining_i][0], feasible_paths[max_capacity_remaining_i][2]

        # feasible_paths_loads = [path[1] for path in feasible_paths]
        # min_load = min(feasible_paths_loads)
        # min_load_i = feasible_paths_loads.index(min_load)
        # return feasible_paths[min_load_i][0], feasible_paths[min_load_i][2]

    def map_ip_to_host(self, ip_address):
        for host in self.hosts:
            host_conf = self.topology.nodes[host]
            if host_conf['ip'] == ip_address:
                return host

    def map_edge_to_switch_port(self, node1, node2):
        return int(self.topology[node1][node2]['port_id'])

    def map_switch_port_to_neighbor_node(self, node, port):
        return self.topology.nodes[node]['ports']['data_links'][port]['peer']

    def _configure_switch_id_table(self):
        for p4switch, p4switch_config in self.get_switches().items():
            switch_id_rule = self.P4_SWITCH_ID_RULE_PATTERN.copy()
            switch_id_rule['action_params'][self.P4_SWITCH_ID_TABLE_ACTION_PARAM] = int(p4switch_config['device_id'])

            self.insert_table_entry(p4switch, switch_id_rule)

    def init_csv_output(self, exp_id, data_source, exp_iter):
        output_dir = os.path.join('p4monitors', 'results')
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        # else:
        #     for dir in os.listdir(output_dir):
        #         shutil.rmtree(os.path.join(output_dir, dir))

        exp_dir = os.path.join(output_dir, str(exp_id), data_source, str(exp_iter))
        try:
            os.makedirs(exp_dir)
        except:
            pass

        for edge in self.get_all_switch_edges():
            switch_link = '{}-{}'.format(edge[0], edge[1])
            output_file = os.path.join(exp_dir, '{}.csv'.format(switch_link))
            self.output_files[switch_link] = open(output_file, 'w')
            self.csv_writer[switch_link] = csv.writer(self.output_files[switch_link])
            self.csv_writer[switch_link].writerow([0, 0.0])
            self.output_files[switch_link].flush()

    def write_csv_output(self, switch_link, timestamp, load_percentage):
        self.csv_writer[switch_link].writerow([timestamp, load_percentage])
        self.output_files[switch_link].flush()

########################################################################################################################
#
# from flask import Flask, request
# import json
#
# topo_register_app = Flask(__name__)
#
#
# @topo_register_app.route('/node', methods=['POST'])
# def register_node():
#     node = json.loads(request.get_json())['node']
#     print(node)
#     return '', 200
#
#
# @topo_register_app.errorhandler(404)
# def page_not_found():
#     return "<h1>404</h1><p>BOOM</p>", 404
#
#
# if __name__ == '__main__':
#     topo_register_app.run(host='0.0.0.0', port=4221, debug=True)
