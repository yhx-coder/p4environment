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

from p4topos.p4topo_parser import TopologyArgumentParser

from itertools import product
from collections import OrderedDict

from experiments_data import experiments


def get_supported_params(args):
    return sorted(vars(args))


def get_supported_params_and_default_args(args):
    result = OrderedDict()

    for param_key, param_value in sorted(vars(args).items(), key=lambda x: x[0]):
        result[param_key] = param_value

    # print(result)
    return result


def complete_experiment_params(experiment_params, args):
    for param_key, param_value in get_supported_params_and_default_args(args=args).items():
        if param_key not in ['exp',
                             'traffic_profile',
                             'p4controller_flow_forwarding_metric'] and param_key not in experiment_params:
            experiment_params[param_key] = param_value

    return experiment_params


def build_parameter_combinations(experiment_params):
    single_argument_parameters = []
    multiple_arguments_parameters = {}

    flow_forwarding_parameters = []
    topology_traffic_profiles_parameters = []

    for param_key, param_value in experiment_params.items():
        if type(param_value) == list:
            multiple_arguments_parameters[param_key] = []
            for value in param_value:
                multiple_arguments_parameters[param_key].append({param_key: value})
        else:
            if param_key not in ['p4controller_flow_forwarding_strategy', 'topology']:
                single_argument_parameters.append({param_key: param_value})

    # print('single_argument_parameters', single_argument_parameters)
    # print('multiple_arguments_parameters', multiple_arguments_parameters)
    if 'p4controller_time_measurement' in experiment_params['p4controller_flow_forwarding_strategy']:
        time_measure = experiment_params['p4controller_flow_forwarding_strategy'].pop('p4controller_time_measurement')
        single_argument_parameters.append({'p4controller_time_measurement': time_measure})

    for strategy, strategy_metrics in experiment_params['p4controller_flow_forwarding_strategy'].items():
        for metrics in strategy_metrics.values():
            for metric in metrics:
                flow_forwarding_parameters.append([{'p4controller_flow_forwarding_strategy': strategy},
                                                   {'p4controller_flow_forwarding_metric': metric}])

    # print('flow_forwarding_parameters', flow_forwarding_parameters)

    for topology, traffic_profiles in experiment_params['topology'].items():
        for traffic_profiles in traffic_profiles.values():
            for traffic_profile in traffic_profiles:
                topology_traffic_profiles_parameters.append([{'topology': topology},
                                                             {'traffic_profile': traffic_profile}])

    # print('topology_traffic_profiles_parameters', topology_traffic_profiles_parameters)

    parameter_combinations = []
    tmp = [combination for combination in apply(product, multiple_arguments_parameters.values())]
    tmp = map(list, tmp)
    for combination in tmp:
        combination += single_argument_parameters
    tmp = product(tmp, flow_forwarding_parameters, topology_traffic_profiles_parameters)
    for combination in tmp:
        experiment = []
        experiment += combination[0]
        experiment += combination[1]
        experiment += combination[2]
        parameter_combinations.append(experiment)

    # print('parameter_combinations', parameter_combinations)

    return parameter_combinations


def build_experiment_commands(command_template, parameter_combinations):
    experiment_commands = []
    for exp_id, experiment in enumerate(parameter_combinations):
        command = command_template
        command += '--{} {} '.format('exp', exp_id + 1)
        for param in sorted(experiment, key=lambda x: x):
            command += '--{} {} '.format(next(iter(param.keys())),
                                         next(iter(param.values())))  # param.keys()[0], param.values()[0]
        experiment_commands.append(command)
    return experiment_commands


def write_experiments(experiments_file, experiments):
    experiments_file = open(experiments_file, 'w')
    for experiment in experiments:
        experiments_file.write('{}\n'.format(experiment))
    experiments_file.close()

    # print('len(experiments)', len(experiments))


if __name__ == '__main__':
    parser = TopologyArgumentParser.create_parser()
    args, _ = parser.parse_known_args()

    command_template = 'sudo python p4runner.py '
    experiment_params = experiments
    experiments_file = 'experiments.txt'

    complete_experiment_params(experiment_params=experiment_params, args=args)
    parameter_combinations = build_parameter_combinations(experiment_params=experiment_params)
    experiments = build_experiment_commands(command_template=command_template,
                                            parameter_combinations=parameter_combinations)
    write_experiments(experiments_file=experiments_file, experiments=experiments)
