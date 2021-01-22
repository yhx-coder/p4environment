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

import sys
import os

sys.path.append(os.path.join(os.pardir, os.pardir))

if __name__ == '__main__':
    ##########
    from tools import modules_installation as minstall

    for module_spec in minstall.python_modules:
        minstall.install_python_module(python_module=module_spec[0], import_name=module_spec[1], version=module_spec[2])
    ##########

import shutil

from enum import Enum

import numpy as np
from sklearn.preprocessing import minmax_scale

import yaml

import random

import matplotlib.pyplot as plt

from traffic_profiles_data import traffic_profiles


class FlowDistribution(Enum):
    RANDOM = 'random'
    STATIC = 'static'
    EVEN = 'even'
    EXPONENTIAL = 'exponential'


class PredictionError(Enum):
    RANDOM = 'random'
    GAUSSIAN = 'gaussian'


class DataRates(Enum):
    KILOBIT = 'k'
    MEGABIT = 'm'
    GIGABIT = 'g'


class TrafficProfileGenerator(object):
    YAML_FILE_DIR = 'profiles'
    YAML_FILE = '{}_{}.yaml'

    DEFAULT_VALUES = {
        'link_bw_unit': 'k',  # Kbit/s
        'link_bw': 1000,
        'link_bw_lower_limit': 15,
        'link_bw_interval_fraction_percent': 20,
        'link_bw_upper_limit': None,

        'number_flows': 100,
        'flow_distribution_mode': FlowDistribution.EXPONENTIAL,

        'flow_transport_protocol': 'UDP',
        'flow_throughput': 'generated',
        'flow_throughput_unit': 'k',
        'flow_duration': 'default',
        'flow_duration_unit': 's',

        'number_classes': 10,
        'class_boundaries': None,

        'flow_batch_interval': 30,
        'flow_batch_size': 10,

        'prediction_accuracy': 1.0,
        'prediction_error_rate': None,
        'prediction_error_mode': PredictionError.RANDOM
    }

    DEFAULT_VALUES.update({
        'link_bw_upper_limit': DEFAULT_VALUES['link_bw_lower_limit'] + \
                               DEFAULT_VALUES['link_bw'] * DEFAULT_VALUES['link_bw_interval_fraction_percent']})

    DEFAULT_VALUES.update({'class_boundaries': np.linspace(DEFAULT_VALUES['link_bw_lower_limit'],
                                                           DEFAULT_VALUES['link_bw_upper_limit'],
                                                           DEFAULT_VALUES['number_classes'] + 1),
                           'prediction_error_rate': 1.0 - DEFAULT_VALUES['prediction_accuracy']})

    def __init__(self):
        self.np_random = None

    def generate_traffic_profile(self, traffic_profile_name, traffic_profile_seed, traffic_profile_data):
        random.seed(traffic_profile_seed)

        self.np_random = np.random.RandomState(seed=traffic_profile_seed)

        traffic_profile_data = self._merge_traffic_profile_data_with_defaults(traffic_profile_data=traffic_profile_data)
        traffic_profile_data = self._update_traffic_profile_data(traffic_profile_data=traffic_profile_data)

        traffic_profile = {'type': 'dynamic',
                           'name': traffic_profile_name,
                           'seed': traffic_profile_seed,
                           'flow_batch_size': traffic_profile_data['flow_batch_size'],
                           'flow_batch_interval': traffic_profile_data['flow_batch_interval']}

        flow_data = traffic_profile_data['flow_data']

        for i, flow_data_i in enumerate(flow_data):
            if flow_data_i['link_bw_unit'] != flow_data_i['flow_throughput_unit']:
                raise TrafficProfileGenerationException("no matching units for 'link_bw_unit' and "
                                                        "'flow_throughput_unit' (traffic profile: {} -> "
                                                        "subprofile: {})".format(traffic_profile_name, i))

        for i, flow_data_i in enumerate(flow_data):
            flow_throughputs = self._generate_flow_throughputs(traffic_profile_name=traffic_profile_name,
                                                               traffic_profile_subprofile_id=i,
                                                               traffic_profile_flows=flow_data_i)

            traffic_profile.update({i + 1: {'num': len(flow_throughputs),
                                            'source': flow_data_i['src_host'],
                                            'destination': flow_data_i['dst_host'],
                                            'protocol': flow_data_i['flow_transport_protocol'],
                                            'throughput': flow_throughputs,
                                            'throughput_unit': flow_data_i['flow_throughput_unit'],
                                            'duration': flow_data_i['flow_duration'],
                                            'duration_unit': flow_data_i['flow_duration_unit']}})

        with open(os.path.join(self.YAML_FILE_DIR, self.YAML_FILE.format(traffic_profile_name,
                                                                         traffic_profile_seed)), 'w') as yaml_file:
            yaml.dump(traffic_profile, yaml_file, default_flow_style=False)

    def _merge_traffic_profile_data_with_defaults(self, traffic_profile_data):
        for k, v in self.DEFAULT_VALUES.items():
            for i in range(len(traffic_profile_data['flow_data'])):
                if k not in ['flow_batch_size', 'flow_batch_interval']:
                    if k not in traffic_profile_data['flow_data'][i] and k not in ['link_bw_upper_limit',
                                                                                   'class_boundaries',
                                                                                   'prediction_error_rate']:
                        traffic_profile_data['flow_data'][i][k] = v

                else:
                    if k not in traffic_profile_data:
                        traffic_profile_data[k] = v
        return traffic_profile_data

    def _update_traffic_profile_data(self, traffic_profile_data):
        for i in range(len(traffic_profile_data['flow_data'])):
            tmp = traffic_profile_data['flow_data'][i]
            tmp.update({'link_bw_upper_limit': tmp['link_bw_lower_limit'] + \
                                               tmp['link_bw'] * (tmp['link_bw_interval_fraction_percent'] / 100.0)})

            tmp.update({'class_boundaries': np.linspace(tmp['link_bw_lower_limit'],
                                                        tmp['link_bw_upper_limit'],
                                                        tmp['number_classes'] + 1),
                        'prediction_error_rate': 1.0 - tmp['prediction_accuracy']})
        return traffic_profile_data

    def _generate_flow_throughputs(self, traffic_profile_name, traffic_profile_subprofile_id, traffic_profile_flows):
        print('### traffic profile: {}'.format(traffic_profile_name))

        flow_throughputs = []
        throughputs = []
        if FlowDistribution(traffic_profile_flows['flow_distribution_mode']) == FlowDistribution.STATIC:
            for i, flow_num in enumerate(traffic_profile_flows['classes_distribution']):
                throughputs_ = []
                for x in range(flow_num):
                    random_number = self.np_random.random_sample(size=1)[0]
                    # random_number = self.np.random.random(size=1)[0]
                    throughputs_.append(random_number)

                throughputs_ = minmax_scale(throughputs_,
                                            feature_range=(traffic_profile_flows['class_boundaries'][i] + 0.001,
                                                           traffic_profile_flows['class_boundaries'][i + 1] - 0.001))
                throughputs += list(throughputs_)

                # throughputs += list(self.np_random.uniform(size=flow_num_,
                #                                            low=traffic_profile_data['class_boundaries'][i],
                #                                            high=traffic_profile_data['class_boundaries'][i + 1]))
                # throughputs += list(np.random.uniform(size=flow_num_,
                #                                       low=traffic_profile_data['class_boundaries'][i],
                #                                       high=traffic_profile_data['class_boundaries'][i + 1]))
        else:
            if FlowDistribution(traffic_profile_flows['flow_distribution_mode']) == FlowDistribution.RANDOM:
                throughputs = [random.random() for _ in range(traffic_profile_flows['number_flows'])]

            if FlowDistribution(traffic_profile_flows['flow_distribution_mode']) == FlowDistribution.EVEN:
                throughputs = self.np_random.uniform(size=traffic_profile_flows['number_flows'])
                # throughputs = np.random.uniform(size=traffic_profile_data['number_flows'])

            if FlowDistribution(traffic_profile_flows['flow_distribution_mode']) == FlowDistribution.EXPONENTIAL:
                throughputs = self.np_random.standard_exponential(size=traffic_profile_flows['number_flows'])
                # throughputs = self.np_random.exponential(scale=1, size=traffic_profile_data['number_flows'])
                # throughputs = np.random.standard_exponential(size=traffic_profile_data['number_flows'])

            throughputs = minmax_scale(throughputs,
                                       feature_range=(traffic_profile_flows['link_bandwidth_lower_limit'] + 0.001,
                                                      traffic_profile_flows['link_bandwidth_upper_limit'] - 0.001))

        classes = np.digitize(throughputs, traffic_profile_flows['class_boundaries']) - 1
        for i, class_ in enumerate(classes):
            class_ = int(class_)
            median_class_throughput = (traffic_profile_flows['class_boundaries'][class_] +
                                       traffic_profile_flows['class_boundaries'][class_ + 1]) / 2
            flow_throughputs.append([float(throughputs[i]), class_, float(median_class_throughput)])

        # self.plot_flow_throughput_class_distribution(traffic_profile_name,
        #                                              traffic_profile_subprofile_id,
        #                                              traffic_profile_seed,
        #                                              classes,
        #                                              traffic_profile_flows['number_classes'],
        #                                              traffic_profile_flows['number_flows'])

        print('classes boundaries: {}'.format(traffic_profile_flows['class_boundaries']))
        print('flow distribution (classes): {}'.format(np.bincount(classes)))
        print('flow load (sum flow throughputs): {}'.format(np.sum(np.array([x[0] for x in flow_throughputs]))))
        for class_ in range(traffic_profile_flows['number_classes']):
            sum_real = np.sum(np.array([x[0] for x in flow_throughputs if x[1] == class_]))
            print('sum flow load (class {}, real): {}'.format(class_, sum_real))
            sum_median = np.sum(np.array([x[2] for x in flow_throughputs if x[1] == class_]))
            print('sum flow load (class {}, median): {}'.format(class_, sum_median))
        print('sum flow load (median per classes, before error application): '
              '{}'.format(np.sum(np.array([x[2] for x in flow_throughputs]))))
        # flow_throughputs = self._apply_prediction_error(flow_throughputs=flow_throughputs,
        #                                                 traffic_profile_data=traffic_profile_data)
        print('sum flow load (median per classes, after error application): '
              '{}'.format(np.sum(np.array([x[2] for x in flow_throughputs]))))

        self.np_random.shuffle(flow_throughputs)
        # np.random.shuffle(flow_throughputs)

        return flow_throughputs

    def _apply_prediction_error(self, flow_throughputs, traffic_profile_data):
        num_error_flows = int(round(traffic_profile_data['number_flows'] * \
                                    traffic_profile_data['prediction_error_rate']))

        # error_flows_i = random.sample(population=range(traffic_profile_data['number_flows']), k=num_error_flows)
        error_flows_i = self.np_random.choice(traffic_profile_data['number_flows'], num_error_flows)

        for error_flow_i in error_flows_i:
            class_ = flow_throughputs[error_flow_i][1]
            other_classes = [x for x in range(traffic_profile_data['number_classes']) if x != class_]
            # error_class = random.sample(population=other_classes, k=1)
            error_class = int(self.np_random.choice(other_classes, 1))
            flow_throughputs[error_flow_i][1] = error_class
            median_class_throughput = (traffic_profile_data['class_boundaries'][error_class] +
                                       traffic_profile_data['class_boundaries'][error_class + 1]) / 2
            flow_throughputs[error_flow_i][2] = float(median_class_throughput)

        return flow_throughputs

    def plot_flow_throughput_class_distribution(self, traffic_profile_name,
                                                traffic_profile_subprofile_id,
                                                traffic_profile_seed,
                                                classes, num_classes, num_flows):
        plt.rc('text', usetex=True)
        plt.rc('font', family='serif')

        plt.figure(figsize=(3.5, 1.6))
        ax = plt.gca()

        plt.plot(np.bincount(classes),
                 color='blue',
                 linewidth=.5,
                 linestyle='-',
                 zorder=1)

        plt.grid(True, which='major', linewidth=.5)
        for axis in ['top', 'bottom', 'left', 'right']:
            ax.spines[axis].set_linewidth(0.5)

        ax.tick_params(axis='x', which='minor', bottom=True)
        plt.xticks(fontsize=8)
        ax.tick_params(axis='y', which='minor', bottom=False)
        plt.yticks(fontsize=8)
        ax.tick_params(which='both', width=0.5)

        plt.minorticks_on()
        ax.set_axisbelow(True)

        plt.xticks(np.arange(num_classes))
        plt.yticks(range(0, num_flows, 100))

        ax.set_xlabel('flow throughput class', fontsize=10)
        ax.set_ylabel('flow count', fontsize=10)

        plt.tight_layout(pad=0.05)

        plt.savefig('{}_{}_{}.pdf'.format(traffic_profile_name, traffic_profile_seed, traffic_profile_subprofile_id))
        plt.show()
        plt.close('all')

    def clear_traffic_profiles_directory(self):
        traffic_profiles_keep = ['example_scenario1.yaml', 'example_scenario2.yaml', 'verification_example.yaml']
        for traffic_profile in os.listdir(self.YAML_FILE_DIR):
            if traffic_profile in traffic_profiles_keep:
                continue
            traffic_profile_path = os.path.join(self.YAML_FILE_DIR, traffic_profile)
            if os.path.isfile(traffic_profile_path):
                os.remove(traffic_profile_path)
            elif os.path.isdir(traffic_profile_path):
                shutil.rmtree(traffic_profile_path)


if __name__ == '__main__':
    traffic_profile_generator = TrafficProfileGenerator()
    traffic_profile_generator.clear_traffic_profiles_directory()
    for i, traffic_profile in enumerate(traffic_profiles.items()):
        traffic_profile_name = traffic_profile[0]
        traffic_profile_data = traffic_profile[1]
        for traffic_profile_seed in traffic_profile_data['seeds']:
            traffic_profile_generator.generate_traffic_profile(traffic_profile_name=traffic_profile_name,
                                                               traffic_profile_seed=traffic_profile_seed,
                                                               traffic_profile_data=traffic_profile_data)


class TrafficProfileGenerationException(Exception):

    def __init__(self, message):
        super(TrafficProfileGenerationException, self).__init__(self.__class__.__name__ + ': ' + message)
