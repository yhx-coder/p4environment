# Copyright 2013-present Barefoot Networks, Inc.
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
# Adapted by Robert MacDavid (macdavid@cs.princeton.edu) from scripts found in
# the p4app repository (https://github.com/p4lang/p4app)
#
#
# modified by Christoph Hardegen
#             (christoph.hardegen@cs.hs-fulda.de)
#             Fulda University of Applied Sciences
#
#############################################################################
# based on P4 language tutorials                                            #
# see https://github.com/p4lang/tutorials/blob/master/utils/run_exercise.py #
#############################################################################

if __name__ == '__main__':
    ##########
    from tools import modules_installation as minstall

    for module_spec in minstall.python_modules:
        minstall.install_python_module(python_module=module_spec[0], import_name=module_spec[1], version=module_spec[2])
    ##########

    import sys
    import os

    if os.getcwd() not in sys.path:
        sys.path.append(os.getcwd())

    from tools.log.log import init_logger, customize_mininet_logger

    init_logger('p4topology')  # see p4topology.log
    customize_mininet_logger('mininet')  # see mininet.log

from mininet.net import Mininet
from mininet.cli import CLI

from tools.log.log import log, change_log_level, LOG_LEVEL_DEFAULT

import subprocess
import traceback
import json

from p4topos.p4topo import P4Topo
from p4topos.p4topo_parser import TopologyArgumentParser
from p4topos.p4topo_generator import TopologyGenerator
from p4topos.p4topo_params import TopologyParameter

from p4env import P4Monitors
from p4env import P4Controllers
from p4env import P4Switches, P4Hosts

from p4env import P4NetworkRunModes

from p4topos.p4topo_traffic import TrafficManager

import threading


class P4TopoRunner(object):

    def __init__(self, topology):
        with open(topology, 'r') as topology_file:
            self.topology_json = json.load(topology_file)

        self.experiment_event = threading.Event()

        self.tp_args = None
        self.tp_params = None

    def run(self, tp_args, tp_params):
        self.tp_args = tp_args
        self.tp_params = tp_params

        log.info('initializing topology...')
        topo = P4Topo(self.topology_json)

        log.info('initializing mininet...')
        net = Mininet(topo=topo, controller=None, autoStaticArp=True)

        log.info('starting mininet...')
        net.start()

        management_host = self.topology_json['management']['host']['name']
        management_switches = [self.topology_json['management']['switch'][x]['name'] for x in ['switches', 'hosts']]

        for switch in management_switches:
            subprocess.call('ovs-ofctl add-flow {switch} action=normal'.format(switch=switch), shell=True)

        run_mode = P4NetworkRunModes(tp_args.run_mode)

        p4monitor_kwargs = {}
        p4controller_kwargs = {}
        if run_mode == P4NetworkRunModes.EXPERIMENT:
            p4monitor_kwargs.update({'exp': tp_args.exp,
                                     'exp_iter': tp_args.exp_iter})
            p4controller_kwargs.update({'exp': tp_args.exp,
                                        'exp_iter': tp_args.exp_iter})
        if tp_params.P4_MONITOR == P4Monitors.PortCounterMonitor.value:
            p4monitor_kwargs.update({'p4monitor_counter_interval': tp_args.p4monitor_counter_interval,
                                     'p4monitor_counter_direction': tp_args.p4monitor_counter_direction,
                                     'p4monitor_counter_data': tp_args.p4monitor_counter_data})
        if tp_params.P4_MONITOR == P4Monitors.ProbingMonitor.value:
            p4monitor_kwargs.update({'p4monitor_probing_interval': tp_args.p4monitor_probing_interval,
                                     'p4monitor_probing_mode': tp_args.p4monitor_probing_mode})
        p4monitor = tp_params.P4_MONITOR(**p4monitor_kwargs)

        if tp_params.P4_CONTROLLER == P4Controllers.FlowForwardingController.value:
            p4controller_kwargs.update({'flow_forwarding_strategy': tp_args.p4controller_flow_forwarding_strategy,
                                        'flow_forwarding_metric': tp_args.p4controller_flow_forwarding_metric,
                                        'time_measurement': tp_args.p4controller_time_measurement})
        p4controller = None
        if tp_params.P4_CONTROLLER:
            p4controller = tp_params.P4_CONTROLLER(**p4controller_kwargs)
            p4monitor.set_p4controller(p4controller)
            p4controller.set_p4monitor(p4monitor)

        log.info('configuring hosts...')
        host_mappings = []
        for host in [h for h in net.hosts if h.name != management_host]:
            host.configure()
            host_config = host.get_host_config()
            p4monitor.add_node(host_config)
            host.start_services()
            host.describe()

            host_mappings.append('{} {}'.format(host_config['mgmt_ip'], host.name))

        log.info('configuring switches...')
        switch_mappings = []
        for switch in [s for s in net.switches if s.name not in management_switches]:
            switch.configure()
            switch_config = switch.get_switch_config()
            p4monitor.add_switch_connection(switch.name, switch_config)
            if p4controller:
                p4controller.add_switch_connection(switch.name, switch_config)
            switch.start_services()
            switch.describe()

            switch_mappings.append('{} {}'.format(switch_config['mgmt_ip'], switch.name))

        p4monitor.build_topology()
        p4monitor.start()

        if p4controller:
            p4controller.start()

        traffic_manager = None
        if tp_params.TRAFFIC_PROFILE:
            traffic_manager = TrafficManager(traffic_profile=tp_params.TRAFFIC_PROFILE,
                                             mininet_network=net,
                                             mininet_runner=self)
            if isinstance(p4controller, P4Controllers.FlowForwardingController.value):
                p4controller.set_traffic_manager(traffic_manager)
            traffic_manager.start()

        manage_hosts_file(host_mappings + switch_mappings, operation='add')

        if run_mode == P4NetworkRunModes.EXPERIMENT:
            self.experiment_event.wait()

        if run_mode == P4NetworkRunModes.CLI:
            CLI(mininet=net)

        manage_hosts_file(host_mappings + switch_mappings, operation='remove')

        p4monitor.stop_monitor()

        if p4controller:
            p4controller.stop_controller()

        p4monitor.shutdown_switch_connections()
        if p4controller:
            p4controller.shutdown_switch_connections()

        if traffic_manager:
            traffic_manager.stop()

        for host in [host_ for host_ in net.hosts if host_.name != management_host]:
            host.stop_services()

        for switch in [switch_ for switch_ in net.switches if switch_.name not in management_switches]:
            switch.stop_services()

        net.stop()

    def end_experiment(self):
        if tp_args.run_mode == P4NetworkRunModes.EXPERIMENT.value:
            self.experiment_event.set()


def cleanup_on_error():
    subprocess.call('''mn -c; for link in `ip link | \
                       grep -e '[h,s]root[h,s]\\?-[h,s]root[h,s]\\?@[h,s]root[h,s]\\?-[h,s]root[h,s]\\?' \
                       -e 'cpu-s[0-9]*@if[0-9]*' -e 'srooth\\?-[h,s][0-9]*@if[0-9]*' | \
                       cut -d ' ' -f 2 | cut -d @ -f 1`; do 
                       if [ $link != 'macvtap0' ]; then ip link delete $link; fi; done; 
                       ip link delete sroot; ip link delete srooth''', shell=True)
    subprocess.call("for pid in `ps auxw | grep p4runner.py | awk '{print $2}'`; do kill -9 $pid; done", shell=True)
    subprocess.call("ps -x | grep /usr/sbin/sshd | grep 'ListenAddress=' | awk -F ' ' '{{print $1}}' | xargs kill -9",
                    shell=True)


def manage_hosts_file(mappings, operation, hosts_file='/etc/hosts'):
    if operation not in ['add', 'remove']:
        return

    if operation == 'add':
        with open(hosts_file, 'r+') as f_hosts:
            for mapping in mappings:
                for line in f_hosts:
                    if mapping in line:
                        break
                else:
                    f_hosts.write(mapping + '\n')

    if operation == 'remove':
        with open(hosts_file, 'r') as f_hosts:
            lines = f_hosts.readlines()
        with open(hosts_file, 'w') as f_hosts:
            for line in lines:
                if line.rstrip() not in mappings:
                    f_hosts.write(line)


if __name__ == '__main__':
    try:
        args_parser = TopologyArgumentParser.create_parser()
        tp_args, _ = args_parser.parse_known_args()
        TopologyArgumentParser.print_args(tp_args)

        if tp_args.loglevel != LOG_LEVEL_DEFAULT:
            change_log_level(tp_args.loglevel)

        if tp_args.p4controller:
            p4controller_class = getattr(P4Controllers, tp_args.p4controller).value
        else:
            p4controller_class = None
        p4monitor_class = getattr(P4Monitors, tp_args.p4monitor).value

        p4switch_class = getattr(P4Switches, tp_args.switch).value
        p4host_class = getattr(P4Hosts, tp_args.host).value

        tp_params = TopologyParameter.get_topology_params(tp_args=tp_args,
                                                          p4switch_class=p4switch_class,
                                                          p4host_class=p4host_class,
                                                          p4monitor_class=p4monitor_class,
                                                          p4controller_class=p4controller_class)

        TopologyGenerator.build_topology_json(tp_params=tp_params)

        P4TopoRunner(topology=tp_params.TOPOLOGY_FILE_PATH).run(tp_args=tp_args, tp_params=tp_params)
    except Exception as ex:
        log.error(traceback.format_exc())
    finally:
        cleanup_on_error()
