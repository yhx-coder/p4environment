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
import csv
import numpy as np

TIME_MEASURE_FILE = 'time_measure.csv'
TIME_MEASURE_INPUT_DIR = 'input'
TIME_MEASURE_OUTPUT_DIR = 'output'

AGGREGATED_ITERATION_ID = 9999


def process_results(input_dir):
    for exp in [x for x in os.listdir(input_dir) if os.path.isdir(os.path.join(input_dir, x))]:
        aggregated_time_measures = None
        for exp_iter in os.listdir(os.path.join(input_dir, exp)):
            output_file = os.path.join(input_dir, exp, exp_iter, TIME_MEASURE_FILE)
            with open(output_file, 'r') as csv_file:
                output_file_data = np.array(next(csv.reader(csv_file))).astype(np.float)

            if aggregated_time_measures is None:
                aggregated_time_measures = output_file_data
            else:
                aggregated_time_measures = np.vstack((aggregated_time_measures, output_file_data))
        aggregated_time_measures = np.mean(np.atleast_2d(aggregated_time_measures), axis=0)

        out_dir = os.path.join(TIME_MEASURE_OUTPUT_DIR, str(exp), str(AGGREGATED_ITERATION_ID))
        try:
            os.makedirs(out_dir)
        except:
            pass

        with open(os.path.join(out_dir, TIME_MEASURE_FILE), 'w') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(aggregated_time_measures)


if __name__ == '__main__':
    process_results(input_dir=TIME_MEASURE_INPUT_DIR)
