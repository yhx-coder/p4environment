# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# Antonin Bas (antonin@barefootnetworks.com)
#
# initially modified by Edgar Costa (cedgar@ethz.ch)
#
# modified by Christoph Hardegen
#             (christoph.hardegen@cs.hs-fulda.de)
#             Fulda University of Applied Sciences
#
#####################################################################################
# adapted from p4utils version of NSG @ ETHZ                                        #
# see https://github.com/nsg-ethz/p4-utils/blob/master/p4utils/utils/sswitch_API.py #
#####################################################################################

import p4runtime.runtimeCLI.runtime_CLI as runtimeCLI
from sswitch_runtime import SimpleSwitch
from sswitch_runtime.ttypes import *

from functools import wraps


def handle_bad_input(f):
    @wraps(f)
    @runtimeCLI.handle_bad_input
    def handle(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except InvalidMirroringOperation as err:
            error = MirroringOperationErrorCode._VALUES_TO_NAMES[err.code]
            print('invalid mirroring operation ({})'.format(error))

    return handle


class SimpleSwitchAPI(runtimeCLI.RuntimeAPI):

    @staticmethod
    def get_thrift_services():
        return [('simple_switch', SimpleSwitch.Client)]

    def __init__(self, thrift_ip, thrift_port, switch, switch_log_file, json_path=None):

        pre_type = runtimeCLI.PreType.SimplePreLAG

        runtimeCLI.RuntimeAPI.__init__(self, thrift_ip, thrift_port, switch, switch_log_file, pre_type, json_path)

        self.simple_switch_client = runtimeCLI.thrift_connect(thrift_ip, thrift_port,
                                                              SimpleSwitchAPI.get_thrift_services())[0]

    def parse_int(self, arg, name):
        try:
            return int(arg)
        except:
            raise runtimeCLI.UIn_Error('bad format for {}, expected integer'.format(name))

    @handle_bad_input
    def set_queue_depth(self, queue_depth_packets, egress_port=None):
        "set depth of one/all egress queue(s): set_queue_depth <nb_pkts> [<egress_port>]"
        self.write_to_log_file('set_queue_depth {} [{}]'.format(queue_depth_packets, egress_port))

        depth = self.parse_int(queue_depth_packets, 'queue_depth')
        if egress_port:
            egress_port = self.parse_int(egress_port, 'egress_port')
            self.simple_switch_client.set_egress_queue_depth(egress_port, depth)
        else:
            self.simple_switch_client.set_all_egress_queue_depths(depth)

    @handle_bad_input
    def set_queue_rate(self, rate_pps, egress_port=None):
        "set rate of one/all egress queue(s): set_queue_rate <rate_pps> [<egress_port>]"
        self.write_to_log_file('set_queue_rate {} [{}]'.format(rate_pps, egress_port))

        rate = self.parse_int(rate_pps, 'rate_pps')
        if egress_port:
            egress_port = self.parse_int(egress_port, 'egress_port')
            self.simple_switch_client.set_egress_queue_rate(egress_port, rate)
        else:
            self.simple_switch_client.set_all_egress_queue_rates(rate)

    @handle_bad_input
    def mirroring_add(self, mirror_id, egress_port):
        "add mirroring mapping: mirroring_add <mirror_id> <egress_port>"
        self.write_to_log_file('mirroring_add {} {}'.format(mirror_id, egress_port))

        mirror_id, egress_port = self.parse_int(mirror_id, 'mirror_id'), self.parse_int(egress_port, 'egress_port')
        config = MirroringSessionConfig(port=egress_port)
        self.simple_switch_client.mirroring_session_add(mirror_id, config)

    @handle_bad_input
    def mirroring_add_mc(self, mirror_id, mgrp):
        "add mirroring session to multicast group: mirroring_add_mc <mirror_id> <mgrp>"
        self.write_to_log_file('mirroring_add_mc {} {}'.format(mirror_id, mgrp))

        mirror_id, mgrp = self.parse_int(mirror_id, 'mirror_id'), self.parse_int(mgrp, 'mgrp')
        config = MirroringSessionConfig(mgid=mgrp)
        self.simple_switch_client.mirroring_session_add(mirror_id, config)

    @handle_bad_input
    def mirroring_delete(self, mirror_id):
        "delete mirroring mapping: mirroring_delete <mirror_id>"
        self.write_to_log_file('mirroring_delete {}'.format(mirror_id))

        mirror_id = self.parse_int(mirror_id, 'mirror_id')
        self.simple_switch_client.mirroring_session_delete(mirror_id)

    @handle_bad_input
    def mirroring_get(self, mirror_id, show=False):
        "display mirroring session: mirroring_get <mirror_id>"
        self.write_to_log_file('mirroring_get {}'.format(mirror_id))

        mirror_id = self.parse_int(mirror_id, 'mirror_id')
        config = self.simple_switch_client.mirroring_session_get(mirror_id)

        self.write_to_log_file(config)
        if show:
            print(config)

        return config

    @handle_bad_input
    def get_time_elapsed(self, show=False):
        "get time elapsed (in microseconds) since the switch started: get_time_elapsed"
        self.write_to_log_file('get_time_elapsed')

        time_elapsed_us = self.simple_switch_client.get_time_elapsed_us()

        self.write_to_log_file(time_elapsed_us)
        if show:
            print(time_elapsed_us)

        return time_elapsed_us

    @handle_bad_input
    def get_time_since_epoch(self, show=False):
        "get time elapsed (in microseconds) since the switch clock's epoch: get_time_since_epoch"
        self.write_to_log_file('get_time_since_epoch')

        time_since_epoch_us = self.simple_switch_client.get_time_since_epoch_us()

        self.write_to_log_file(time_since_epoch_us)
        if show:
            print(time_since_epoch_us)

        return time_since_epoch_us
