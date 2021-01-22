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

import argparse
import os
import sys

from p4env import P4NetworkRunModes, P4Topologies, P4Hosts, P4Switches, P4SwitchInit, P4Programs, P4Controllers, \
    P4Monitors, LinkConfig, HostNetwork

from p4monitors.p4port_counter import CounterDirection, CounterData
from p4monitors.p4probing import ProbingMode

from p4controllers.flow_forwarding import FlowForwardingStrategy, \
    ShortestPathMetrics, ECMPMetrics, PathMetrics, FlowPredictionMetrics

from tools.log.log import LogLevel


class TopologyArgumentParser(object):

    @staticmethod
    def print_args(args_):
        print('-' * 80)
        for k, v in sorted(vars(args_).items()):
            print('\t * {}: {}'.format(k, v))
        print('-' * 80)

    @staticmethod
    def create_parser(all_parameters=False):
        parser = argparse.ArgumentParser()

        parser.add_argument('--run_mode', type=str, default=P4NetworkRunModes.CLI.value,
                            choices=[mode.value for mode in P4NetworkRunModes],
                            help='run mode for the P4 network', required=False)

        args_parser_tmp, _ = parser.parse_known_args()
        if args_parser_tmp.run_mode == P4NetworkRunModes.EXPERIMENT.value or all_parameters:
            parser.add_argument('--exp', type=int, default=42,
                                help='experiment ID for an flow forwarding experiment', required=False)
            parser.add_argument('--exp_iter', type=int, default=21,
                                help='experiment run iteration', required=False)

        parser.add_argument('--topology', type=str, default=P4Topologies.DIAMOND_SHAPE.value,
                            choices=[p4topology.value for p4topology in P4Topologies],
                            help='name of the P4 topology', required=False)

        parser.add_argument('--link_config', type=str, default=LinkConfig.AUTO.value,
                            choices=[mode.value for mode in LinkConfig],
                            help='link respectively switch port (ID) configuration mode', required=False)

        parser.add_argument('--p4program', type=str, default=P4Programs.L2_FORWARDING_STATIC.value,
                            choices=[p4program.value for p4program in P4Programs],
                            help='default P4 program that runs on any deployed P4 switch', required=False)

        parser.add_argument('--switch', type=str, default=P4Switches.P4RuntimeSwitch.value.__name__,
                            choices=[p4switch.value.__name__ for p4switch in P4Switches],
                            help='type of the deployed P4 switches (class)', required=False)

        parser.add_argument('--switch_init', type=str, default=P4SwitchInit.P4RUNTIME_API.value,
                            choices=[mode.value for mode in P4SwitchInit],
                            help='initialization method for deployed P4 switches', required=False)

        parser.add_argument('--host', type=str, default=P4Hosts.P4Host.value.__name__,
                            choices=[p4host.value.__name__ for p4host in P4Hosts],
                            help='type of the deployed P4 hosts (class)', required=False)

        parser.add_argument('--host_init', type=eval, default=False,
                            choices=[False, True],
                            help='perform initialization for deployed P4 hosts', required=False)

        parser.add_argument('--host_network', type=str, default=HostNetwork.SHARED.value,
                            choices=[mode.value for mode in HostNetwork],
                            help='addressing mode for P4 hosts (network subnet)', required=False)

        parser.add_argument('--p4monitor', type=str, default=P4Monitors.P4Monitor.value.__name__,
                            choices=[p4monitor.value.__name__ for p4monitor in P4Monitors],
                            help='P4 monitor (class) for the P4 topology', required=False)

        args_parser_tmp, _ = parser.parse_known_args()
        if args_parser_tmp.p4monitor == P4Monitors.PortCounterMonitor.value.__name__ or all_parameters:
            parser.add_argument('--p4monitor_counter_interval', type=int, default=10,
                                help='time interval for performing port counter collection', required=False)
            parser.add_argument('--p4monitor_counter_direction', type=str,
                                default=CounterDirection.TX_PORT_COUNTER.value,
                                choices=[mode.value for mode in CounterDirection],
                                help='flow direction for port counters to be collected', required=False)
            parser.add_argument('--p4monitor_counter_data', type=str,
                                default=CounterData.BYTE_COUNT.value,
                                choices=[mode.value for mode in CounterData],
                                help='port counter data to be collected', required=False)
        if args_parser_tmp.p4monitor == P4Monitors.ProbingMonitor.value.__name__ or all_parameters:
            parser.add_argument('--p4monitor_probing_interval', type=int, default=10,
                                help='time interval for performing link/path probing', required=False)
            parser.add_argument('--p4monitor_probing_mode', type=str, default=ProbingMode.LOCAL_MULTICAST.value,
                                choices=[mode.value for mode in ProbingMode],
                                help='strategy for performing link/path probing', required=False)

        parser.add_argument('--p4controller', type=str, default=None,
                            choices=[p4controller.value.__name__ for p4controller in P4Controllers],
                            help='P4 controller (class) for the P4 topology', required=False)

        args_parser_tmp, _ = parser.parse_known_args()
        if args_parser_tmp.p4controller == P4Controllers.FlowForwardingController.value.__name__ or all_parameters:
            parser.add_argument('--p4controller_flow_forwarding_strategy', type=str,
                                default=FlowForwardingStrategy.SHORTEST_PATH.value,
                                choices=[strategy.value for strategy in FlowForwardingStrategy],
                                help='routing strategy for forwarding flows', required=False)
            strategies = [ShortestPathMetrics, ECMPMetrics, PathMetrics, FlowPredictionMetrics]
            metrics = set()
            for strategy in strategies:
                for metric in strategy:
                    metrics.add(metric.value)
            parser.add_argument('--p4controller_flow_forwarding_metric', type=str,
                                default=ShortestPathMetrics.HOPS.value,
                                choices=list(metrics),
                                help='routing metric for selected flow forwarding strategy', required=False)
            parser.add_argument('--p4controller_time_measurement', type=eval, default=False,
                                choices=[False, True],
                                help='measure elapsed times for flow forwarding controller operations', required=False)

        choices = None
        try:
            if sys.argv[0] == 'p4runner.py':
                choices = [file_ for file_ in os.listdir('tools/traffic_profiles/profiles') if not file_.startswith('.')]
            if sys.argv[0] == 'experiments_generator.py':
                choices = [file_ for file_ in os.listdir('../traffic_profiles/profiles') if not file_.startswith('.')]
        except:
            pass
        parser.add_argument('--traffic_profile', type=str, default=None, choices=choices,
                            help='traffic profile that is applied to and replayed in the P4 topology', required=False)

        parser.add_argument('--loglevel', type=str, default=LogLevel.INFO.value,
                            choices=[level.value for level in LogLevel],
                            help='make an educated guess', required=False)

        return parser
