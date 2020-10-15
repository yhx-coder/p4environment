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
#####################################################################################
# adapted from P4 language tutorials                                                #
# see https://github.com/p4lang/tutorials/blob/master/utils/p4runtime_lib/helper.py #
#####################################################################################

import re

import google.protobuf.text_format
from p4.v1 import p4runtime_pb2
from p4.config.v1 import p4info_pb2

from p4runtime.runtimeAPI.convert import encode


class P4InfoHelper(object):
    def __init__(self, p4_info_file):
        p4info = p4info_pb2.P4Info()
        with open(p4_info_file) as p4info_file:
            google.protobuf.text_format.Merge(p4info_file.read(), p4info)
        self.p4info = p4info

    def get(self, entity_type, name=None, id_=None):
        if name is not None and id_ is not None:
            raise AssertionError('name or id must be None')

        for object_ in getattr(self.p4info, entity_type):
            preamble = object_.preamble
            if name:
                if preamble.name == name or preamble.alias == name:
                    return object_
            else:
                if preamble.id == id_:
                    return object_

        if name:
            raise AttributeError('could not find name {} of type {}'.format(name, entity_type))
        else:
            raise AttributeError('could not find id {} of type {}'.format(id, entity_type))

    def get_id(self, entity_type, name):
        return self.get(entity_type, name=name).preamble.id

    def get_name(self, entity_type, id_):
        return self.get(entity_type, id_=id_).preamble.name

    def get_alias(self, entity_type, id_):
        return self.get(entity_type, id_=id_).preamble.alias

    def __getattr__(self, attr):
        # synthesize convenience functions for name to id lookups for top-level entities
        # e.g. get_tables_id(name_string) or get_actions_id(name_string)
        x = re.search(r'^get_(\w+)_id$', attr)
        if x:
            primitive = x.group(1)
            return lambda name: self.get_id(primitive, name)

        # synthesize convenience functions for id to name lookups
        # e.g. get_tables_name(id) or get_actions_name(id)
        x = re.search(r'^get_(\w+)_name$', attr)
        if x:
            primitive = x.group(1)
            return lambda id_: self.get_name(primitive, id_)

        raise AttributeError('{} object has no attribute {}'.format(self.__class__, attr))

    def get_match_field(self, table_name, name=None, id_=None):
        for table in self.p4info.tables:
            preamble = table.preamble
            if preamble.name == table_name:
                for match_field in table.match_fields:
                    if name is not None:
                        if match_field.name == name:
                            return match_field
                    elif id_ is not None:
                        if match_field.id == id_:
                            return match_field

        raise AttributeError('{} has no attribute {}'.format(table_name, name if name is not None else id_))

    def get_match_field_id(self, table_name, match_field_name):
        return self.get_match_field(table_name, name=match_field_name).id

    def get_match_field_name(self, table_name, match_field_id):
        return self.get_match_field(table_name, id_=match_field_id).name

    def get_match_field_pb(self, table_name, match_field_name, value):
        p4info_match = self.get_match_field(table_name, match_field_name)
        bit_width = p4info_match.bitwidth
        p4runtime_match = p4runtime_pb2.FieldMatch()
        p4runtime_match.field_id = p4info_match.id
        match_type = p4info_match.match_type
        if match_type == p4info_pb2.MatchField.EXACT:
            exact = p4runtime_match.exact
            exact.value = encode(value, bit_width)
        elif match_type == p4info_pb2.MatchField.LPM:
            lpm = p4runtime_match.lpm
            lpm.value = encode(value[0], bit_width)
            lpm.prefix_len = value[1]
        elif match_type == p4info_pb2.MatchField.TERNARY:
            lpm = p4runtime_match.ternary
            lpm.value = encode(value[0], bit_width)
            lpm.mask = encode(value[1], bit_width)
        elif match_type == p4info_pb2.MatchField.RANGE:
            lpm = p4runtime_match.range
            lpm.low = encode(value[0], bit_width)
            lpm.high = encode(value[1], bit_width)
        else:
            raise Exception('unsupported match type with type {}'.format(match_type))
        return p4runtime_match

    def get_match_field_value(self, match_field):
        match_type = match_field.WhichOneof('field_match_type')
        if match_type == 'valid':
            return match_field.valid.value
        elif match_type == 'exact':
            return match_field.exact.value
        elif match_type == 'lpm':
            return match_field.lpm.value, match_field.lpm.prefix_len
        elif match_type == 'ternary':
            return match_field.ternary.value, match_field.ternary.mask
        elif match_type == 'range':
            return match_field.range.low, match_field.range.high
        else:
            raise Exception('unsupported match type with type {}'.format(match_type))

    def get_action_param(self, action_name, name=None, id_=None):
        for action in self.p4info.actions:
            pre = action.preamble
            if pre.name == action_name:
                for param in action.params:
                    if name is not None:
                        if param.name == name:
                            return param
                    elif id_ is not None:
                        if param.id == id_:
                            return param
        raise AttributeError('action {} has no param {}, (has: {})'.format(action_name,
                                                                           name if name is not None else id_,
                                                                           action.params))

    def get_action_param_id(self, action_name, param_name):
        return self.get_action_param(action_name, name=param_name).id

    def get_action_param_name(self, action_name, param_id):
        return self.get_action_param(action_name, id_=param_id).name

    def get_action_param_pb(self, action_name, param_name, value):
        p4info_param = self.get_action_param(action_name, param_name)
        p4runtime_param = p4runtime_pb2.Action.Param()
        p4runtime_param.param_id = p4info_param.id
        p4runtime_param.value = encode(value, p4info_param.bitwidth)
        return p4runtime_param

    def build_table_entry(self, table_name, match_fields=None,
                          default_action=False, action_name=None, action_params=None,
                          priority=None):
        table_entry = p4runtime_pb2.TableEntry()
        table_entry.table_id = self.get_tables_id(table_name)

        if priority is not None:
            table_entry.priority = priority

        if match_fields:
            table_entry.match.extend([
                self.get_match_field_pb(table_name, match_field_name, value)
                for match_field_name, value in match_fields.iteritems()
            ])

        if default_action:
            table_entry.is_default_action = True

        if action_name:
            action = table_entry.action.action
            action.action_id = self.get_actions_id(action_name)
            if action_params:
                action.params.extend([
                    self.get_action_param_pb(action_name, field_name, value)
                    for field_name, value in action_params.iteritems()
                ])
        return table_entry

    def build_multicast_group_entry(self, multicast_group_id, replicas):
        multicast_entry = p4runtime_pb2.PacketReplicationEngineEntry()
        multicast_entry.multicast_group_entry.multicast_group_id = multicast_group_id
        for replica in replicas:
            replica_ = p4runtime_pb2.Replica()
            replica_.egress_port = replica['egress_port']
            replica_.instance = replica['instance']
            multicast_entry.multicast_group_entry.replicas.extend([replica_])
        return multicast_entry
