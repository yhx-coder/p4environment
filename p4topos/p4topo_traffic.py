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

from time import sleep
import threading

from enum import Enum

import numpy as np

import yaml

import hashlib


class DataRates(Enum):
    KILOBIT = 'k'
    MEGABIT = 'm'
    GIGABIT = 'g'


class TrafficProfiles(Enum):
    STATIC = 'static'
    DYNAMIC = 'dynamic'


class TrafficManager(threading.Thread):
    IPERF_CLIENT_BASE_PORT = 60000
    IPERF_SERVER_PORT = 5100

    traffic_generation_event = threading.Event()

    def __init__(self, traffic_profile, mininet_network, mininet_runner):
        super(TrafficManager, self).__init__()

        self.traffic_profile = self._load_traffic_profile(traffic_profile)
        self.traffic_flag = True

        self.default_throughput = 10
        self.default_duration = 600
        self.default_protocol = '-u'  # UDP
        self.default_bw_unit = 'k'  # Kbit/s

        self.mininet_network = mininet_network
        self.mininet_runner = mininet_runner

        self.flow_throughputs = {}
        self.flow_throughput_predictions = {}

        self.np_random = None

    def _load_traffic_profile(self, traffic_profile):
        yaml_content = None
        with open(traffic_profile, 'r') as yaml_file:
            try:
                yaml_content = yaml.safe_load(yaml_file)
            except:
                raise yaml.YAMLError('specified traffic profile ({}) is no valid YAML file'.format(traffic_profile))
        return yaml_content

    def run(self):
        traffic_profile_type = TrafficProfiles(self.traffic_profile.pop('type'))

        if traffic_profile_type == TrafficProfiles.STATIC:
            self._static_traffic_profile()

        if traffic_profile_type == TrafficProfiles.DYNAMIC:
            self._dynamic_traffic_profile()

    def _static_traffic_profile(self):
        flow_traffic_i = 0
        flow_counter = 0

        while self.traffic_flag:
            for flow_spec_id, flow_spec in self.traffic_profile.items():
                for flow in range(flow_spec['num']):
                    if flow_spec['start'][flow] == flow_traffic_i:
                        flow_counter += 1

                        flow_throughput = flow_spec['throughput'][flow]
                        flow_duration = flow_spec['duration'][flow]

                        flow_src = flow_spec['source']
                        flow_dst = flow_spec['destination']
                        client_address = self.mininet_network[flow_src].IP()
                        server_address = self.mininet_network[flow_dst].IP()

                        bandwidth = self.default_throughput if flow_throughput == 'default' else flow_throughput
                        bw_unit = self.default_bw_unit if flow_throughput == 'default' else flow_spec['throughput_unit']
                        time = self.default_duration if flow_duration == 'default' else flow_duration
                        protocol = '-u' if flow_spec['protocol'][flow] == 'UDP' else ''

                        flow_hash = hashlib.sha1('{}_{}_{}_{}_{}'.format(client_address,
                                                                         server_address,
                                                                         17 if protocol == '-u' else 6,
                                                                         self.IPERF_CLIENT_BASE_PORT + flow_counter,
                                                                         self.IPERF_SERVER_PORT)).hexdigest()

                        flow_throughput_unit = DataRates(flow_spec['throughput_unit'])

                        self._add_flow_throughput(flow_hash=flow_hash,
                                                  flow_throughput=(flow_throughput, flow_throughput_unit))

                        self.mininet_network[flow_dst].start_iperf_server()
                        self.mininet_network[flow_src].start_iperf_client(client_address=client_address,
                                                                          client_port=self.IPERF_CLIENT_BASE_PORT + \
                                                                                      flow_counter,
                                                                          server_address=server_address,
                                                                          server_port=self.IPERF_SERVER_PORT,
                                                                          protocol=protocol,
                                                                          bandwidth=bandwidth,
                                                                          bw_unit=bw_unit,
                                                                          time=time)
            flow_traffic_i += 1
            sleep(1)
            if flow_counter == max([flow_spec['num'] for flow_spec in self.traffic_profile.values()]):
                sleep(60)
                self.mininet_runner.end_experiment()

    def _dynamic_traffic_profile(self):
        flow_batch_size = self.traffic_profile.pop('flow_batch_size')
        flow_batch_interval = self.traffic_profile.pop('flow_batch_interval')

        self.traffic_profile.pop('name')

        flow_replay_seed = self.traffic_profile.pop('seed')
        self.np_random = np.random.RandomState(seed=flow_replay_seed)

        flow_batch_i = 0
        flow_counter = 0

        while self.traffic_flag:
            # sleep(flow_batch_interval)

            if not self.traffic_profile.keys():
                break

            self.traffic_generation_event.wait()
            self.traffic_generation_event.clear()

            for flow_spec_id, flow_spec in self.traffic_profile.items():
                if len(flow_spec['throughput']) == 0:
                    self.traffic_profile.pop(flow_spec_id)
                    continue

                for flow in range(flow_batch_size):
                    flow_counter += 1

                    flow_throughput_i = self.np_random.randint(0, len(flow_spec['throughput']))
                    # flow_throughput_i = np.random.randint(0, len(flow_spec['throughput']))
                    flow_throughput = flow_spec['throughput'].pop(flow_throughput_i)
                    flow_duration = flow_spec['duration']

                    flow_src = flow_spec['source']
                    flow_dst = flow_spec['destination']
                    client_address = self.mininet_network[flow_src].IP()
                    server_address = self.mininet_network[flow_dst].IP()

                    bandwidth = flow_throughput[0]
                    time = self.default_duration if flow_duration == 'default' else flow_duration
                    protocol = '-u' if flow_spec['protocol'] == 'UDP' else ''

                    flow_hash = hashlib.sha1('{}_{}_{}_{}_{}'.format(client_address,
                                                                     server_address,
                                                                     17 if protocol == '-u' else 6,
                                                                     self.IPERF_CLIENT_BASE_PORT + flow_counter,
                                                                     self.IPERF_SERVER_PORT)).hexdigest()

                    flow_throughput_unit = DataRates(flow_spec['throughput_unit'])

                    self._add_flow_throughput_prediction(flow_hash=flow_hash,
                                                         flow_throughput_prediction=(flow_throughput,
                                                                                     flow_throughput_unit))

                    self.mininet_network[flow_dst].start_iperf_server()
                    self.mininet_network[flow_src].start_iperf_client(client_address=client_address,
                                                                      client_port=self.IPERF_CLIENT_BASE_PORT + \
                                                                                  flow_counter,
                                                                      server_address=server_address,
                                                                      server_port=self.IPERF_SERVER_PORT,
                                                                      protocol=protocol,
                                                                      bandwidth=bandwidth,
                                                                      bw_unit=flow_spec['throughput_unit'],
                                                                      time=time)

                flow_batch_i += 1

        sleep(60)
        self.mininet_runner.end_experiment()

    def stop(self):
        self.traffic_flag = False

    def _add_flow_throughput(self, flow_hash, flow_throughput):
        self.flow_throughputs[flow_hash] = flow_throughput

    def get_flow_throughput(self, flow_hash):
        return self.flow_throughputs[flow_hash]

    def _add_flow_throughput_prediction(self, flow_hash, flow_throughput_prediction):
        self.flow_throughput_predictions[flow_hash] = flow_throughput_prediction

    def get_flow_throughput_prediction(self, flow_hash):
        return self.flow_throughput_predictions[flow_hash]
