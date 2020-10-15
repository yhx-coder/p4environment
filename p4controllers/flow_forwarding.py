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

from p4controllers.p4controller_cpu import P4ControllerCPU

from scapy.all import sendp, sendpfast, Packet, BitField, bind_layers
from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, TCP, UDP

from itertools import product

from tools.log.log import log

from enum import Enum

import time
from functools import wraps
import numpy as np

import hashlib

from p4monitors.p4monitor import PathLinkData, TimeScales

import os
import csv


# https://stackoverflow.com/questions/5929107/decorators-with-parameters
def time_measure_factory(measurement):
    def time_measure(function):
        @wraps(function)
        def wrapper(self, *args, **kwargs):
            if not self.time_measurement:
                return function(*args, **kwargs)

            start_timestamp = time.time()
            function_result = function(*args, **kwargs)
            stop_timestamp = time.time()
            elapsed_time = int(round((stop_timestamp - start_timestamp) * TimeScales.MILLISECOND.value))
            self.times[measurement.value].append(elapsed_time)
            return function_result

        return wrapper

    return time_measure


class FlowForwardingStrategy(Enum):
    SHORTEST_PATH = 'shortest_path'
    ECMP = 'ecmp'
    PATH_PROPERTY = 'path_property'
    FLOW_PREDICTION = 'flow_prediction'


class ShortestPathMetrics(Enum):
    HOPS = 'hops'
    BANDWIDTH = 'bw'
    LOAD_PORT_COUNTER = 'load_port_counter'
    LOAD_PROBING = 'load_probing'
    LATENCY_PROBING = 'latency_probing'


class ECMPMetrics(Enum):
    HASH = 'hash'
    ROUND_ROBIN = 'round_robin'
    RANDOM = 'random'


class PathMetrics(Enum):
    LOAD_PORT_COUNTER = 'load_port_counter'
    LOAD_PROBING = 'load_probing'
    LATENCY_PROBING = 'latency_probing'
    COMBINED = 'combined'


class FlowPredictionMetrics(Enum):
    THROUGHPUT = 'throughput'
    DURATION = 'duration'
    BYTES = 'bytes'
    COMBINED = 'combined'  # bytes and duration => throughput


mapping_flow_routing_strategy_and_metric = {'shortest_path': ShortestPathMetrics,
                                            'ecmp': ECMPMetrics,
                                            'path_property': PathMetrics,
                                            'flow_prediction': FlowPredictionMetrics}


def check_mapping_flow_routing_strategy_and_metric(strategy, metric):
    for strategy_, metrics_ in mapping_flow_routing_strategy_and_metric.items():
        if strategy_ == strategy:
            if metric not in [metric_.value for metric_ in metrics_]:
                raise P4FlowForwardingMappingException('no valid mapping between specified flow forwarding strategy '
                                                       'and metric found (strategy: {}| metric: {})'.format(strategy,
                                                                                                            metric))
            break


class TimeMeasurements(Enum):
    FLOW_FORWARDING = 'flow_forwarding'
    PACKET_DISASSEMBLY = 'packet_disassembly'
    PATH_DETERMINATION = 'path_determination'
    PATH_PROGRAMMING = 'path_programming'
    PACKET_REASSEMBLY = 'packet_reassembly'
    PACKET_SENDING = 'packet_sending'


class CPUHeader(Packet):
    name = 'CPUPacket'
    fields_desc = [BitField('ingress_port', 0, 8),
                   BitField('flow_hash_one', 0, 16),
                   BitField('flow_hash_two', 0, 32),
                   BitField('ecmp_result', 0, 8)]


bind_layers(TCP, CPUHeader)
bind_layers(UDP, CPUHeader)


class FlowForwardingController(P4ControllerCPU):
    ETHERTYPE_IPV4 = 0x800
    SNIFF_FILTER = 'ether proto {}'.format(ETHERTYPE_IPV4)

    P4_CONTROLLER_PACKET_SRC_MAC = '99:99:99:99:99:99'

    P4_ECMP_RESULT_TABLE = 'FlowForwardingIngress.ecmp_result_computation_table'
    P4_ECMP_RESULT_ACTION = 'FlowForwardingIngress.compute_ecmp_result_action'
    P4_ECMP_RESULT_ACTION_PARAM1 = 'ecmp_base'
    P4_ECMP_RESULT_ACTION_PARAM2 = 'ecmp_count'
    P4_ECMP_RESULT_RULE_PATTERN = {
        'table': P4_ECMP_RESULT_TABLE,
        'default_action': True,
        'action_name': P4_ECMP_RESULT_ACTION,
        'action_params': {
            P4_ECMP_RESULT_ACTION_PARAM1: None,
            P4_ECMP_RESULT_ACTION_PARAM2: None
        }
    }

    P4_FORWARDING_TABLE = 'FlowForwardingIngress.flow_forwarding_table'
    P4_FORWARDING_MATCH1 = 'meta.flow_hash_one'
    P4_FORWARDING_MATCH2 = 'meta.flow_hash_two'
    P4_FORWARDING_MATCH1_BIT_WIDTH = 16
    P4_FORWARDING_MATCH2_BIT_WIDTH = 32
    P4_FORWARDING_MATCH1_NUM_ELEMENTS = P4_FORWARDING_MATCH1_BIT_WIDTH / 4
    P4_FORWARDING_MATCH2_NUM_ELEMENTS = P4_FORWARDING_MATCH2_BIT_WIDTH / 4
    P4_FORWARDING_ACTION = 'FlowForwardingIngress.to_port_action'
    P4_FORWARDING_ACTION_PARAM = 'port'
    P4_FORWARDING_RULE_PATTERN = {
        'table': P4_FORWARDING_TABLE,
        'match': {
            P4_FORWARDING_MATCH1: None,
            P4_FORWARDING_MATCH2: None
        },
        'action_name': P4_FORWARDING_ACTION,
        'action_params': {
            P4_FORWARDING_ACTION_PARAM: None
        }
    }

    P4_NEXTHOP_UPDATE_TABLE = 'FlowForwardingIngress.nexthop_mac_update_table'
    P4_NEXTHOP_UPDATE_MATCH = 'standard_metadata.egress_spec'
    P4_NEXTHOP_UPDATE_ACTION = 'FlowForwardingIngress.update_nexthop_mac_action'
    P4_NEXTHOP_UPDATE_ACTION_PARAM = 'nexthop_mac'
    P4_NEXTHOP_UPDATE_RULE_PATTERN = {
        'table': P4_NEXTHOP_UPDATE_TABLE,
        'match': {
            P4_NEXTHOP_UPDATE_MATCH: None
        },
        'action_name': P4_NEXTHOP_UPDATE_ACTION,
        'action_params': {
            P4_NEXTHOP_UPDATE_ACTION_PARAM: None
        }
    }

    P4_SOURCE_UPDATE_TABLE = 'FlowForwardingIngress.source_mac_update_table'
    P4_SOURCE_UPDATE_ACTION = 'FlowForwardingIngress.update_source_mac_action'
    P4_SOURCE_UPDATE_ACTION_PARAM = 'source_mac'
    P4_SOURCE_UPDATE_RULE_PATTERN = {
        'table': P4_SOURCE_UPDATE_TABLE,
        'default_action': True,
        'action_name': P4_SOURCE_UPDATE_ACTION,
        'action_params': {
            P4_SOURCE_UPDATE_ACTION_PARAM: None
        }
    }

    P4_ICMP_TABLE = 'FlowForwardingIngress.icmp_forwarding_table'
    P4_ICMP_MATCH_SRC_ADDR = 'hdr.ipv4.src_addr'
    P4_ICMP_MATCH_DST_ADDR = 'hdr.ipv4.dst_addr'
    P4_ICMP_ACTION = 'FlowForwardingIngress.to_port_action'
    P4_ICMP_ACTION_PARAM = 'port'
    P4_ICMP_RULE_PATTERN = {
        'table': P4_ICMP_TABLE,
        'match': {
            P4_ICMP_MATCH_SRC_ADDR: None,
            P4_ICMP_MATCH_DST_ADDR: None
        },
        'action_name': P4_ICMP_ACTION,
        'action_params': {
            P4_ICMP_ACTION_PARAM: None
        }
    }

    def __init__(self, *args, **kwargs):
        P4ControllerCPU.__init__(self, *args, **kwargs)

        self.flow_hashes = []

        self.forwarding_rules = dict()

        self.p4switches = None
        self.p4hosts = None

        self.traffic_manager = None

        strategy = kwargs['flow_forwarding_strategy']
        metric = kwargs['flow_forwarding_metric']
        check_mapping_flow_routing_strategy_and_metric(strategy=strategy, metric=metric)
        self.flow_forwarding_strategy = FlowForwardingStrategy(strategy)
        self.flow_forwarding_metric = mapping_flow_routing_strategy_and_metric[strategy](metric)

        self.time_measurement = kwargs['time_measurement']

        if self.time_measurement:
            self.times = {measurement.value: [] for measurement in TimeMeasurements}

        # ECMP flow hash
        # ecmp_base is 2 because port id 0 is not used and port id 1 belongs to the associated host network
        self.ecmp_base = 2
        self.ecmp_count = {}  # only used for ECMP "edge" switches
        # ECMP round robin
        self.round_robin_i = dict()
        # ECMP random
        self.np_random = np.random.RandomState(seed=42)

        if 'exp' in kwargs:
            self.csv_output = True
            self.exp_id = kwargs['exp']
            self.exp_iter = kwargs['exp_iter']

            self.output_file = None
            self.csv_writer = None
        else:
            self.csv_output = False

    def set_traffic_manager(self, traffic_manager):
        self.traffic_manager = traffic_manager

    def run_controller(self, *args, **kwargs):
        super(FlowForwardingController, self)._run_cpu_port_handler(sniff_filter=self.SNIFF_FILTER)

        self.p4switches = self.p4monitor.get_switches()
        self.p4hosts = self.p4monitor.get_hosts()

        for p4switch, p4switch_config in self.p4switches.items():
            self.round_robin_i[p4switch] = 0

            self.forwarding_rules[p4switch] = dict()

            # ecmp_count is the maximum port id - 1; this assumes that all other ports (>= 2) are considered for ECMP;
            # while this is sufficient for determining an ECMP decision at an "edge" switch, a more sophisticated
            # solution for supporting ECMP decisions at "intermediate" switches is required
            ecmp_count = max(p4switch_config['ports']['data_links'].keys()) - 1
            self._configure_ecmp_result_table(p4switch, ecmp_base=self.ecmp_base, ecmp_count=ecmp_count)
            self.ecmp_count[p4switch] = ecmp_count

            for port_id, port_params in p4switch_config['ports']['data_links'].items():
                nexthop = port_params['peer']
                nexthop_mac = None
                if nexthop in self.p4switches:
                    nexthop_mac = self.p4switches[nexthop]['mgmt_mac']
                if nexthop in self.p4hosts:
                    nexthop_mac = self.p4hosts[nexthop]['mac']
                self._configure_nexthop_update_table(p4switch, int(port_id), nexthop_mac)

            self._configure_source_update_table(p4switch, p4switch_config['mgmt_mac'])

        self._program_icmp_paths()

        if self.csv_output:
            self.init_csv_output(self.exp_id, self.exp_iter)

    def stop_controller(self, *args, **kwargs):
        super(FlowForwardingController, self)._stop_cpu_port_handler()

        if self.csv_output:
            self.write_csv_output([np.mean(self.times[TimeMeasurements.FLOW_FORWARDING.value]),
                                   np.median(self.times[TimeMeasurements.FLOW_FORWARDING.value]),
                                   np.mean(self.times[TimeMeasurements.PACKET_DISASSEMBLY.value]),
                                   np.median(self.times[TimeMeasurements.PACKET_DISASSEMBLY.value]),
                                   np.mean(self.times[TimeMeasurements.PATH_DETERMINATION.value]),
                                   np.median(self.times[TimeMeasurements.PATH_DETERMINATION.value]),
                                   np.mean(self.times[TimeMeasurements.PATH_PROGRAMMING.value]),
                                   np.median(self.times[TimeMeasurements.PATH_PROGRAMMING.value]),
                                   np.mean(self.times[TimeMeasurements.PACKET_REASSEMBLY.value]),
                                   np.median(self.times[TimeMeasurements.PACKET_REASSEMBLY.value]),
                                   np.mean(self.times[TimeMeasurements.PACKET_SENDING.value]),
                                   np.median(self.times[TimeMeasurements.PACKET_SENDING.value])])
            self.output_file.close()

    def _configure_ecmp_result_table(self, sw, ecmp_base, ecmp_count):
        ecmp_result_rule = self.P4_ECMP_RESULT_RULE_PATTERN.copy()
        ecmp_result_rule['action_params'][self.P4_ECMP_RESULT_ACTION_PARAM1] = ecmp_base
        ecmp_result_rule['action_params'][self.P4_ECMP_RESULT_ACTION_PARAM2] = ecmp_count

        self.insert_table_entry(sw, ecmp_result_rule)

    def _configure_nexthop_update_table(self, sw, port, dst_mac):
        nexthop_update_rule = self.P4_NEXTHOP_UPDATE_RULE_PATTERN.copy()
        nexthop_update_rule['match'][self.P4_NEXTHOP_UPDATE_MATCH] = port
        nexthop_update_rule['action_params'][self.P4_NEXTHOP_UPDATE_ACTION_PARAM] = str(dst_mac)

        self.insert_table_entry(sw, nexthop_update_rule)

    def _configure_source_update_table(self, sw, src_mac):
        source_update_rule = self.P4_SOURCE_UPDATE_RULE_PATTERN.copy()
        source_update_rule['action_params'][self.P4_SOURCE_UPDATE_ACTION_PARAM] = str(src_mac)

        self.insert_table_entry(sw, source_update_rule)

    def _program_path(self, path, flow, forwarding_flow=False, flow_5_tuple=None):
        switches = path[1:-1]

        for i, sw in enumerate(switches):
            flow['action_params']['port'] = self.p4monitor.map_edge_to_switch_port(sw, path[i + 2])

            self.insert_table_entry(sw, flow)

            if forwarding_flow:
                flow_hash = hashlib.sha1('{}_{}_{}_{}_{}'.format(flow_5_tuple['src_ip'],
                                                                 flow_5_tuple['dst_ip'],
                                                                 flow_5_tuple['protocol'],
                                                                 flow_5_tuple['src_port'],
                                                                 flow_5_tuple['dst_port'])).hexdigest()

                self.forwarding_rules[sw][flow_hash] = flow

    def _program_icmp_paths(self):
        icmp_rule = self.P4_ICMP_RULE_PATTERN.copy()

        host_pairs = [host_pair for host_pair in product(self.p4hosts, self.p4hosts) if host_pair[0] != host_pair[1]]
        host_pairs = [tuple(host_pair) for host_pair in set(map(frozenset, host_pairs))]

        for host1, host2 in host_pairs:
            path = self.p4monitor.get_shortest_path_hops(host1, host2)
            icmp_rule['match'][self.P4_ICMP_MATCH_SRC_ADDR] = str(self.p4hosts[host1]['ip'])
            icmp_rule['match'][self.P4_ICMP_MATCH_DST_ADDR] = str(self.p4hosts[host2]['ip'])
            self._program_path(path, icmp_rule)

            reversed_path = list(reversed(path))
            icmp_rule['match'][self.P4_ICMP_MATCH_SRC_ADDR] = str(self.p4hosts[host2]['ip'])
            icmp_rule['match'][self.P4_ICMP_MATCH_DST_ADDR] = str(self.p4hosts[host1]['ip'])
            self._program_path(reversed_path, icmp_rule)

    def _handle_cpu_packet(self, packet):
        # print(packet.show2())

        ethernet = packet[Ether]
        # only process IPv4 packets, skip probes
        # if ethernet.type != self.ETHERTYPE_IPV4:   # sniff_filter
        #     return
        # do not process packets sent by the controller itself
        if ethernet.src == self.P4_CONTROLLER_PACKET_SRC_MAC:
            return
        # sometimes packets get faster forwarded than path programming happens for the following switches;
        # solution: program path in reversed order
        # if ethernet.src == ethernet.dst:
        #     return

        # print(packet.show2())

        ethernet, ip, tproto, cpu, data = self._disassemble_packet(self, packet)

        flow_hash = hashlib.sha1('{}_{}_{}_{}_{}'.format(ip.src,
                                                         ip.dst,
                                                         ip.proto,
                                                         tproto.sport,
                                                         tproto.dport)).hexdigest()
        if flow_hash in self.flow_hashes:
            return
        else:
            self.flow_hashes.append(flow_hash)

        self._forward_flow(self, ethernet, ip, tproto, cpu, data, packet.sniffed_on)

    @time_measure_factory(TimeMeasurements.FLOW_FORWARDING)
    def _forward_flow(self, ethernet_header, ip_header, tproto_header, cpu_header, data, intf):
        # flow 5-tuple
        flow_5_tuple = {'src_ip': ip_header.src,
                        'dst_ip': ip_header.dst,
                        'protocol': ip_header.proto,
                        'src_port': tproto_header.sport,
                        'dst_port': tproto_header.dport}

        # print('flow 5-tuple: ', flow_5_tuple['src_ip'], flow_5_tuple['dst_ip'],
        #       flow_5_tuple['protocol'], flow_5_tuple['src_port'], flow_5_tuple['dst_port'])

        path = self._determine_path(self, flow_5_tuple, cpu_header)

        self._program_flow_forwarding_path(self, flow_5_tuple, path, cpu_header)

        packet = self._reassemble_packet(self, ethernet_header, ip_header, tproto_header, data)

        self._send_packet(self, packet, intf)

    @time_measure_factory(TimeMeasurements.PACKET_DISASSEMBLY)
    def _disassemble_packet(self, packet):
        ethernet = packet[Ether]
        ip = packet[IP]
        if TCP in packet:
            tproto = packet[TCP]
        else:
            tproto = packet[UDP]
        # cpu = packet[CPUHeader]
        cpu = CPUHeader(str(tproto.payload))
        data = cpu.payload

        ethernet.remove_payload()  # 14 bytes
        ip.remove_payload()  # 20 bytes
        tproto.remove_payload()  # 20 bytes (TCP)/ 08 bytes (UDP)
        cpu.remove_payload()  # 10 bytes

        return ethernet, ip, tproto, cpu, data

    @time_measure_factory(TimeMeasurements.PATH_DETERMINATION)
    def _determine_path(self, flow_5_tuple, cpu_header):
        src_host = self.p4monitor.map_ip_to_host(flow_5_tuple['src_ip'])
        dst_host = self.p4monitor.map_ip_to_host(flow_5_tuple['dst_ip'])

        path = None  # uniform link capacities
        if self.flow_forwarding_strategy == FlowForwardingStrategy.SHORTEST_PATH:  # shortest path routing
            if self.flow_forwarding_metric == ShortestPathMetrics.HOPS:  # switch hop number
                path = self.p4monitor.get_shortest_path_hops(src_host, dst_host)
            else:  # BANDWIDTH, LOAD_PORT_COUNTER, LOAD_PROBING, LATENCY_PROBING (link level properties)
                path = self.p4monitor.get_shortest_path_property(src_host, dst_host, self.flow_forwarding_metric.value)
        elif self.flow_forwarding_strategy == FlowForwardingStrategy.ECMP:  # ECMP routing
            switch_pathes = self.p4monitor.get_all_simple_paths(src_host, dst_host)
            ecmp_switch = switch_pathes[0][1]

            ecmp_result = None
            if self.flow_forwarding_metric == ECMPMetrics.HASH:  # switch ECMP (flow hash)
                ecmp_result = cpu_header.ecmp_result
            elif self.flow_forwarding_metric == ECMPMetrics.ROUND_ROBIN:  # switch ECMP (round robin)
                ecmp_result = self.round_robin_i[ecmp_switch] + self.ecmp_base
                self.round_robin_i[ecmp_switch] = (self.round_robin_i[ecmp_switch] + 1) % self.ecmp_count[ecmp_switch]
            elif self.flow_forwarding_metric == ECMPMetrics.RANDOM:  # switch ECMP (random)
                ecmp_result = self.np_random.randint(self.ecmp_base, self.ecmp_base + self.ecmp_count[ecmp_switch])
                # ecmp_result = np.random.randint(self.ecmp_base, self.ecmp_base + self.ecmp_count[ecmp_switch])

            ecmp_neighbor = self.p4monitor.map_switch_port_to_neighbor_node(ecmp_switch, ecmp_result)
            for switch_path in switch_pathes:
                if switch_path[1] == ecmp_switch and switch_path[2] == ecmp_neighbor:
                    path = switch_path
                    break
        elif self.flow_forwarding_strategy == FlowForwardingStrategy.PATH_PROPERTY:
            # path routing (path level properties)
            if self.flow_forwarding_metric == PathMetrics.LOAD_PORT_COUNTER:  # load by port counters
                path = self.p4monitor.get_path_less_loaded(src_host, dst_host, PathLinkData.LOAD_PORT_COUNTER)
            elif self.flow_forwarding_metric == PathMetrics.LOAD_PROBING:  # load by probing
                raise NotImplementedYetException("use of path loads collected by probing for routing "
                                                 "based on path criteria (snapshots) is not implemented yet")
            elif self.flow_forwarding_metric == PathMetrics.LATENCY_PROBING:  # latency by probing
                raise NotImplementedYetException("use of path latencies collected by probing for routing "
                                                 "based on path criteria (snapshots) is not implemented yet")
            elif self.flow_forwarding_metric == PathMetrics.COMBINED:
                # load by port counters and probing, latency by probing
                raise NotImplementedYetException("combined use of path loads collected by probing and port counters "
                                                 "as well as path latencies collected by probing for routing based on "
                                                 "path criteria (snapshots) is not implemented yet")
        elif self.flow_forwarding_strategy == FlowForwardingStrategy.FLOW_PREDICTION:  # flow prediction
            if self.flow_forwarding_metric == FlowPredictionMetrics.THROUGHPUT:  # flow throughput
                flow_hash = hashlib.sha1('{}_{}_{}_{}_{}'.format(flow_5_tuple['src_ip'],
                                                                 flow_5_tuple['dst_ip'],
                                                                 flow_5_tuple['protocol'],
                                                                 flow_5_tuple['src_port'],
                                                                 flow_5_tuple['dst_port'])).hexdigest()
                flow_throughput, flow_throughput_unit = self.traffic_manager.get_flow_throughput_prediction(flow_hash)
                path, flow_load = self.p4monitor.get_path_pfr(src_host, dst_host,
                                                              PathLinkData.LOAD_PORT_COUNTER,
                                                              flow_throughput[2],
                                                              flow_throughput_unit)

                path_ = path[1:-1]
                for i, sw in enumerate(path_[:-1]):
                    sw_neighbor = path_[i + 1]
                    link_load = self.p4monitor.get_link_property(sw, sw_neighbor, PathLinkData.LOAD_PORT_COUNTER)
                    self.p4monitor.update_link_property(sw, sw_neighbor, PathLinkData.LOAD_PORT_COUNTER,
                                                        link_load + flow_load)
            elif self.flow_forwarding_metric == FlowPredictionMetrics.DURATION:  # flow duration
                raise NotImplementedYetException("consideration of a flow's predicted duration "
                                                 "in the context of routing based on flow predictions "
                                                 "is not implemented yet")
            elif self.flow_forwarding_metric == FlowPredictionMetrics.BYTES:  # flow bytes
                raise NotImplementedYetException("consideration of a flow's predicted number of bytes "
                                                 "in the context of routing based on flow predictions "
                                                 "is not implemented yet")
            elif self.flow_forwarding_metric == FlowPredictionMetrics.COMBINED:  # flow bytes and duration => throughput
                raise NotImplementedYetException("combined consideration of a flow's predicted number of bytes and "
                                                 "its duration in the context of routing based on flow predictions "
                                                 "is not implemented yet")

        return path

    @time_measure_factory(TimeMeasurements.PATH_PROGRAMMING)
    def _program_flow_forwarding_path(self, flow_5_tuple, path, cpu_header):
        def _encode_flow_hash(flow_hash, match_num_elements):
            return hex(flow_hash)[2:].zfill(match_num_elements).decode('hex')

        forwarding_rule = self.P4_FORWARDING_RULE_PATTERN.copy()

        flow_hash_one = cpu_header.flow_hash_one
        flow_hash_two = cpu_header.flow_hash_two
        forwarding_rule['match'][self.P4_FORWARDING_MATCH1] = _encode_flow_hash(flow_hash_one,
                                                                                self.P4_FORWARDING_MATCH1_NUM_ELEMENTS)
        forwarding_rule['match'][self.P4_FORWARDING_MATCH2] = _encode_flow_hash(flow_hash_two,
                                                                                self.P4_FORWARDING_MATCH2_NUM_ELEMENTS)

        log.info('programming path: {} - '
                 'flow 5-tuple: {}/{},{}/{},{} - '
                 'flow hashes:{}/{}'.format([str(x) for x in path[1:-1]],
                                            flow_5_tuple['src_ip'], flow_5_tuple['dst_ip'], flow_5_tuple['protocol'],
                                            flow_5_tuple['src_port'], flow_5_tuple['dst_port'],
                                            flow_hash_one, flow_hash_two))

        self._program_path(path, forwarding_rule, forwarding_flow=True, flow_5_tuple=flow_5_tuple)

    @time_measure_factory(TimeMeasurements.PACKET_REASSEMBLY)
    def _reassemble_packet(self, ethernet_header, ip_header, tproto_header, data):
        ethernet_header.src = self.P4_CONTROLLER_PACKET_SRC_MAC
        packet = ethernet_header / ip_header / tproto_header / data
        return packet

    @time_measure_factory(TimeMeasurements.PACKET_SENDING)
    def _send_packet(self, packet, intf):
        sendp(packet, iface=intf, verbose=False)
        # sendpfast(packet, iface=intf)  # requires 'tcpreplay'

    def init_csv_output(self, exp_id, exp_iter):
        output_dir = os.path.join('p4controllers', 'results')
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        # else:
        #     for dir in os.listdir(output_dir):
        #         shutil.rmtree(os.path.join(output_dir, dir))

        exp_dir = os.path.join(output_dir, str(exp_id), str(exp_iter))
        try:
            os.makedirs(exp_dir)
        except:
            pass

        output_file = os.path.join(exp_dir, 'time_measure.csv')
        self.output_file = open(output_file, 'w')
        self.csv_writer = csv.writer(self.output_file)

    def write_csv_output(self, time_measures):
        self.csv_writer.writerow(time_measures)
        self.output_file.flush()


class P4FlowForwardingMappingException(Exception):

    def __init__(self, message):
        super(P4FlowForwardingMappingException, self).__init__(self.__class__.__name__ + ': ' + message)


class NotImplementedYetException(Exception):

    def __init__(self, message):
        super(NotImplementedYetException, self).__init__(self.__class__.__name__ + ': ' + message)
