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

import os
import sys
import csv
import yaml
import numpy as np
import re

if __name__ == '__main__':
    import sys
    import os

    if os.path.abspath('../../../') not in sys.path:
        sys.path.append('../../../')

from p4topos.p4topo_parser import TopologyArgumentParser
import pickle
import gzip

from enum import Enum

import matplotlib.pyplot as plt

color_list = ['blue',
              'orange',
              'forestgreen',
              'red',
              'darkturquoise',
              'purple',
              'lightcoral',
              'saddlebrown',
              'crimson',
              'gold',
              'firebrick',
              'green',
              'purple',
              'skyblue',
              'lightgreen',
              'pink',
              'cyan',
              'gold',
              'lime',
              'cornflowerblue',
              'midnightblue',
              'orchid',
              'lightpink',
              'palegreen',
              'darkorange',
              'mediumblue',
              'grey',
              'black']

marker_list = ['o',
               's',
               'D',
               'H',
               '^',
               'v',
               '<',
               '>',
               'p',
               'X']

EXP_PARAMS_FILE = os.path.join(os.pardir, 'experiments.txt')
EXP_INPUT_DIR = 'input'
EXP_OUTPUT_DIR = 'output'
EXP_RESULTS_FILE = os.path.join(EXP_INPUT_DIR, 'experiments_results')

TRAFFIC_PROFILES_DIR = os.path.join(os.pardir, os.pardir, 'traffic_profiles', 'profiles')

AGGREGATED_ITERATION_ID = 9999


class Plots(Enum):
    LINK_LOAD = 'link_load'
    PATH_LOAD = 'path_load'


PATHS = {'flow_routing_1': {'P1': ['s1-s2', 's2-s11'],
                            'P2': ['s1-s3', 's3-s4', 's4-s11'],
                            'P3': ['s1-s5', 's5-s6', 's6-s11'],
                            'P4': ['s1-s7', 's7-s8', 's8-s11'],
                            'P5': ['s1-s9', 's9-s10', 's10-s11']},
         'flow_routing_2': {'P1': ['s1-s2', 's2-s7'],
                            'P2': ['s1-s3', 's3-s7'],
                            'P3': ['s1-s4', 's4-s7'],
                            'P4': ['s1-s5', 's5-s7'],
                            'P5': ['s1-s6', 's6-s7']}}


def pickle_data_gz(filename, data):
    with gzip.GzipFile(filename, 'wb') as file:
        pickle.dump(data, file, pickle.HIGHEST_PROTOCOL)


def pickle_data(filename, data):
    with open(filename, 'wb') as file:
        pickle.dump(data, file, protocol=pickle.HIGHEST_PROTOCOL)


def unpickle_data_gz(filename):
    with gzip.open(filename, 'rb') as file:
        return pickle.load(file)


def unpickle_data(filename):
    with open(filename, 'rb') as file:
        return pickle.load(file)


def read_command_params(command_file):
    # if os.path.isfile('{}.pkl'.format(command_file)):
    #     return unpickle_data('{}.pkl'.format(command_file))

    parser = TopologyArgumentParser.create_parser(all_parameters=True)

    result = {}
    with open(command_file, 'r') as cmd_file:
        for line in cmd_file:
            line_ = line.split('.py ', 1)[1]
            splitted_line = line_.split(' ')
            sys.argv = ['filename'] + splitted_line
            args, _ = parser.parse_known_args()
            result[args.exp] = vars(args)

            traffic_profile_files = sorted([yaml_file for yaml_file in os.listdir(TRAFFIC_PROFILES_DIR) if
                                            re.match(r'{}_\d*.yaml'.format(args.traffic_profile), yaml_file)])

            result[args.exp]['replay_num_flows'] = []
            result[args.exp]['replay_flow_batch_size'] = []
            result[args.exp]['flow_replay_seed'] = []

            for traffic_profile_file in traffic_profile_files:
                with open(os.path.join(TRAFFIC_PROFILES_DIR, traffic_profile_file), 'r') as yaml_file:
                    yaml_content = yaml.safe_load(yaml_file)
                result[args.exp]['replay_num_flows'].append(yaml_content[1]['num'])
                result[args.exp]['replay_flow_batch_size'].append(yaml_content['flow_batch_size'])
                result[args.exp]['flow_replay_seed'].append(yaml_content['seed'])

    # pickle_data('{}.pkl'.format(EXP_PARAMS_FILE), result)

    return result


def read_output(output_file):
    # if os.path.isfile('{}.npy'.format(output_file)):
    #     return np.load('{}.npy'.format(output_file), allow_pickle=True)

    with open(output_file, 'r') as csv_file:
        output = []
        for row in csv.reader(csv_file):
            if row:
                row = [float(val) for val in row]
                output += [row]
        csv_file = np.array(output)
    # np.save('{}.npy'.format(output_file), csv_file)
    return csv_file


def load_results(input_dir, experiments_results_file):
    # if os.path.isfile('{}.pkl'.format(experiments_results_file)):
    #     return unpickle_data('{}.pkl'.format(experiments_results_file))

    experiment_results = {}

    for exp in [x for x in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir, x))]:
        experiment_results[exp] = {}

        for data_source in os.listdir(os.path.join(input_dir, exp)):
            experiment_results[exp][data_source] = {}

            for exp_iter in os.listdir(os.path.join(input_dir, exp, data_source)):
                experiment_results[exp][data_source][exp_iter] = {}

                for output_file in os.listdir(os.path.join(input_dir, exp, data_source, exp_iter)):
                    if not output_file.endswith('.csv'):
                        continue

                    link = output_file.split('.')[0]

                    output_file = os.path.join(input_dir, exp, data_source, exp_iter, output_file)

                    output_file_data = read_output(output_file=output_file)

                    timestamps = output_file_data[:, 0].astype(np.float)
                    load = output_file_data[:, 1].astype(np.float)
                    load = np.where(load <= 1.0, load, 1.0)

                    min_ = min(len(timestamps), len(load))

                    experiment_results[exp][data_source][exp_iter][link] = {'timestamps': timestamps[:min_],
                                                                            'load': load[:min_]}

    # pickle_data('{}.pkl'.format(experiments_results_file), experiment_results)

    return experiment_results


def plot_exps(exp_params, exp_results):
    for exp in exp_results:
        for data_source in exp_results[exp]:
            for exp_iter in exp_results[exp][data_source]:
                plot(int(exp), data_source, int(exp_iter),  # LINK_LOAD
                     exp_results[exp][data_source][exp_iter],
                     exp_params, Plots.LINK_LOAD)
                plot(int(exp), data_source, int(exp_iter),  # PATH_LOAD
                     exp_results[exp][data_source][exp_iter],
                     exp_params, Plots.PATH_LOAD)

            if len(exp_params[int(exp)]['flow_replay_seed']) == 1:
                aggregated_results_links = {}
                first_exp_iter = sorted(exp_results[exp][data_source])[0]
                for link in exp_results[exp][data_source][first_exp_iter]:
                    aggregated_results_links[link] = {
                        'load': None,
                        'timestamps': exp_results[exp][data_source][first_exp_iter][link]['timestamps']
                    }
                    aggregated_results_link = None
                    for exp_iter in exp_results[exp][data_source]:
                        if aggregated_results_link is None:
                            aggregated_results_link = exp_results[exp][data_source][exp_iter][link]['load']
                        else:
                            aggregated_results_link = np.vstack((aggregated_results_link,
                                                                 exp_results[exp][data_source][exp_iter][link]['load']))
                    aggregated_results_links[link]['load'] = np.mean(np.atleast_2d(aggregated_results_link), axis=0)
                plot(int(exp), data_source, AGGREGATED_ITERATION_ID,  # LINK_LOAD
                     aggregated_results_links,
                     exp_params, Plots.LINK_LOAD)
                plot(int(exp), data_source, AGGREGATED_ITERATION_ID,  # PATH_LOAD
                     aggregated_results_links,
                     exp_params, Plots.PATH_LOAD)


def plot(exp, data_source, exp_iter, exp_results, exp_params, plot_type):
    plt.rc('text', usetex=True)
    plt.rc('font', family='serif')

    plt.figure(figsize=(3.5, 1.6))
    ax = plt.gca()

    max_timestamp = 0

    if plot_type == Plots.LINK_LOAD:
        for i, link in enumerate(exp_results):
            load_data = exp_results[link]
            # ax.plot(load_data['timestamps'], map(lambda x: x*100, load_data['load']),
            ax.plot(load_data['timestamps'], load_data['load'],
                    label=r'{}\,({}\,\%)'.format(link, load_data['load'].max()),
                    color=color_list[i],
                    linewidth=.5,
                    linestyle='-',
                    zorder=1)
            if load_data['timestamps'][-1] > max_timestamp:
                max_timestamp = load_data['timestamps'][-1]

    final_path_loads = []
    if plot_type == Plots.PATH_LOAD:
        for i, path in enumerate(sorted(PATHS[exp_params[exp]['topology']])):
            links = PATHS[exp_params[exp]['topology']][path]

            # use data of the first link belonging to the considered path as representative data for the entire path
            path_timestamps = exp_results[links[0]]['timestamps']
            # print('path_timestamps', path_timestamps)
            path_load = exp_results[links[0]]['load']
            # print('path_load', path_load)

            path_label_part = r',\,'.join([link.split('-')[0] for link in links[:-1]])
            path_label_part += r',\,'
            path_label_part += r',\,'.join(links[-1].split('-'))
            # ax.plot(path_timestamps, map(lambda x: x*100, path_load),
            ax.plot(path_timestamps, path_load,
                    # label=r'{}:\,{} ({}\,\%)'.format(path, path_label_part, max(path_load * 100)),
                    # label=r'{}:\,{}'.format(path, path_label_part),
                    label=r'{}'.format(path),
                    color=color_list[i],
                    marker=marker_list[i],
                    markersize=1,
                    # markeredgewidth=.1,
                    # markeredgecolor='k',
                    # markerfacecolor='w',
                    linewidth=.5,
                    linestyle='-',
                    zorder=1)
            if max(path_timestamps) > max_timestamp:
                max_timestamp = max(path_timestamps)

            if len(exp_params[exp]['flow_replay_seed']) == 1:  # one seed for each experiment iteration
                replay_num_flows = exp_params[exp]['replay_num_flows'][0]
                replay_flow_batch_size = exp_params[exp]['replay_flow_batch_size'][0]
            else:  # individual seeds for each experiment iteration
                replay_num_flows = exp_params[exp]['replay_num_flows'][exp_iter]
                replay_flow_batch_size = exp_params[exp]['replay_flow_batch_size'][exp_iter]
            final_path_load_start = replay_num_flows // replay_flow_batch_size
            final_path_loads.append(np.mean(path_load[final_path_load_start:]))

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

    ax.set_xlim(0, max_timestamp)
    # ax.set_ylim(0, 100)
    ax.set_ylim(0.0, 1.0)

    ax.set_xlabel('elapsed time (s)', fontsize=10)
    if plot_type == Plots.LINK_LOAD:
        # ax.set_ylabel('link load (\%)', fontsize=10)
        ax.set_ylabel('link load (ratio)', fontsize=10)

    min_path_load = None
    max_path_load = None
    mean_path_load = None
    median_path_load = None
    sum_path_loads = None
    if plot_type == Plots.PATH_LOAD:
        # ax.set_ylabel('path load (\%)', fontsize=10)
        ax.set_ylabel('path load (ratio)', fontsize=10)

        import copy
        handles, labels = ax.get_legend_handles_labels()
        handles = [copy.copy(ha) for ha in handles]
        [ha.set_linewidth(.5) for ha in handles]
        legend = plt.legend(handles=handles,
                            labels=labels,
                            fontsize=6,
                            edgecolor='black',
                            loc='lower right',
                            ncol=3,
                            framealpha=1,
                            borderpad=0.3,
                            labelspacing=.2,
                            handlelength=1)
        frame = legend.get_frame()
        frame.set_linewidth(0.5)

        min_path_load = np.min(final_path_loads)
        max_path_load = np.max(final_path_loads)
        mean_path_load = np.mean(final_path_loads)
        median_path_load = np.median(final_path_loads)
        sum_path_loads = np.sum(final_path_loads)

    plt.tight_layout(pad=0.05)

    out_dir = os.path.join(EXP_OUTPUT_DIR, str(exp), data_source, str(exp_iter))
    try:
        os.makedirs(out_dir)
    except:
        pass

    if plot_type == Plots.PATH_LOAD:
        with open(os.path.join(out_dir, 'final_path_loads.csv'), 'w') as file_:
            file_.write('\n'.join(['Path Load Stats',
                                   'Minimum: {:.2f}%'.format(min_path_load * 100),
                                   'Maximum: {:.2f}%'.format(max_path_load * 100),
                                   'Mean: {:.2f}%'.format(mean_path_load * 100),
                                   'Median: {:.2f}%'.format(median_path_load * 100),
                                   'Sum: {:.2f} Mbit/s'.format(sum_path_loads)]))

    if len(exp_params[exp]['flow_replay_seed']) == 1:  # one seed for each experiment iteration
        plt.savefig(os.path.join(out_dir, '{}_{}.pdf'.format(plot_type, exp_params[exp]['flow_replay_seed'][0])))
    else:  # individual seeds for each experiment iteration
        plt.savefig(os.path.join(out_dir, '{}_{}.pdf'.format(plot_type, exp_params[exp]['flow_replay_seed'][exp_iter])))
    plt.close('all')


if __name__ == '__main__':
    exp_params = read_command_params(command_file=EXP_PARAMS_FILE)
    exp_results = load_results(input_dir=EXP_INPUT_DIR, experiments_results_file=EXP_RESULTS_FILE)
    plot_exps(exp_params=exp_params, exp_results=exp_results)
