# Copyright 2017-present Open Networking Foundation
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
# modified by Christoph Hardegen
#             (christoph.hardegen@cs.hs-fulda.de)
#             Fulda University of Applied Sciences
#
################################################################################################
# adapted from P4 language tutorials                                                           #
# see https://github.com/p4lang/tutorials/blob/master/utils/p4runtime_lib/simple_controller.py #
################################################################################################

import json
import os

import switch
import helper as p4info_help

from tools.log.log import log


def check_switch_config(switch_config, work_dir):
    if 'target' not in switch_config:
        raise P4RuntimeConfigException("missing key 'target' in switch runtime config")
    target = switch_config['target']
    if target != 'bmv2':
        raise P4RuntimeConfigException('unknown target in switch runtime config (' + target + ' instead of bmv2)')

    for config_key in ['p4info', 'bmv2_json']:
        if config_key not in switch_config or len(switch_config[config_key]) == 0:
            raise P4RuntimeConfigException('missing key {0} or empty value for key {0}'.format(config_key))

        config_file_path = os.path.join(work_dir, switch_config[config_key])
        if not os.path.exists(config_file_path):
            raise P4RuntimeConfigException('config file {} does not exist'.format(config_file_path))


def program_switch(switch_name, switch_addr, device_id, runtime_conf_file, p4init, work_dir, runtime_gRPC_log):
    def table_entry_to_string(flow):
        if 'match' in flow:
            match_str = ['{}={}'.format(mname, str(flow['match'][mname])) for mname in flow['match']]
            match_str = ', '.join(match_str)
        elif 'default_action' in flow and flow['default_action']:
            match_str = '(default action)'
        else:
            match_str = '(any)'
        params = ['{}={}'.format(pname, str(flow['action_params'][pname])) for pname in flow['action_params']]
        params = ', '.join(params)
        return '{}: {} => {}({})'.format(flow['table'], match_str, flow['action_name'], params)

    def group_entry_to_string(rule):
        group_id = rule['multicast_group_id']
        replicas = [replica['egress_port'] for replica in rule['replicas']]
        ports_str = ', '.join(replicas)
        return 'group {0} => ({1})'.format(group_id, ports_str)

    switch_config = json_load_byteified(runtime_conf_file)

    try:
        check_switch_config(switch_config=switch_config, work_dir=work_dir)
    except P4RuntimeConfigException as ex:
        raise P4RuntimeConfigException('parsing the runtime configuration failed: ' + str(ex))

    log.info('applying p4info file ' + switch_config['p4info'] + ' to ' + switch_name)
    p4info_file = os.path.join(work_dir, switch_config['p4info'])
    p4info_helper = p4info_help.P4InfoHelper(p4info_file)

    log.info('connecting to p4runtime server on ' + switch_addr + ' (' + switch_name + ')')
    p4switch = switch.Bmv2SwitchConnection(switch_addr=switch_addr, device_id=device_id,
                                           runtime_gRPC_log=runtime_gRPC_log)
    try:
        p4switch.master_arbitration_update()

        log.info('applying pipeline config ' + switch_config['bmv2_json'] + ' to ' + switch_name)
        bmv2_json_file = os.path.join(work_dir, switch_config['bmv2_json'])
        p4switch.set_forwarding_pipeline_config(p4info=p4info_helper.p4info,
                                                bmv2_json_file=bmv2_json_file)

        if p4init in ['p4runtime_API', 'hybrid']:
            if 'table_entries' in switch_config:
                table_entries = switch_config['table_entries']
                log.info('inserting {} table entries'.format(len(table_entries)))
                for entry in table_entries:
                    log.info(table_entry_to_string(entry))
                    insert_table_entry(p4switch, p4info_helper, entry)

                    # if not 'default_action' in entry:
                    #     delete_table_entry(p4switch, entry, p4info_helper)

            if 'multicast_group_entries' in switch_config:
                group_entries = switch_config['multicast_group_entries']
                log.info('inserting {} group entries'.format(len(group_entries)))
                for entry in group_entries:
                    log.info(group_entry_to_string(entry))
                    insert_multicast_group_entry(p4switch, p4info_helper, entry)

                    # if not 'default_action' in entry:
                    #     delete_multicast_group_entry(p4switch, entry, p4info_helper)
    except Exception as ex:
        log.error(ex)
    finally:
        p4switch.shutdown()


# object hook for json library, use str instead of unicode object
# https://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-from-json
def json_load_byteified(file_handle):
    def _byteify(data, ignore_dicts=False):
        # if this is a unicode string, return its string representation
        if isinstance(data, unicode):
            return data.encode('utf-8')
        # if this is a list of values, return list of byteified values
        if isinstance(data, list):
            return [_byteify(item, ignore_dicts=True) for item in data]
        # if this is a dictionary, return dictionary of byteified keys and values
        # but only if we haven't already byteified it
        if isinstance(data, dict) and not ignore_dicts:
            return {_byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True) for key, value in
                    data.iteritems()}
        # if its anything else, return it in its original form
        return data

    return _byteify(json.load(file_handle, object_hook=_byteify), ignore_dicts=True)


def insert_table_entry(p4switch_connection, p4info_helper, flow):
    table_name = flow['table']
    match_fields = flow.get('match')  # None if not found
    action_name = flow['action_name']
    default_action = flow.get('default_action')  # None if not found
    action_params = flow['action_params']
    priority = flow.get('priority')  # None if not found

    table_entry = p4info_helper.build_table_entry(table_name=table_name,
                                                  match_fields=match_fields,
                                                  default_action=default_action,
                                                  action_name=action_name,
                                                  action_params=action_params,
                                                  priority=priority)

    p4switch_connection.write_table_entry(table_entry)


def delete_table_entry(p4switch_connection, p4info_helper, flow):
    table_name = flow['table']
    match_fields = flow.get('match')  # None if not found
    action_name = flow['action_name']
    default_action = flow.get('default_action')  # None if not found
    action_params = flow['action_params']
    priority = flow.get('priority')  # None if not found

    table_entry = p4info_helper.build_table_entry(table_name=table_name,
                                                  match_fields=match_fields,
                                                  default_action=default_action,
                                                  action_name=action_name,
                                                  action_params=action_params,
                                                  priority=priority)

    p4switch_connection.remove_table_entry(table_entry)


def insert_multicast_group_entry(p4switch_connection, p4info_helper, rule):
    multicast_entry = p4info_helper.build_multicast_group_entry(rule['multicast_group_id'], rule['replicas'])
    p4switch_connection.write_multicast_group_entry(multicast_entry)


def delete_multicast_group_entry(p4switch_connection, p4info_helper, rule):
    multicast_entry = p4info_helper.build_multicast_group_entry(rule['multicast_group_id'], rule['replicas'])
    p4switch_connection.delete_multicast_group_entry(multicast_entry)


def get_table_entries(p4switch_connection, p4info_helper, table_name, show=False):
    def table_entry_to_string(flow):
        if 'match' in flow:
            match_str = ['{}={}'.format(mname, str(flow['match'][mname])) for mname in flow['match']]
            match_str = ', '.join(match_str)
        elif 'default_action' in flow and flow['default_action']:
            match_str = '(default action)'
        else:
            match_str = '(any)'
        params = ['{}={}'.format(pname, str(flow['action_params'][pname])) for pname in flow['action_params']]
        params = ', '.join(params)
        return '{}: {} => {}({})'.format(flow['table'], match_str, flow['action_name'], params)

    # def group_entry_to_string(rule):
    #     group_id = rule['multicast_group_id']
    #     replicas = [replica['egress_port'] for replica in rule['replicas']]
    #     ports_str = ', '.join(replicas)
    #     return 'group {0} => ({1})'.format(group_id, ports_str)

    table_entries = []
    for result in p4switch_connection.get_table_entries(p4info_helper.get_tables_id(table_name)):
        for entity in result.entities:
            table_entry = entity.table_entry
            table_entries.append(table_entry)
            # log.info(table_entry_to_string(table_entry))
    if show:
        print(table_entries)
    return table_entries


def get_counters(p4switch_connection, p4info_helper, counter_name, index=None, show=False):
    counters = []
    for result in p4switch_connection.get_counters(p4info_helper.get_counters_id(counter_name), index):
        for entity in result.entities:
            counter_entry = entity.counter_entry
            counters.append(counter_entry)
    if show:
        print(counters)
    return counters


class P4RuntimeConfigException(Exception):

    def __init__(self, message):
        super(P4RuntimeConfigException, self).__init__(self.__class__.__name__ + ': ' + message)
