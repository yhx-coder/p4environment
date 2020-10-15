import os
import subprocess
from time import sleep
import re

EXPERIMENTS_FILE = 'tools/experiments/experiments.txt'
EXPERIMENTS_ITERATIONS = 10
EXPERIMENTS_SLEEP_AFTER = 2

TRAFFIC_PROFILES_DIR = 'tools/traffic_profiles/profiles/'

DEV_NULL = open(os.devnull, 'w')

with open(EXPERIMENTS_FILE, 'r') as cmd_file:
    for cmd in cmd_file:
        traffic_profile_pattern = re.search(r'--traffic_profile\s(\w*)\s', cmd).group(1)
        traffic_profile_files = sorted([yaml_file for yaml_file in os.listdir(TRAFFIC_PROFILES_DIR) if
                                        re.match(r'{}_\d*.yaml'.format(traffic_profile_pattern), yaml_file)])
        if len(traffic_profile_files) == 1:
            # one seed for each experiment iteration
            traffic_profile_files = [traffic_profile_files[0] for _ in range(EXPERIMENTS_ITERATIONS)]
        else:  # individual seeds for each experiment iteration
            pass

        print('#begin experiment')
        for experiment_iteration in range(EXPERIMENTS_ITERATIONS):
            if experiment_iteration > len(traffic_profile_files) - 1:
                # multiple seeds but less than number of experiment iterations
                break
            print('#experiment iteration: {}'.format(experiment_iteration))
            exp_cmd = cmd.strip() + ' --exp_iter {}'.format(experiment_iteration)
            exp_cmd = exp_cmd.replace(traffic_profile_pattern, traffic_profile_files[experiment_iteration])
            print('#experiment command: {}'.format(exp_cmd))
            subprocess.call(exp_cmd, shell=True, stdout=DEV_NULL, stderr=DEV_NULL)
            sleep(EXPERIMENTS_SLEEP_AFTER)
        print('#end experiment\n')
