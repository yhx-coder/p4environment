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
# adapted from behavioral model and p4utils version of NSG @ ETHZ                   #
# see https://github.com/p4lang/behavioral-model/blob/master/tools/runtime_CLI.py   #
# see https://github.com/nsg-ethz/p4-utils/blob/master/p4utils/utils/runtime_API.py #
#####################################################################################

import logging
import traceback

from collections import Counter
import os
import struct
import json
from functools import wraps
import bmpy_utils as utils

from bm_runtime.standard import Standard
from bm_runtime.standard.ttypes import *

try:
    from bm_runtime.simple_pre import SimplePre
except:
    pass

try:
    from bm_runtime.simple_pre_lag import SimplePreLAG
except:
    pass


def enum(type_name, *sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.iteritems())

    @staticmethod
    def to_str(x):
        return reverse[x]

    enums['to_str'] = to_str

    @staticmethod
    def from_str(x):
        return enums[x]

    enums['from_str'] = from_str
    return type(type_name, (), enums)


PreType = enum('PreType',
               'None',
               'SimplePre',
               'SimplePreLAG')

MeterType = enum('MeterType',
                 'packets',
                 'bytes')

TableType = enum('TableType',
                 'simple',
                 'indirect',
                 'indirect_ws')

ResType = enum('ResType',
               'table',
               'action_prof',
               'action',
               'meter_array',
               'counter_array',
               'register_array',
               'parse_vset')


def bytes_to_string(byte_array):
    form = 'B' * len(byte_array)
    return struct.pack(form, *byte_array)


def table_error_name(x):
    return TableOperationErrorCode._VALUES_TO_NAMES[x]


TABLES = {}
ACTION_PROFS = {}
ACTIONS = {}
METER_ARRAYS = {}
COUNTER_ARRAYS = {}
REGISTER_ARRAYS = {}
CUSTOM_CRC_CALCS = {}
PARSE_VSETS = {}

# maps (object type, unique suffix) to object
SUFFIX_LOOKUP_MAP = {}


class MatchType:
    EXACT = 0
    LPM = 1
    TERNARY = 2
    VALID = 3
    RANGE = 4

    @staticmethod
    def to_str(x):
        return {0: 'exact',
                1: 'lpm',
                2: 'ternary',
                3: 'valid',
                4: 'range'}[x]

    @staticmethod
    def from_str(x):
        return {'exact': 0,
                'lpm': 1,
                'ternary': 2,
                'valid': 3,
                'range': 4}[x]


class Table:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.match_type_ = None
        self.actions = {}
        self.key = []
        self.default_action = None
        self.type_ = None
        self.support_timeout = False
        self.action_prof = None

        TABLES[name] = self

    def num_key_fields(self):
        return len(self.key)

    def key_str(self):
        return ',\t'.join([name + '(' + MatchType.to_str(t) + ', ' + str(bw) + ')' for name, t, bw in self.key])

    def table_str(self):
        ap_str = 'implementation={}'.format('None' if not self.action_prof else self.action_prof.name)
        return '{0:30} [{1}, mk={2}]'.format(self.name, ap_str, self.key_str())

    def get_action(self, action_name):
        key = ResType.action, action_name
        action = SUFFIX_LOOKUP_MAP.get(key, None)
        if action is None or action.name not in self.actions:
            return None
        return action


class ActionProf:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.with_selection = False
        self.actions = {}
        self.ref_cnt = 0

        ACTION_PROFS[name] = self

    def action_prof_str(self):
        return '{0:30} [{1}]'.format(self.name, self.with_selection)

    def get_action(self, action_name):
        key = ResType.action, action_name
        action = SUFFIX_LOOKUP_MAP.get(key, None)
        if action is None or action.name not in self.actions:
            return None
        return action


class Action:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.runtime_data = []

        ACTIONS[name] = self

    def num_params(self):
        return len(self.runtime_data)

    def runtime_data_str(self):
        return ',\t'.join([name + '(' + str(bw) + ')' for name, bw in self.runtime_data])

    def action_str(self):
        return '{0:30} [{1}]'.format(self.name, self.runtime_data_str())


class MeterArray:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.type_ = None
        self.is_direct = None
        self.size = None
        self.binding = None
        self.rate_count = None

        METER_ARRAYS[name] = self

    def meter_str(self):
        return '{0:30} [{1}, {2}]'.format(self.name, self.size, MeterType.to_str(self.type_))


class CounterArray:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.is_direct = None
        self.size = None
        self.binding = None

        COUNTER_ARRAYS[name] = self

    def counter_str(self):
        return '{0:30} [{1}]'.format(self.name, self.size)


class RegisterArray:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.width = None
        self.size = None

        REGISTER_ARRAYS[name] = self

    def register_str(self):
        return '{0:30} [{1}]'.format(self.name, self.size)


class ParseVSet:
    def __init__(self, name, id_):
        self.name = name
        self.id_ = id_
        self.bitwidth = None

        PARSE_VSETS[name] = self

    def parse_vset_str(self):
        return '{0:30} [compressed bitwidth:{1}]'.format(self.name, self.bitwidth)


def reset_config():
    TABLES.clear()
    ACTION_PROFS.clear()
    ACTIONS.clear()
    METER_ARRAYS.clear()
    COUNTER_ARRAYS.clear()
    REGISTER_ARRAYS.clear()
    CUSTOM_CRC_CALCS.clear()
    PARSE_VSETS.clear()

    SUFFIX_LOOKUP_MAP.clear()


def load_json_config(standard_client=None, json_path=None):
    load_json_str(utils.get_json_config(standard_client, json_path))


def load_json_str(json_str):
    def get_header_type(header_name, j_headers):
        for h in j_headers:
            if h['name'] == header_name:
                return h['header_type']
        assert 0

    def get_field_bitwidth(header_type, field_name, j_header_types):
        for h in j_header_types:
            if h['name'] != header_type: continue
            for t in h['fields']:
                # t can have a third element (field signedness)
                f, bw = t[0], t[1]
                if f == field_name:
                    return bw
        assert 0

    reset_config()
    json_ = json.loads(json_str)

    def get_json_key(key):
        return json_.get(key, [])

    for j_action in get_json_key('actions'):
        action = Action(j_action['name'], j_action['id'])
        for j_param in j_action['runtime_data']:
            action.runtime_data += [(j_param['name'], j_param['bitwidth'])]

    for j_pipeline in get_json_key('pipelines'):
        if 'action_profiles' in j_pipeline:  # new JSON format
            for j_aprof in j_pipeline['action_profiles']:
                action_prof = ActionProf(j_aprof['name'], j_aprof['id'])
                action_prof.with_selection = 'selector' in j_aprof

        for j_table in j_pipeline['tables']:
            table = Table(j_table['name'], j_table['id'])
            table.match_type = MatchType.from_str(j_table['match_type'])
            table.type_ = TableType.from_str(j_table['type'])
            table.support_timeout = j_table['support_timeout']
            for action in j_table['actions']:
                table.actions[action] = ACTIONS[action]

            if table.type_ in {TableType.indirect, TableType.indirect_ws}:
                if 'action_profile' in j_table:
                    action_prof = ACTION_PROFS[j_table['action_profile']]
                else:  # for backward compatibility
                    assert ('act_prof_name' in j_table)
                    action_prof = ActionProf(j_table['act_prof_name'], table.id_)
                    action_prof.with_selection = 'selector' in j_table
                action_prof.actions.update(table.actions)
                action_prof.ref_cnt += 1
                table.action_prof = action_prof

            for j_key in j_table['key']:
                target = j_key['target']
                match_type = MatchType.from_str(j_key['match_type'])
                if match_type == MatchType.VALID:
                    field_name = target + '_valid'
                    bitwidth = 1
                elif target[1] == '$valid$':
                    field_name = target[0] + '_valid'
                    bitwidth = 1
                else:
                    field_name = '.'.join(target)
                    header_type = get_header_type(target[0], json_['headers'])
                    bitwidth = get_field_bitwidth(header_type, target[1], json_['header_types'])
                table.key += [(field_name, match_type, bitwidth)]

    for j_meter in get_json_key('meter_arrays'):
        meter_array = MeterArray(j_meter['name'], j_meter['id'])
        if 'is_direct' in j_meter and j_meter['is_direct']:
            meter_array.is_direct = True
            meter_array.binding = j_meter['binding']
        else:
            meter_array.is_direct = False
            meter_array.size = j_meter['size']
        meter_array.type_ = MeterType.from_str(j_meter['type'])
        meter_array.rate_count = j_meter['rate_count']

    for j_counter in get_json_key('counter_arrays'):
        counter_array = CounterArray(j_counter['name'], j_counter['id'])
        counter_array.is_direct = j_counter['is_direct']
        if counter_array.is_direct:
            counter_array.binding = j_counter['binding']
        else:
            counter_array.size = j_counter['size']

    for j_register in get_json_key('register_arrays'):
        register_array = RegisterArray(j_register['name'], j_register['id'])
        register_array.size = j_register['size']
        register_array.width = j_register['bitwidth']

    for j_calc in get_json_key('calculations'):
        calc_name = j_calc['name']
        if j_calc['algo'] == 'crc16_custom':
            CUSTOM_CRC_CALCS[calc_name] = 16
        elif j_calc['algo'] == 'crc32_custom':
            CUSTOM_CRC_CALCS[calc_name] = 32

    for j_parse_vset in get_json_key('parse_vsets'):
        parse_vset = ParseVSet(j_parse_vset['name'], j_parse_vset['id'])
        parse_vset.bitwidth = j_parse_vset['compressed_bitwidth']

    # builds a dictionary mapping (object type, unique suffix) to the object (Table, Action, etc...).
    # in P4_16 the object name is the fully-qualified name, which can be quite long,
    # which is why we accept unique suffixes as valid identifiers.
    # auto-complete does not support suffixes, only the fully-qualified names,
    # but that can be changed in the future if needed.
    suffix_count = Counter()
    for res_type, res_dict in [
        (ResType.table, TABLES), (ResType.action_prof, ACTION_PROFS),
        (ResType.action, ACTIONS), (ResType.meter_array, METER_ARRAYS),
        (ResType.counter_array, COUNTER_ARRAYS),
        (ResType.register_array, REGISTER_ARRAYS),
        (ResType.parse_vset, PARSE_VSETS)]:
        for name, res in res_dict.items():
            suffix = None
            for s in reversed(name.split('.')):
                suffix = s if suffix is None else s + '.' + suffix
                key = (res_type, suffix)
                SUFFIX_LOOKUP_MAP[key] = res
                suffix_count[key] += 1
    for key, c in suffix_count.items():
        if c > 1:
            del SUFFIX_LOOKUP_MAP[key]


class UIn_Error(Exception):
    def __init__(self, info=''):
        self.info = info

    def __str__(self):
        return self.info


class UIn_ResourceError(UIn_Error):
    def __init__(self, res_type, name):
        self.res_type = res_type
        self.name = name

    def __str__(self):
        return 'invalid {} name ({})'.format(self.res_type, self.name)


class UIn_MatchKeyError(UIn_Error):
    def __init__(self, info=''):
        self.info = info

    def __str__(self):
        return self.info


class UIn_RuntimeDataError(UIn_Error):
    def __init__(self, info=''):
        self.info = info

    def __str__(self):
        return self.info


class CLI_FormatExploreError(Exception):
    def __init__(self):
        pass


class UIn_BadParamError(UIn_Error):
    def __init__(self, info=''):
        self.info = info

    def __str__(self):
        return self.info


class UIn_BadIPv4Error(UIn_Error):
    def __init__(self):
        pass


class UIn_BadIPv6Error(UIn_Error):
    def __init__(self):
        pass


class UIn_BadMacError(UIn_Error):
    def __init__(self):
        pass


def ipv4Addr_to_bytes(addr):
    if not '.' in addr:
        raise CLI_FormatExploreError()
    s = addr.split('.')
    if len(s) != 4:
        raise UIn_BadIPv4Error()
    try:
        return [int(b) for b in s]
    except:
        raise UIn_BadIPv4Error()


def macAddr_to_bytes(addr):
    if not ':' in addr:
        raise CLI_FormatExploreError()
    s = addr.split(':')
    if len(s) != 6:
        raise UIn_BadMacError()
    try:
        return [int(b, 16) for b in s]
    except:
        raise UIn_BadMacError()


def ipv6Addr_to_bytes(addr):
    from ipaddr import IPv6Address
    if not ':' in addr:
        raise CLI_FormatExploreError()
    try:
        ip = IPv6Address(addr)
    except:
        raise UIn_BadIPv6Error()
    try:
        return [ord(b) for b in ip.packed]
    except:
        raise UIn_BadIPv6Error()


def int_to_bytes(i, num):
    byte_array = []
    while i > 0:
        byte_array.append(i % 256)
        i = i / 256
        num -= 1
    if num < 0:
        raise UIn_BadParamError('parameter is too large')
    while num > 0:
        byte_array.append(0)
        num -= 1
    byte_array.reverse()
    return byte_array


def parse_param(input_str, bitwidth):
    if bitwidth == 32:
        try:
            return ipv4Addr_to_bytes(input_str)
        except CLI_FormatExploreError:
            pass
        except UIn_BadIPv4Error:
            raise UIn_BadParamError('invalid IPv4 address')
    elif bitwidth == 48:
        try:
            return macAddr_to_bytes(input_str)
        except CLI_FormatExploreError:
            pass
        except UIn_BadMacError:
            raise UIn_BadParamError('invalid MAC address')
    elif bitwidth == 128:
        try:
            return ipv6Addr_to_bytes(input_str)
        except CLI_FormatExploreError:
            pass
        except UIn_BadIPv6Error:
            raise UIn_BadParamError('invalid IPv6 address')
    try:
        input_ = int(input_str, 0)
    except:
        raise UIn_BadParamError('invalid input, could not cast to integer, try in hex with 0x prefix')
    try:
        return int_to_bytes(input_, (bitwidth + 7) / 8)
    except UIn_BadParamError:
        raise


def parse_runtime_data(action, params):
    def parse_param_(field, bw):
        try:
            return parse_param(field, bw)
        except UIn_BadParamError as err:
            raise UIn_RuntimeDataError('error while parsing {} - {}'.format(field, err))

    bitwidths = [bw for (_, bw) in action.runtime_data]
    byte_array = []
    for input_str, bitwidth in zip(params, bitwidths):
        byte_array += [bytes_to_string(parse_param_(input_str, bitwidth))]
    return byte_array


_match_types_mapping = {
    MatchType.EXACT: BmMatchParamType.EXACT,
    MatchType.LPM: BmMatchParamType.LPM,
    MatchType.TERNARY: BmMatchParamType.TERNARY,
    MatchType.VALID: BmMatchParamType.VALID,
    MatchType.RANGE: BmMatchParamType.RANGE,
}


def parse_match_key(table, key_fields):
    def parse_param_(field, bw):
        try:
            return parse_param(field, bw)
        except UIn_BadParamError as err:
            raise UIn_MatchKeyError('error while parsing {} - {}'.format(field, err))

    params = []
    match_types = [t for (_, t, _) in table.key]
    bitwidths = [bw for (_, _, bw) in table.key]
    for idx, field in enumerate(key_fields):
        param_type = _match_types_mapping[match_types[idx]]
        bw = bitwidths[idx]
        if param_type == BmMatchParamType.EXACT:
            key = bytes_to_string(parse_param_(field, bw))
            param = BmMatchParam(type=param_type, exact=BmMatchParamExact(key))
        elif param_type == BmMatchParamType.LPM:
            try:
                prefix, length = field.split('/')
            except ValueError:
                raise UIn_MatchKeyError("invalid LPM value {}, use '/' to separate prefix and length".format(field))
            key = bytes_to_string(parse_param_(prefix, bw))
            param = BmMatchParam(type=param_type, lpm=BmMatchParamLPM(key, int(length)))
        elif param_type == BmMatchParamType.TERNARY:
            try:
                key, mask = field.split('&&&')
            except ValueError:
                raise UIn_MatchKeyError("invalid ternary value {}, use '&&&' to separate key and mask".format(field))
            key = bytes_to_string(parse_param_(key, bw))
            mask = bytes_to_string(parse_param_(mask, bw))
            if len(mask) != len(key):
                raise UIn_MatchKeyError('key and mask have different lengths in expression {}'.format(field))
            param = BmMatchParam(type=param_type, ternary=BmMatchParamTernary(key, mask))
        elif param_type == BmMatchParamType.VALID:
            key = bool(int(field))
            param = BmMatchParam(type=param_type, valid=BmMatchParamValid(key))
        elif param_type == BmMatchParamType.RANGE:
            try:
                start, end = field.split('->')
            except ValueError:
                raise UIn_MatchKeyError("invalid range value {}, use '->' to separate range start "
                                        'and range end'.format(field))
            start = bytes_to_string(parse_param_(start, bw))
            end = bytes_to_string(parse_param_(end, bw))
            if len(start) != len(end):
                raise UIn_MatchKeyError('start and end have different lengths in expression {}'.format(field))
            if start > end:
                raise UIn_MatchKeyError('start is less than end in expression {}'.format(field))
            param = BmMatchParam(type=param_type, range=BmMatchParamRange(start, end))
        else:
            assert 0
        params.append(param)
    return params


def printable_byte_str(s):
    return ':'.join('{:02x}'.format(ord(c)) for c in s)


def BmMatchParam_to_str(self):
    return BmMatchParamType._VALUES_TO_NAMES[self.type] + '-' + \
           (self.exact.to_str() if self.exact else '') + \
           (self.lpm.to_str() if self.lpm else '') + \
           (self.ternary.to_str() if self.ternary else '') + \
           (self.valid.to_str() if self.valid else '') + \
           (self.range.to_str() if self.range else '')


def BmMatchParamExact_to_str(self):
    return printable_byte_str(self.key)


def BmMatchParamLPM_to_str(self):
    return printable_byte_str(self.key) + '/' + str(self.prefix_length)


def BmMatchParamTernary_to_str(self):
    return printable_byte_str(self.key) + ' &&& ' + printable_byte_str(self.mask)


def BmMatchParamValid_to_str(self):
    return ''


def BmMatchParamRange_to_str(self):
    return printable_byte_str(self.start) + ' -> ' + printable_byte_str(self.end_)


BmMatchParam.to_str = BmMatchParam_to_str
BmMatchParamExact.to_str = BmMatchParamExact_to_str
BmMatchParamLPM.to_str = BmMatchParamLPM_to_str
BmMatchParamTernary.to_str = BmMatchParamTernary_to_str
BmMatchParamValid.to_str = BmMatchParamValid_to_str
BmMatchParamRange.to_str = BmMatchParamRange_to_str


def parse_pvs_value(input_str, bitwidth):
    try:
        input_ = int(input_str, 0)
    except:
        raise UIn_BadParamError('invalid input, could not cast to integer, try in hex with 0x prefix')
    max_v = (1 << bitwidth) - 1
    # bmv2 does not perform this check when receiving the value (and does not truncate values which are too large),
    # so we perform this check client-side.
    if input_ > max_v:
        raise UIn_BadParamError('input is too large, it should fit within {} bits'.format(bitwidth))
    try:
        v = int_to_bytes(input_, (bitwidth + 7) / 8)
    except UIn_BadParamError:
        # should not happen because of check above
        raise
    return bytes_to_string(v)


# services is [(service_name, client_class), ...]
def thrift_connect(thrift_ip, thrift_port, services):
    return utils.thrift_connect(thrift_ip, thrift_port, services)


def handle_bad_input(f):
    @wraps(f)
    def handle(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except UIn_MatchKeyError as err:
            print('invalid match key:', err)
            print(traceback.format_exc())
        except UIn_RuntimeDataError as err:
            print('invalid runtime data:', err)
            print(traceback.format_exc())
        except UIn_Error as err:
            print('error:', err, f)
            print(traceback.format_exc())
        except InvalidTableOperation as err:
            error = TableOperationErrorCode._VALUES_TO_NAMES[err.code]
            print('invalid table operation ({})'.format(error))
            print(traceback.format_exc())
        except InvalidCounterOperation as err:
            error = CounterOperationErrorCode._VALUES_TO_NAMES[err.code]
            print('invalid counter operation ({})'.format(error))
            print(traceback.format_exc())
        except InvalidMeterOperation as err:
            error = MeterOperationErrorCode._VALUES_TO_NAMES[err.code]
            print('invalid meter operation ({})'.format(error))
            print(traceback.format_exc())
        except InvalidRegisterOperation as err:
            error = RegisterOperationErrorCode._VALUES_TO_NAMES[err.code]
            print('invalid register operation ({})'.format(error))
            print(traceback.format_exc())
        except InvalidLearnOperation as err:
            error = LearnOperationErrorCode._VALUES_TO_NAMES[err.code]
            print('invalid learn operation ({})'.format(error))
            print(traceback.format_exc())
        except InvalidSwapOperation as err:
            error = SwapOperationErrorCode._VALUES_TO_NAMES[err.code]
            print('invalid swap operation ({})'.format(error))
            print(traceback.format_exc())
        except InvalidDevMgrOperation as err:
            error = DevMgrErrorCode._VALUES_TO_NAMES[err.code]
            print('invalid device manager operation ({})'.format(error))
            print(traceback.format_exc())
        except InvalidCrcOperation as err:
            error = CrcErrorCode._VALUES_TO_NAMES[err.code]
            print('invalid crc operation ({})'.format(error))
            print(traceback.format_exc())
        except InvalidParseVSetOperation as err:
            error = ParseVSetOperationErrorCode._VALUES_TO_NAMES[err.code]
            print('invalid parser value set operation ({})'.format(error))
            print(traceback.format_exc())

    return handle


def handle_bad_input_mc(f):
    @wraps(f)
    def handle(*args, **kwargs):
        pre_type = args[0].pre_type
        if pre_type == PreType.None:
            return handle_bad_input(f)(*args, **kwargs)
        EType = {PreType.SimplePre: SimplePre.InvalidMcOperation,
                 PreType.SimplePreLAG: SimplePreLAG.InvalidMcOperation}[pre_type]
        Codes = {PreType.SimplePre: SimplePre.McOperationErrorCode,
                 PreType.SimplePreLAG: SimplePreLAG.McOperationErrorCode}[pre_type]
        try:
            return handle_bad_input(f)(*args, **kwargs)
        except EType as err:
            error = Codes._VALUES_TO_NAMES[err.code]
            print('invalid PRE operation ({})'.format(error))

    return handle


# thrift does not support unsigned integers
def hex_to_i16(h):
    x = int(h, 0)
    if x > 0xFFFF:
        raise UIn_Error('integer cannot fit within 16 bits')
    if x > 0x7FFF:
        x -= 0x10000
    return x


def i16_to_hex(h):
    x = int(h)
    if x & 0x8000:
        x += 0x10000
    return x


def hex_to_i32(h):
    x = int(h, 0)
    if x > 0xFFFFFFFF:
        raise UIn_Error('integer cannot fit within 32 bits')
    if x > 0x7FFFFFFF:
        x -= 0x100000000
    return x


def i32_to_hex(h):
    x = int(h)
    if x & 0x80000000:
        x += 0x100000000
    return x


def parse_bool(s):
    if s == 'true' or s == 'True':
        return True
    if s == 'false' or s == 'False':
        return False
    try:
        s = int(s, 0)
        return bool(s)
    except:
        pass
    raise UIn_Error('invalid bool parameter')


def hexstr(v):
    return ''.join('{:02x}'.format(ord(c)) for c in v)


def get_logger(name, log_file, log_level='INFO'):
    log = logging.getLogger(name + '_runtimeCLI')

    if len(log.handlers) == 0:
        log.setLevel(log_level)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(formatter)

        log.addHandler(file_handler)

    return log


class RuntimeAPI(object):

    @staticmethod
    def get_thrift_services(pre_type):
        services = [('standard', Standard.Client)]

        if pre_type == PreType.SimplePre:
            services += [('simple_pre', SimplePre.Client)]
        elif pre_type == PreType.SimplePreLAG:
            services += [('simple_pre_lag', SimplePreLAG.Client)]
        else:
            services += [(None, None)]

        return services

    @staticmethod
    def get_tables():
        return TABLES

    @staticmethod
    def get_action_profs():
        return ACTION_PROFS

    @staticmethod
    def get_actions():
        return ACTIONS

    @staticmethod
    def get_meter_arrays():
        return METER_ARRAYS

    @staticmethod
    def get_counter_arrays():
        return COUNTER_ARRAYS

    @staticmethod
    def get_register_arrays():
        return REGISTER_ARRAYS

    def __init__(self, thrift_ip, thrift_port, switch, switch_log_file, pre_type=None, json_path=None):

        # self.log_file = open(switch_log_file, 'a')
        self.logger = get_logger(switch, switch_log_file)

        if not pre_type:
            # pre_type = PreType.SimplePre
            pre_type = PreType.SimplePreLAG

        self.pre_type = pre_type

        standard_client, mc_client = thrift_connect(thrift_ip, thrift_port, RuntimeAPI.get_thrift_services(pre_type))

        self.client = standard_client
        self.mc_client = mc_client

        load_json_config(standard_client, json_path)

    def write_to_log_file(self, message, show=False):
        # self.log_file.write(message + '\n')
        # self.log_file.flush()
        if show:
            print(message)
        self.logger.info(message)

    def do_shell(self, line):
        "run a shell command"

        output = os.popen(line).read()
        self.write_to_log_file(output)
        # return output

    def get_res(self, type_name, name, res_type):
        key = res_type, name
        if key not in SUFFIX_LOOKUP_MAP:
            raise UIn_ResourceError(type_name, name)
        return SUFFIX_LOOKUP_MAP[key]

    @handle_bad_input
    def do_show_tables(self, show=True):
        "list tables defined in the P4 program: show_tables"
        self.write_to_log_file('show_tables')

        tables = []
        for table_name in sorted(TABLES):
            table_str = TABLES[table_name].table_str()
            tables.append(table_str)

            self.write_to_log_file(table_str, show)
        return tables

    @handle_bad_input
    def do_show_actions(self, show=True):
        "list actions defined in the P4 program: show_actions"
        self.write_to_log_file('show_actions')

        actions = []
        for action_name in sorted(ACTIONS):
            action_str = ACTIONS[action_name].action_str()
            actions.append(action_str)

            self.write_to_log_file(action_str, show)
        return actions

    @handle_bad_input
    def do_table_show_actions(self, table_name, show=True):
        "list one table's actions as per the P4 program: table_show_actions <table_name>"
        self.write_to_log_file('table_show_actions {}'.format(table_name))

        table = self.get_res('table', table_name, ResType.table)

        actions = []
        for action_name in sorted(table.actions):
            action_str = ACTIONS[action_name].action_str()
            actions.append(action_str)

            self.write_to_log_file(action_str, show)
        return actions

    @handle_bad_input
    def do_table_info(self, table_name, show=True):
        "show info about a table: table_info <table_name>"
        self.write_to_log_file('table_info {}'.format(table_name))

        table = self.get_res('table', table_name, ResType.table)

        table_str = table.table_str()
        self.write_to_log_file(table_str + '\n' + '*' * 80, show)

        actions = []
        for action_name in sorted(table.actions):
            action_str = ACTIONS[action_name].action_str()
            actions.append(action_str)

            self.write_to_log_file(action_str, show)

        return table_str, actions

    # for debugging
    def print_set_default(self, table_name, action_name, runtime_data):
        self.write_to_log_file('setting default action of {}'.format(table_name))
        self.write_to_log_file('{0:20} {1}'.format('action:', action_name))
        self.write_to_log_file('{0:20} {1}'.format('runtime data:',
                                                   '\t'.join(printable_byte_str(d) for d in runtime_data)))

    @handle_bad_input
    def do_table_set_default(self, table_name, action_name, action_params):
        "set default action for a match table: table_set_default <table name> <action name> <action parameters>"
        self.write_to_log_file('table_set_default {} {} {}'.format(table_name, action_name, action_params))

        table = self.get_res('table', table_name, ResType.table)
        action = table.get_action(action_name)
        if action is None:
            raise UIn_Error('table {} has no action {}'.format(table_name, action_name))

        runtime_data = self.parse_runtime_data(action, action_params)

        self.print_set_default(table_name, action_name, runtime_data)

        self.client.bm_mt_set_default_action(0, table.name, action.name, runtime_data)

    @handle_bad_input
    def do_table_reset_default(self, table_name):
        "reset default entry for a match table: table_reset_default <table name>"
        self.write_to_log_file('table_reset_default {}'.format(table_name))

        table = self.get_res('table', table_name, ResType.table)

        self.client.bm_mt_reset_default_entry(0, table.name)

    def parse_runtime_data(self, action, action_params):
        if len(action_params) != action.num_params():
            raise UIn_Error('action {} needs {} parameters'.format(action.name, action.num_params()))

        return parse_runtime_data(action, action_params)

    # for debugging
    def print_table_add(self, match_key, action_name, runtime_data):
        self.write_to_log_file('{0:20} {1}'.format('match key:', '\t'.join(d.to_str() for d in match_key)))
        self.write_to_log_file('{0:20} {1}'.format('action:', action_name))
        self.write_to_log_file('{0:20} {1}'.format('runtime data:',
                                                   '\t'.join(printable_byte_str(d) for d in runtime_data)))

    @handle_bad_input
    def do_table_num_entries(self, table_name, show=True):
        "return the number of entries in a match table (direct or indirect): table_num_entries <table name>"
        self.write_to_log_file('table_num_entries {}'.format(table_name))

        table = self.get_res('table', table_name, ResType.table)

        num_table_entries = self.client.bm_mt_get_num_entries(0, table.name)
        self.write_to_log_file(str(num_table_entries), show)
        return num_table_entries

    @handle_bad_input
    def do_table_clear(self, table_name):
        "clear all entries in a match table (direct or indirect), but not the default entry: table_clear <table name>"
        self.write_to_log_file('table_clear {}'.format(table_name))

        table = self.get_res('table', table_name, ResType.table)

        self.client.bm_mt_clear_entries(0, table.name, False)

    @handle_bad_input
    def do_table_add(self, table_name, action_name, match_keys, action_params=[], priority=None, show=True):
        "add entry to a match table: table_add <table name> <action name> <match fields> => <action parameters> [priority]"
        self.write_to_log_file('table_add {} {} {} => {} [{}]'.format(table_name, action_name,
                                                                      ' '.join([str(mk) for mk in match_keys]),
                                                                      ' '.join([str(ap) for ap in action_params]),
                                                                      priority))

        table = self.get_res('table', table_name, ResType.table)
        action = table.get_action(action_name)
        if action is None:
            raise UIn_Error('table {} has no action {}'.format(table_name, action_name))
        if table.match_type in {MatchType.TERNARY, MatchType.RANGE}:
            try:
                priority = int(priority)
            except:
                raise UIn_Error('table is ternary, but could not extract a valid priority from args')
        else:
            priority = 0

        if len(match_keys) != table.num_key_fields():
            raise UIn_Error('table {} needs {} key fields'.format(table_name, table.num_key_fields()))

        match_keys = parse_match_key(table, match_keys)

        runtime_data = self.parse_runtime_data(action, action_params)

        self.write_to_log_file('adding entry {} to match table {}'.format(MatchType.to_str(table.match_type),
                                                                          table_name), show)

        # disable, maybe a verbose CLI option?
        self.print_table_add(match_keys, action_name, runtime_data)

        entry_handle = self.client.bm_mt_add_entry(0, table.name, match_keys, action.name, runtime_data,
                                                   BmAddEntryOptions(priority=priority))
        self.write_to_log_file('entry has been added to table {} with handle {}'.format(table_name, entry_handle), show)

        return entry_handle

    @handle_bad_input
    def do_table_set_timeout(self, table_name, entry_handle, timeout):
        "set a timeout in ms for a given entry; the table has to support timeouts: table_set_timeout <table_name> <entry handle> <timeout (ms)>"
        self.write_to_log_file('table_set_timeout {} {} {}'.format(table_name, entry_handle, timeout))

        table = self.get_res('table', table_name, ResType.table)
        if not table.support_timeout:
            raise UIn_Error('table {} does not support entry timeouts'.format(table_name))

        try:
            entry_handle = int(entry_handle)
        except:
            raise UIn_Error('bad format for entry handle')

        try:
            timeout = int(timeout)
        except:
            raise UIn_Error('bad format for timeout')

        self.write_to_log_file('setting a {}ms timeout for entry {}'.format(timeout, entry_handle))

        self.client.bm_mt_set_entry_ttl(0, table.name, entry_handle, timeout)

    @handle_bad_input
    def do_table_modify(self, table_name, action_name, entry_handle, action_parameters=[]):
        "add entry to a match table: table_modify <table name> <action name> <entry handle> [action parameters]"
        self.write_to_log_file('table_modify {} {} {} [{}]'.format(table_name, action_name, entry_handle,
                                                                   action_parameters))

        table = self.get_res('table', table_name, ResType.table)
        action = table.get_action(action_name)
        if action is None:
            raise UIn_Error('table {} has no action {}'.format(table_name, action_name))

        try:
            entry_handle = int(entry_handle)
        except:
            raise UIn_Error('bad format for entry handle')

        action_params = action_parameters

        runtime_data = self.parse_runtime_data(action, action_params)

        self.write_to_log_file('modifying entry {} for {} match table {}'.format(entry_handle,
                                                                                 MatchType.to_str(table.match_type),
                                                                                 table_name))

        self.client.bm_mt_modify_entry(0, table.name, entry_handle, action.name, runtime_data)

    @handle_bad_input
    def do_table_delete(self, table_name, entry_handle):
        "delete entry from a match table: table_delete <table name> <entry handle>"
        self.write_to_log_file('table_delete {} {}'.format(table_name, entry_handle))

        table = self.get_res('table', table_name, ResType.table)

        try:
            entry_handle = int(entry_handle)
        except:
            raise UIn_Error('bad format for entry handle')

        self.write_to_log_file('deleting entry {} from table {}'.format(entry_handle, table_name))

        self.client.bm_mt_delete_entry(0, table.name, entry_handle)

    def check_indirect(self, table):
        if table.type_ not in {TableType.indirect, TableType.indirect_ws}:
            raise UIn_Error('cannot run this command on non-indirect table')

    def check_indirect_ws(self, table):
        if table.type_ != TableType.indirect_ws:
            raise UIn_Error('cannot run this command on non-indirect table '
                            'or on indirect table with no selector')

    def check_act_prof_ws(self, act_prof):
        if not act_prof.with_selection:
            raise UIn_Error('cannot run this command on an action profile without selector')

    @handle_bad_input
    def do_act_prof_create_member(self, act_prof_name, action_name, action_parameters):
        "add a member to an action profile: act_prof_create_member <action profile name> <action_name> [action parameters]"
        self.write_to_log_file('act_prof_create_member {} {} [{}]'.format(act_prof_name, action_name,
                                                                          action_parameters))

        act_prof = self.get_res('action profile', act_prof_name, ResType.action_prof)
        action = act_prof.get_action(action_name)
        if action is None:
            raise UIn_Error('action profile {} has no action {}'.format(act_prof_name, action_name))

        action_params = action_parameters

        runtime_data = self.parse_runtime_data(action, action_params)

        member_handle = self.client.bm_mt_act_prof_add_member(0, act_prof.name, action.name, runtime_data)

        self.write_to_log_file('member has been created with handle ({})'.format(member_handle))

        return member_handle

    @handle_bad_input
    def do_act_prof_delete_member(self, act_prof_name, member_handle):
        "delete a member in an action profile: act_prof_delete_member <action profile name> <member handle>"
        self.write_to_log_file('act_prof_delete_member {} {}'.format(act_prof_name, member_handle))

        act_prof = self.get_res('action profile', act_prof_name, ResType.action_prof)

        try:
            member_handle = int(member_handle)
        except:
            raise UIn_Error('bad format for member handle')

        self.client.bm_mt_act_prof_delete_member(0, act_prof.name, member_handle)

    @handle_bad_input
    def do_act_prof_modify_member(self, act_prof_name, action_name, member_handle, action_parameters):
        "modify member in an action profile: act_prof_modify_member <action profile name> <action_name> <member_handle> [action parameters]"
        self.write_to_log_file('act_prof_modify_member {} {} {} [{}]'.format(act_prof_name, action_name,
                                                                             member_handle, action_parameters))

        act_prof = self.get_res('action profile', act_prof_name, ResType.action_prof)

        action = act_prof.get_action(action_name)
        if action is None:
            raise UIn_Error('action profile {} has no action {}'.format(act_prof_name, action_name))

        try:
            member_handle = int(member_handle)
        except:
            raise UIn_Error('bad format for member handle')

        action_params = action_parameters

        runtime_data = self.parse_runtime_data(action, action_params)

        self.client.bm_mt_act_prof_modify_member(0, act_prof.name, member_handle, action.name, runtime_data)

    def indirect_add_common(self, table_name, match_keys, handle, priority=None, ws=False):
        table = self.get_res('table', table_name, ResType.table)

        if ws:
            self.check_indirect_ws(table)
        else:
            self.check_indirect(table)

        if table.match_type in {MatchType.TERNARY, MatchType.RANGE}:
            try:
                priority = int(priority)
            except:
                raise UIn_Error('table is ternary, but could not extract a valid priority from args')
        else:
            priority = 0

        match_keys = parse_match_key(table, match_keys)

        try:
            handle = int(handle)
        except:
            raise UIn_Error('bad format for handle')

        self.write_to_log_file('adding entry to indirect match table {}'.format(table.name))

        return table.name, match_keys, handle, BmAddEntryOptions(priority=priority)

    @handle_bad_input
    def do_table_indirect_add(self, table_name, match_keys, member_handle, priority=None):
        "add entry to an indirect match table: table_indirect_add <table name> <match fields> => <member handle> [priority]"
        self.write_to_log_file('table_indirect_add {} {} => {} [{}]'.format(table_name, match_keys,
                                                                            member_handle, priority))

        table_name, match_keys, member_handle, options = self.indirect_add_common(table_name, match_keys,
                                                                                  member_handle, priority)

        entry_handle = self.client.bm_mt_indirect_add_entry(0, table_name, match_keys, member_handle, options)

        self.write_to_log_file('entry has been added to table {} with handle {}'.format(table_name, entry_handle))

        return entry_handle

    @handle_bad_input
    def do_table_indirect_add_with_group(self, table_name, match_keys, group_handle, priority=None):
        "add entry to an indirect match table: table_indirect_add <table name> <match fields> => <group handle> [priority]"
        self.write_to_log_file('table_indirect_add {} {} => {} [{}]'.format(table_name, match_keys,
                                                                            group_handle, priority))

        table_name, match_keys, group_handle, options = self.indirect_add_common(table_name, match_keys, group_handle,
                                                                                 priority=None, ws=True)

        entry_handle = self.client.bm_mt_indirect_ws_add_entry(0, table_name, match_keys, group_handle, options)

        self.write_to_log_file('entry has been added to table {} with handle {}'.format(table_name, entry_handle))

        return entry_handle

    @handle_bad_input
    def do_table_indirect_delete(self, table_name, entry_handle):
        "delete entry from an indirect match table: table_indirect_delete <table name> <entry handle>"
        self.write_to_log_file('table_indirect_delete {} {}'.format(table_name, entry_handle))

        table = self.get_res('table', table_name, ResType.table)
        self.check_indirect(table)

        try:
            entry_handle = int(entry_handle)
        except:
            raise UIn_Error('bad format for entry handle')

        self.write_to_log_file('deleting entry {} from table {}'.format(entry_handle, table_name))

        self.client.bm_mt_indirect_delete_entry(0, table.name, entry_handle)

    def indirect_set_default_common(self, table_name, handle, ws=False):

        table = self.get_res('table', table_name, ResType.table)
        if ws:
            self.check_indirect_ws(table)
        else:
            self.check_indirect(table)

        try:
            handle = int(handle)
        except:
            raise UIn_Error('bad format for handle')

        return table.name, handle

    @handle_bad_input
    def do_table_indirect_set_default(self, table_name, member_handle):
        "set default member for indirect match table: table_indirect_set_default <table name> <member handle>"
        self.write_to_log_file('table_indirect_set_default {} {}'.format(table_name, member_handle))

        table_name, member_handle = self.indirect_set_default_common(table_name, member_handle)

        self.client.bm_mt_indirect_set_default_member(0, table_name, member_handle)

    @handle_bad_input
    def do_table_indirect_set_default_with_group(self, table_name, group_handle):
        "set default group for indirect match table: table_indirect_set_default <table name> <group handle>"
        self.write_to_log_file('table_indirect_set_default {} {}'.format(table_name, group_handle))

        table_name, group_handle = self.indirect_set_default_common(table_name, group_handle, ws=True)

        self.client.bm_mt_indirect_ws_set_default_group(0, table_name, group_handle)

    @handle_bad_input
    def do_table_indirect_reset_default(self, table_name):
        "reset default entry for indirect match table: table_indirect_reset_default <table name>"
        self.write_to_log_file('table_indirect_reset_default {}'.format(table_name))

        table = self.get_res('table', table_name, ResType.table)

        self.client.bm_mt_indirect_reset_default_entry(0, table.name)

    @handle_bad_input
    def do_act_prof_create_group(self, action_profile_name):
        "add a group to an action pofile: act_prof_create_group <action profile name>"
        self.write_to_log_file('act_prof_create_group {}'.format(action_profile_name))

        act_prof = self.get_res('action profile', action_profile_name, ResType.action_prof)

        self.check_act_prof_ws(act_prof)

        group_handle = self.client.bm_mt_act_prof_create_group(0, act_prof.name)

        self.write_to_log_file('group has been created with handle {}'.format(group_handle))

        return group_handle

    @handle_bad_input
    def do_act_prof_delete_group(self, action_profile_name, group_handle):
        "delete a group from an action profile: act_prof_delete_group <action profile name> <group handle>"
        self.write_to_log_file('act_prof_delete_group {} {}'.format(action_profile_name, group_handle))

        act_prof = self.get_res('action profile', action_profile_name, ResType.action_prof)
        self.check_act_prof_ws(act_prof)

        try:
            group_handle = int(group_handle)
        except:
            raise UIn_Error('bad format for group handle')

        self.client.bm_mt_act_prof_delete_group(0, act_prof.name, group_handle)

    @handle_bad_input
    def do_act_prof_add_member_to_group(self, action_profile_name, member_handle, group_handle):
        "add member to group in an action profile: act_prof_add_member_to_group <action profile name> <member handle> <group handle>"
        self.write_to_log_file('act_prof_add_member_to_group {} {} {}'.format(action_profile_name,
                                                                              member_handle, group_handle))

        act_prof = self.get_res('action profile', action_profile_name, ResType.action_prof)
        self.check_act_prof_ws(act_prof)

        try:
            member_handle = int(member_handle)
        except:
            raise UIn_Error('bad format for member handle')
        try:
            group_handle = int(group_handle)
        except:
            raise UIn_Error('bad format for group handle')

        self.client.bm_mt_act_prof_add_member_to_group(0, act_prof.name, member_handle, group_handle)

    @handle_bad_input
    def do_act_prof_remove_member_from_group(self, action_profile_name, member_handle, group_handle):
        "remove member from group in action profile: act_prof_remove_member_from_group <action profile name> <member handle> <group handle>"
        self.write_to_log_file('act_prof_remove_member_from_group {} {} {}'.format(action_profile_name,
                                                                                   member_handle, group_handle))

        act_prof = self.get_res('action profile', action_profile_name, ResType.action_prof)
        self.check_act_prof_ws(act_prof)

        try:
            member_handle = int(member_handle)
        except:
            raise UIn_Error('bad format for member handle')
        try:
            group_handle = int(group_handle)
        except:
            raise UIn_Error('bad format for group handle')

        self.client.bm_mt_act_prof_remove_member_from_group(0, act_prof.name, member_handle, group_handle)

    def check_has_pre(self):
        if self.pre_type == PreType.None:
            raise UIn_Error('cannot execute this command without packet replication engine')

    def get_mgrp(self, s):
        try:
            return int(s)
        except:
            raise UIn_Error('bad format for multicast group id')

    @handle_bad_input_mc
    def do_mc_mgrp_create(self, mgrp):
        "create multicast group: mc_mgrp_create <group id>"
        self.write_to_log_file('mc_mgrp_create {}'.format(mgrp))

        mgrp = self.get_mgrp(mgrp)
        self.write_to_log_file('creating multicast group {}'.format(mgrp))
        mgrp_hdl = self.mc_client.bm_mc_mgrp_create(0, mgrp)
        assert (mgrp == mgrp_hdl)

        return mgrp_hdl

    @handle_bad_input_mc
    def do_mc_mgrp_destroy(self, mgrp):
        "destroy multicast group: mc_mgrp_destroy <group id>"
        self.write_to_log_file('mc_mgrp_destroy {}'.format(mgrp))

        mgrp = self.get_mgrp(mgrp)
        self.write_to_log_file('destroying multicast group {}'.format(mgrp))
        self.mc_client.bm_mc_mgrp_destroy(0, mgrp)

    def ports_to_port_map_str(self, ports, description='port'):
        last_port_num = 0
        port_map_str = ''
        ports_int = []
        for port_num_str in ports:
            try:
                port_num = int(port_num_str)
            except:
                raise UIn_Error('{} is not a valid {} number'.format(port_num_str, description))
            if port_num < 0:
                raise UIn_Error('{} is not a valid {} number'.format(port_num_str, description))
            ports_int.append(port_num)
        ports_int.sort()
        for port_num in ports_int:
            if port_num == (last_port_num - 1):
                raise UIn_Error('found duplicate {} number {}'.format(description, port_num))
            port_map_str += '0' * (port_num - last_port_num) + '1'
            last_port_num = port_num + 1
        return port_map_str[::-1]

    def parse_ports_and_lags(self, args):
        ports = []
        i = 1
        while (i < len(args) and args[i] != '|'):
            ports.append(args[i])
            i += 1
        port_map_str = self.ports_to_port_map_str(ports)
        if self.pre_type == PreType.SimplePreLAG:
            i += 1
            lags = [] if i == len(args) else args[i:]
            lag_map_str = self.ports_to_port_map_str(lags, description='lag')
        else:
            lag_map_str = None
        return port_map_str, lag_map_str

    @handle_bad_input_mc
    def do_mc_node_create(self, rid, ports, lags=[]):
        "create multicast node: mc_node_create <rid> <space-separated port list> [ | <space-separated lag list> ]"
        self.write_to_log_file('mc_node_create {} {} [ | {} ]'.format(rid, ' '.join([str(p) for p in ports]),
                                                                      ' '.join([str(l) for l in lags])))

        try:
            rid = int(rid)
        except:
            raise UIn_Error('bad format for rid')

        port_map_str = self.ports_to_port_map_str(ports)
        lag_map_str = self.ports_to_port_map_str(lags, description='lag')

        if self.pre_type == PreType.SimplePre:
            self.write_to_log_file('creating multicast node with rid {} and with port map {}'.format(rid, port_map_str))
            l1_hdl = self.mc_client.bm_mc_node_create(0, rid, port_map_str)
        else:
            self.write_to_log_file('creating multicast node with rid {} + port map {} + lag map {}'.format(rid,
                                                                                                           port_map_str,
                                                                                                           lag_map_str))
            l1_hdl = self.mc_client.bm_mc_node_create(0, rid, port_map_str, lag_map_str)
        self.write_to_log_file('node was created with handle {}'.format(l1_hdl))

        return l1_hdl

    def get_node_handle(self, s):
        try:
            return int(s)
        except:
            raise UIn_Error('bad format for node handle')

    @handle_bad_input_mc
    def do_mc_node_update(self, l1_hdl, ports, lags=[]):
        "update multicast node: mc_node_update <node handle> <space-separated port list> [ | <space-separated lag list> ]"
        self.write_to_log_file('mc_node_update {} {} [ | {} ]'.format(l1_hdl, ' '.join([str(p) for p in ports]),
                                                                      ' '.join([str(l) for l in lags])))

        l1_hdl = self.get_node_handle(l1_hdl)

        port_map_str = self.ports_to_port_map_str(ports)
        lag_map_str = self.ports_to_port_map_str(lags, description='lag')

        if self.pre_type == PreType.SimplePre:
            self.write_to_log_file('updating multicast node {} with port map {}'.format(l1_hdl, port_map_str))
            self.mc_client.bm_mc_node_update(0, l1_hdl, port_map_str)
        else:
            self.write_to_log_file('updating multicast node {} with port map {} and lag map {}'.format(l1_hdl,
                                                                                                       port_map_str,
                                                                                                       lag_map_str))
            self.mc_client.bm_mc_node_update(0, l1_hdl, port_map_str, lag_map_str)

    @handle_bad_input_mc
    def do_mc_node_associate(self, mgrp, l1_hdl):
        "associate node to multicast group: mc_node_associate <group handle> <node handle>"
        self.write_to_log_file('mc_node_associate {} {}'.format(mgrp, l1_hdl))

        mgrp = self.get_mgrp(mgrp)
        l1_hdl = self.get_node_handle(l1_hdl)
        self.write_to_log_file('associating multicast node {} to multicast group {}'.format(l1_hdl, mgrp))
        self.mc_client.bm_mc_node_associate(0, mgrp, l1_hdl)

    @handle_bad_input_mc
    def do_mc_node_dissociate(self, mgrp, l1_hdl):
        "dissociate node from multicast group: mc_node_associate <group handle> <node handle>"
        self.write_to_log_file('mc_node_associate {} {}'.format(mgrp, l1_hdl))

        mgrp = self.get_mgrp(mgrp)
        l1_hdl = self.get_node_handle(l1_hdl)
        self.write_to_log_file('dissociating multicast node {} from multicast group'.format(l1_hdl, mgrp))
        self.mc_client.bm_mc_node_dissociate(0, mgrp, l1_hdl)

    @handle_bad_input_mc
    def do_mc_node_destroy(self, l1_hdl):
        "destroy multicast node: mc_node_destroy <node handle>"
        self.write_to_log_file('mc_node_destroy {}'.format(l1_hdl))

        l1_hdl = self.get_node_handle(l1_hdl)
        self.write_to_log_file('destroying multicast node {}'.format(l1_hdl))
        self.mc_client.bm_mc_node_destroy(0, l1_hdl)

    @handle_bad_input_mc
    def do_mc_set_lag_membership(self, lag_index, ports):
        "set lag membership of port list: mc_set_lag_membership <lag index> <space-separated port list>"
        self.write_to_log_file('mc_set_lag_membership {} {}'.format(lag_index, ' '.join([str(p) for p in ports])))

        self.check_has_pre()
        if self.pre_type != PreType.SimplePreLAG:
            raise UIn_Error('cannot execute this command with this type of PRE, SimplePreLAG is required')

        try:
            lag_index = int(lag_index)
        except:
            raise UIn_Error('bad format for lag index')

        port_map_str = self.ports_to_port_map_str(ports, description='lag')
        self.write_to_log_file('setting lag membership: {} <- {}'.format(lag_index, port_map_str))
        self.mc_client.bm_mc_set_lag_membership(0, lag_index, port_map_str)

    @handle_bad_input_mc
    def do_mc_dump(self, show=True):
        "dump entries in multicast engine: mc_dump"
        self.write_to_log_file('mc_dump')

        self.check_has_pre()
        json_dump = self.mc_client.bm_mc_get_entries(0)
        try:
            mc_json = json.loads(json_dump)
        except:
            self.write_to_log_file('exception when retrieving multicast entries')
            return

        l1_handles = {}
        for h in mc_json['l1_handles']:
            l1_handles[h['handle']] = (h['rid'], h['l2_handle'])
        l2_handles = {}
        for h in mc_json['l2_handles']:
            l2_handles[h['handle']] = (h['ports'], h['lags'])

        self.write_to_log_file('==========', show)
        self.write_to_log_file('MC ENTRIES', show)
        for mgrp in mc_json['mgrps']:
            self.write_to_log_file('**********', show)
            mgid = mgrp['id']
            self.write_to_log_file('mgrp({})'.format(mgid), show)
            for L1h in mgrp['l1_handles']:
                rid, L2h = l1_handles[L1h]
                self.write_to_log_file('  -> (L1h={}, rid={})'.format(L1h, rid), show)
                ports, lags = l2_handles[L2h]
                self.write_to_log_file('-> (ports=[{}], lags=[{}])'.format(', '.join([str(p) for p in ports]),
                                                                           ', '.join([str(l) for l in lags])), show)

        self.write_to_log_file('==========', show)
        self.write_to_log_file('LAGS', show)
        if 'lags' in mc_json:
            for lag in mc_json['lags']:
                self.write_to_log_file('lag({})'.format(lag['id']), show)
                self.write_to_log_file('-> ports=[{}]'.format(', '.join([str(p) for p in ports])), show)
        else:
            self.write_to_log_file('None for this PRE type', show)
        self.write_to_log_file('==========', show)

    @handle_bad_input
    def do_load_new_config_file(self, filename):
        "load new json config: load_new_config_file <path to .json file>"
        self.write_to_log_file('load_new_config_file {}'.format(filename))

        if not os.path.isfile(filename):
            raise UIn_Error('not a valid filename')
        self.write_to_log_file('loading new JSON config')
        with open(filename, 'r') as f:
            json_str = f.read()
            try:
                json.loads(json_str)
            except:
                raise UIn_Error('not a valid JSON file')
            self.client.bm_load_new_config(json_str)
            load_json_str(json_str)

    @handle_bad_input
    def do_swap_configs(self, line):
        "swap the 2 existing configs, need to have called load_new_config_file before"
        self.write_to_log_file('swap_configs')

        self.write_to_log_file('swapping configs')
        self.client.bm_swap_configs()

    @handle_bad_input
    def do_meter_array_set_rates(self, meter_name, rates):
        "configure rates for an entire meter array: meter_array_set_rates <name> <rate_1>:<burst_1> <rate_2>:<burst_2>"
        self.write_to_log_file('meter_array_set_rates {} {}'.format(meter_name, rates))

        meter = self.get_res('meter', meter_name, ResType.meter_array)

        if len(rates) != meter.rate_count:
            raise UIn_Error('invalid number of rates, expected {} but got {}'.format(meter.rate_count, len(rates)))
        new_rates = []
        for rate in rates:
            try:
                r, b = rate.split(':')
                r = float(r)
                b = int(b)
                new_rates.append(BmMeterRateConfig(r, b))
            except:
                raise UIn_Error('error while parsing rates')
        self.client.bm_meter_array_set_rates(0, meter.name, new_rates)

    @handle_bad_input
    def do_meter_set_rates(self, meter_name, index, rates):
        "configure rates for a meter: meter_set_rates <name> <index> <rate_1>:<burst_1> <rate_2>:<burst_2>; rate uses units/microsecond and burst uses units where units is bytes or packets"
        self.write_to_log_file('meter_set_rates {} {} {}'.format(meter_name, index, rates))

        meter = self.get_res('meter', meter_name, ResType.meter_array)
        try:
            index = int(index)
        except:
            raise UIn_Error('bad format for index')
        if len(rates) != meter.rate_count:
            raise UIn_Error('invalid number of rates, expected {} but got {}'.format(meter.rate_count, len(rates)))
        new_rates = []
        for rate in rates:
            try:
                r, b = rate.split(':')
                r = float(r)
                b = int(b)
                new_rates.append(BmMeterRateConfig(r, b))
            except:
                raise UIn_Error('error while parsing rates')
        if meter.is_direct:
            table_name = meter.binding
            self.client.bm_mt_set_meter_rates(0, table_name, index, new_rates)
        else:
            self.client.bm_meter_set_rates(0, meter.name, index, new_rates)

    @handle_bad_input
    def do_meter_get_rates(self, meter_name, index, show=True):
        "retrieve rates for a meter: meter_get_rates <name> <index>"
        self.write_to_log_file('meter_get_rates {} {}'.format(meter_name, index))

        meter = self.get_res('meter', meter_name, ResType.meter_array)
        try:
            index = int(index)
        except:
            raise UIn_Error('bad format for index')
        # meter.rate_count
        if meter.is_direct:
            table_name = meter.binding
            rates = self.client.bm_mt_get_meter_rates(0, table_name, index)
        else:
            rates = self.client.bm_meter_get_rates(0, meter.name, index)
        if len(rates) != meter.rate_count:
            self.write_to_log_file('WARNING: expected {} rates but only received {}'.format(meter.rate_count,
                                                                                            len(rates)))

        rate_values = []
        for idx, rate in enumerate(rates):
            self.write_to_log_file('{}: info rate = {}, burst size = {}'.format(idx, rate.units_per_micros,
                                                                                rate.burst_size), show)
            rate_values.append([rate.units_per_micros, rate.burst_size])

        return rate_values

    @handle_bad_input
    def do_counter_read(self, counter_name, index, show=True):
        "read counter value: counter_read <name> <index>"
        self.write_to_log_file('counter_read {} {}'.format(counter_name, index))

        counter = self.get_res('counter', counter_name, ResType.counter_array)
        try:
            index = int(index)
        except:
            raise UIn_Error('bad format for index')
        if counter.is_direct:
            table_name = counter.binding
            self.write_to_log_file('this is the direct counter ({}) for table '.format(counter_name, table_name))
            # index = index & 0xffffffff
            value = self.client.bm_mt_read_counter(0, table_name, index)
        else:
            value = self.client.bm_counter_read(0, counter.name, index)

        self.write_to_log_file('{}[{}]={}'.format(counter_name, index, value), show)

        return value

    @handle_bad_input
    def do_counter_write(self, counter_name, index, packets, bytes):
        "write counter value: counter_write <name> <index> <packets> <bytes>"
        self.write_to_log_file('counter_write {} {} {} {}'.format(counter_name, index, packets, bytes))

        counter = self.get_res('counter', counter_name, ResType.counter_array)
        try:
            index = int(index)
        except:
            raise UIn_Error('bad format for index')
        try:
            packets = int(packets)
        except:
            raise UIn_Error('bad format for packets')
        try:
            bytes = int(bytes)
        except:
            raise UIn_Error('bad format for bytes')
        if counter.is_direct:
            table_name = counter.binding
            self.write_to_log_file('writing to direct counter ({}) for table {}'.format(counter_name, table_name))
            self.client.bm_mt_write_counter(0, table_name, index, BmCounterValue(packets=packets, bytes=bytes))
        else:
            self.client.bm_counter_write(0, counter_name, index, BmCounterValue(packets=packets, bytes=bytes))

        self.write_to_log_file('{}[{}] has been updated'.format(counter_name, index))

    @handle_bad_input
    def do_counter_reset(self, counter_name):
        "reset counter: counter_reset <name>"
        self.write_to_log_file('counter_reset {}'.format(counter_name))

        counter = self.get_res('counter', counter_name, ResType.counter_array)
        if counter.is_direct:
            table_name = counter.binding
            self.write_to_log_file('this is the direct counter ({}) for table {}'.format(counter_name, table_name))
            self.client.bm_mt_reset_counters(0, table_name)
        else:
            self.client.bm_counter_reset_all(0, counter.name)

    @handle_bad_input
    def do_register_read(self, register_name, index=None, show=True):
        "read register value: register_read <name> [index]"
        self.write_to_log_file('register_read {} [{}]'.format(register_name, index))

        register = self.get_res('register', register_name, ResType.register_array)
        if index or index == 0:
            try:
                index = int(index)
            except:
                raise UIn_Error('bad format for index')
            value = self.client.bm_register_read(0, register.name, index)
            self.write_to_log_file('{}[{}]={}'.format(register_name, index, value))

            return value
        else:
            self.write_to_log_file('register index omitted, reading entire array\n')
            entries = self.client.bm_register_read_all(0, register.name)
            self.write_to_log_file('{}={}'.format(register_name, ', '.join([str(e) for e in entries])), show)

            return entries

    @handle_bad_input
    def do_register_write(self, register_name, index, value):
        "write register value: register_write <name> <index> <value>"
        self.write_to_log_file('register_write {} {} {}}'.format(register_name, index, value))

        register = self.get_res('register', register_name, ResType.register_array)
        try:
            index = int(index)
        except:
            raise UIn_Error('bad format for index')
        try:
            value = int(value)
        except:
            raise UIn_Error('bad format for value, must be an integer')

        self.client.bm_register_write(0, register.name, index, value)

    @handle_bad_input
    def do_register_reset(self, register_name):
        "reset all the cells in the register array to 0: register_reset <name>"
        self.write_to_log_file('register_reset {}'.format(register_name))

        register = self.get_res('register', register_name, ResType.register_array)

        self.client.bm_register_reset(0, register.name)

    def dump_action_and_data(self, action_name, action_data, show=True):
        self.write_to_log_file('action entry: {} - {}'.format(action_name, ', '.join([hexstr(a) for a in action_data])),
                               show)

    def dump_action_entry(self, action_entry, show=True):
        if action_entry.action_type == BmActionEntryType.NONE:
            self.write_to_log_file('EMPTY', show)
        elif action_entry.action_type == BmActionEntryType.ACTION_DATA:
            self.dump_action_and_data(action_entry.action_name, action_entry.action_data)
        elif action_entry.action_type == BmActionEntryType.MBR_HANDLE:
            self.write_to_log_file('index: member({})'.format(action_entry.mbr_handle), show)
        elif action_entry.action_type == BmActionEntryType.GRP_HANDLE:
            self.write_to_log_file('index: group({})'.format(action_entry.grp_handle), show)

    def dump_one_member(self, member, show=True):
        self.write_to_log_file('dumping member {}'.format(member.mbr_handle), show)
        self.dump_action_and_data(member.action_name, member.action_data)

    def dump_members(self, members, show=True):
        for member in members:
            self.write_to_log_file('**********', show)
            self.dump_one_member(member)

    def dump_one_group(self, group, show=True):
        self.write_to_log_file('dumping group {}'.format(group.grp_handle), show)
        self.write_to_log_file('members: [{}]'.format(', '.join([str(h) for h in group.mbr_handles])), show)

    def dump_groups(self, groups, show=True):
        for group in groups:
            self.write_to_log_file('**********', show)
            self.dump_one_group(group)

    def dump_one_entry(self, table, entry, show=True):
        if table.key:
            out_name_w = max(20, max([len(t[0]) for t in table.key]))

        def dump_exact(p):
            return hexstr(p.exact.key)

        def dump_lpm(p):
            return '{}/{}'.format(hexstr(p.lpm.key), p.lpm.prefix_length)

        def dump_ternary(p):
            return '{} &&& {}'.format(hexstr(p.ternary.key), hexstr(p.ternary.mask))

        def dump_range(p):
            return '{} -> {}'.format(hexstr(p.range.start), hexstr(p.range.end_))

        def dump_valid(p):
            return '01' if p.valid.key else '00'

        pdumpers = {'exact': dump_exact, 'lpm': dump_lpm,
                    'ternary': dump_ternary, 'valid': dump_valid,
                    'range': dump_range}

        self.write_to_log_file('dumping entry {}'.format(hex(entry.entry_handle)), show)
        self.write_to_log_file('match key:', show)
        for p, k in zip(entry.match_key, table.key):
            assert (k[1] == p.type)
            pdumper = pdumpers[MatchType.to_str(p.type)]
            self.write_to_log_file('* {0:{w}}: {1:10}{2}'.format(k[0], MatchType.to_str(p.type).upper(),
                                                                 pdumper(p), w=out_name_w), show)
        if entry.options.priority >= 0:
            self.write_to_log_file('priority: {}'.format(entry.options.priority), show)
        self.dump_action_entry(entry.action_entry)
        if entry.life is not None:
            self.write_to_log_file('life: {}ms since hit, timeout is {}ms'.format(entry.life.time_since_hit_ms,
                                                                                  entry.life.timeout_ms), show)

    @handle_bad_input
    def do_table_dump_entry(self, table_name, entry_handle, show=True):
        "display some information about a table entry: table_dump_entry <table name> <entry handle>"
        self.write_to_log_file('table_dump_entry {} {}'.format(table_name, entry_handle))

        table = self.get_res('table', table_name, ResType.table)

        try:
            entry_handle = int(entry_handle)
        except:
            raise UIn_Error('bad format for entry handle')

        entry = self.client.bm_mt_get_entry(0, table.name, entry_handle)
        self.dump_one_entry(table, entry)

        return entry

    @handle_bad_input
    def do_act_prof_dump_member(self, action_profile_name, member_handle, show=True):
        "display some information about a member: act_prof_dump_member <action profile name> <member handle>"
        self.write_to_log_file('act_prof_dump_member {} {}'.format(action_profile_name, member_handle))

        act_prof = self.get_res('action profile', action_profile_name, ResType.action_prof)

        try:
            member_handle = int(member_handle)
        except:
            raise UIn_Error('bad format for member handle')

        member = self.client.bm_mt_act_prof_get_member(0, act_prof.name, member_handle)
        self.dump_one_member(member)

        return member

    @handle_bad_input
    def do_act_prof_dump_group(self, action_profile_name, group_handle, show=True):
        "display some information about a group: table_dump_group <action profile name> <group handle>"
        self.write_to_log_file('table_dump_group {} {}'.format(action_profile_name, group_handle))

        act_prof = self.get_res('action profile', action_profile_name, ResType.action_prof)

        try:
            group_handle = int(group_handle)
        except:
            raise UIn_Error('bad format for group handle')

        group = self.client.bm_mt_act_prof_get_group(0, act_prof.name, group_handle)
        self.dump_one_group(group)

        return group

    def _dump_act_prof(self, act_prof, show=True):
        act_prof_name = act_prof.name
        members = self.client.bm_mt_act_prof_get_members(0, act_prof.name)
        self.write_to_log_file('==========', show)
        self.write_to_log_file('MEMBERS', show)
        self.dump_members(members)
        if act_prof.with_selection:
            groups = self.client.bm_mt_act_prof_get_groups(0, act_prof.name)
            self.write_to_log_file('==========', show)
            self.write_to_log_file('GROUPS', show)
            self.dump_groups(groups)

    @handle_bad_input
    def do_act_prof_dump(self, action_profile_name, show=True):
        "display entries in an action profile: act_prof_dump <action profile name>"
        self.write_to_log_file('act_prof_dump {}'.format(action_profile_name))

        act_prof = self.get_res('action profile', action_profile_name, ResType.action_prof)
        self._dump_act_prof(act_prof)

        return act_prof

    @handle_bad_input
    def do_table_dump(self, table_name, show=True):
        "display entries in a match-table: table_dump <table name>"
        self.write_to_log_file('table_dump {}'.format(table_name))

        table = self.get_res('table', table_name, ResType.table)
        entries = self.client.bm_mt_get_entries(0, table.name)

        self.write_to_log_file('==========', show)
        self.write_to_log_file('TABLE ENTRIES', show)

        for entry in entries:
            self.write_to_log_file('**********', show)
            self.dump_one_entry(table, entry)

        if table.type_ == TableType.indirect or table.type_ == TableType.indirect_ws:
            assert (table.action_prof is not None)
            self._dump_act_prof(table.action_prof)

        # default entry
        default_entry = self.client.bm_mt_get_default_entry(0, table.name)
        self.write_to_log_file('==========', show)
        self.write_to_log_file('dumping default entry', show)
        self.dump_action_entry(default_entry)
        self.write_to_log_file('==========', show)

    @handle_bad_input
    def do_table_dump_entry_from_key(self, table_name, match_keys, priority, show=True):
        "display some information about a table entry: table_dump_entry_from_key <table name> <match fields> [priority]"
        self.write_to_log_file('table_dump_entry_from_key {} {} [{}]'.format(table_name, match_keys, priority))

        table = self.get_res('table', table_name, ResType.table)

        if table.match_type in {MatchType.TERNARY, MatchType.RANGE}:
            try:
                priority = int(priority)
            except:
                raise UIn_Error('table is ternary, but could not extract a valid priority from args')
        else:
            priority = 0

        if len(match_keys) != table.num_key_fields():
            raise UIn_Error('table {} needs {} key fields'.format(table_name, table.num_key_fields()))
        match_keys = parse_match_key(table, match_keys)

        entry = self.client.bm_mt_get_entry_from_key(0, table.name, match_keys, BmAddEntryOptions(priority=priority))
        self.dump_one_entry(table, entry)

        return entry

    @handle_bad_input
    def do_show_pvs(self, show=True):
        "list parser value sets defined in the P4 program: show_pvs"
        self.write_to_log_file('show_pvs')

        parser_value_sets = []
        for pvs_name in sorted(PARSE_VSETS):
            parse_vset_str = PARSE_VSETS[pvs_name].parse_vset_str()
            parser_value_sets.append(parse_vset_str)

            self.write_to_log_file(parse_vset_str, show)
        return parser_value_sets

    @handle_bad_input
    def do_pvs_add(self, pvs_name, value):
        '''
        add a value to a parser value set: pvs_add <pvs_name> <value>
        bmv2 will not report an error if the value already exists.
        '''
        self.write_to_log_file('pvs_add {} {}'.format(pvs_name, value))

        pvs = self.get_res('parser value set', pvs_name, ResType.parse_vset)

        value = parse_pvs_value(value, pvs.bitwidth)

        self.client.bm_parse_vset_add(0, pvs_name, value)

    @handle_bad_input
    def do_pvs_remove(self, pvs_name, value):
        '''
        remove a value from a parser value set: pvs_remove <pvs_name> <value>
        bmv2 will not report an error if the value does not exist.
        '''
        self.write_to_log_file('pvs_remove {} {}'.format(pvs_name, value))

        pvs = self.get_res('parser value set', pvs_name, ResType.parse_vset)

        value = parse_pvs_value(value, pvs.bitwidth)

        self.client.bm_parse_vset_remove(0, pvs_name, value)

    @handle_bad_input
    def do_pvs_get(self, pvs_name, show=True):
        '''
        print all values from a parser value set: pvs_get <pvs_name>
        values are displayed in no particular order, one per line.
        '''
        self.write_to_log_file('pvs_get {}'.format(pvs_name))

        pvs = self.get_res('parser value set', pvs_name, ResType.parse_vset)

        values = self.client.bm_parse_vset_get(0, pvs_name)

        vals = []
        for value in values:
            val = hexstr(value)
            vals.append(val)

            self.write_to_log_file(val, show)
        return vals

    @handle_bad_input
    def do_pvs_clear(self, pvs_name):
        '''
        remove all values from a parser value set: pvs_clear <pvs_name>
        '''
        self.write_to_log_file('pvs_clear {}'.format(pvs_name))

        pvs = self.get_res('parser value set', pvs_name, ResType.parse_vset)

        self.client.bm_parse_vset_clear(0, pvs_name)

    @handle_bad_input
    def do_port_add(self, iface_name, port_num, pcap_path=""):
        "add a port to the switch (behavior depends on device manager used): port_add <iface_name> <port_num> [pcap_path]"
        self.write_to_log_file('port_add {} {} [{}]'.format(iface_name, port_num, pcap_path))

        try:
            port_num = int(port_num)
        except:
            raise UIn_Error('bad format for port_num, must be an integer')

        self.client.bm_dev_mgr_add_port(iface_name, port_num, pcap_path)

    @handle_bad_input
    def do_port_remove(self, port_num):
        "removes a port from the switch (behavior depends on device manager used): port_remove <port_num>"
        self.write_to_log_file('port_remove {}'.format(port_num))

        try:
            port_num = int(port_num)
        except:
            raise UIn_Error('bad format for port_num, must be an integer')

        self.client.bm_dev_mgr_remove_port(port_num)

    @handle_bad_input
    def do_show_ports(self, show=True):
        "shows the ports connected to the switch: show_ports"
        self.write_to_log_file('show_ports')

        ports = self.client.bm_dev_mgr_show_ports()
        self.write_to_log_file('{:^10}{:^20}{:^10}{}'.format('port #', 'iface name', 'status', 'extra info'), show)
        self.write_to_log_file('=' * 50, show)
        for port_info in ports:
            status = 'UP' if port_info.is_up else 'DOWN'
            extra_info = '; '.join([k + '=' + v for k, v in port_info.extra.items()])
            self.write_to_log_file('{:^10}{:^20}{:^10}{}'.format(port_info.port_num, port_info.iface_name,
                                                                 status, extra_info), show)
        return ports

    @handle_bad_input
    def do_switch_info(self, show=True):
        "show some basic info about the switch: switch_info"
        self.write_to_log_file('switch_info')

        info = self.client.bm_mgmt_get_info()
        attributes = [t[2] for t in info.thrift_spec[1:]]
        out_attr_w = 5 + max(len(a) for a in attributes)
        for attr in attributes:
            self.write_to_log_file('{:{w}}: {}'.format(attr, getattr(info, attr), w=out_attr_w), show)

    @handle_bad_input
    def do_reset_state(self):
        "reset all state in the switch (table entries, registers, ...), but P4 config is preserved: reset_state"
        self.write_to_log_file('reset_state')

        self.client.bm_reset_state()

    @handle_bad_input
    def do_write_config_to_file(self, filename):
        "retrieves the JSON config currently used by the switch and dumps it to user-specified file"
        self.write_to_log_file('write_config_to_file {}'.format(filename))

        json_cfg = self.client.bm_get_config()
        with open(filename, 'w') as f:
            f.write(json_cfg)

    @handle_bad_input
    def do_serialize_state(self, filename):
        "serialize the switch state and dumps it to user-specified file"
        self.write_to_log_file('serialize_state {}'.format(filename))

        state = self.client.bm_serialize_state()
        with open(filename, 'w') as f:
            f.write(state)

    def set_crc_parameters_common(self, name, polynomial, initial_remainder, final_xor_value,
                                  reflect_data, reflect_remainder, crc_width=16):
        conversion_fn = {16: hex_to_i16, 32: hex_to_i32}[crc_width]
        config_type = {16: BmCrc16Config, 32: BmCrc32Config}[crc_width]
        thrift_fn = {16: self.client.bm_set_crc16_custom_parameters,
                     32: self.client.bm_set_crc32_custom_parameters}[crc_width]

        if name not in CUSTOM_CRC_CALCS or CUSTOM_CRC_CALCS[name] != crc_width:
            raise UIn_ResourceError('crc{}_custom'.format(crc_width), name)
        config_args = [conversion_fn(a) for a in [polynomial, initial_remainder, final_xor_value]]
        config_args += [parse_bool(a) for a in [reflect_data, reflect_remainder]]
        crc_config = config_type(*config_args)
        thrift_fn(0, name, crc_config)

    @handle_bad_input
    def do_set_crc16_parameters(self, name, polynomial, initial_remainder,
                                final_xor_value, reflect_data, reflect_remainder):
        "change the parameters for a custom crc16 hash: set_crc16_parameters <name> <polynomial> <initial remainder> <final xor value> <reflect data?> <reflect remainder?>"
        self.write_to_log_file('set_crc16_parameters {} {} {} {} {} {}'.format(name, polynomial, initial_remainder,
                                                                               final_xor_value,
                                                                               reflect_data, reflect_remainder))

        self.set_crc_parameters_common(name, polynomial, initial_remainder,
                                       final_xor_value, reflect_data, reflect_remainder, 16)

    @handle_bad_input
    def do_set_crc32_parameters(self, name, polynomial, initial_remainder,
                                final_xor_value, reflect_data, reflect_remainder):
        "change the parameters for a custom crc32 hash: set_crc32_parameters <name> <polynomial> <initial remainder> <final xor value> <reflect data?> <reflect remainder?>"
        self.write_to_log_file('set_crc32_parameters {} {} {} {} {} {}'.format(name, polynomial, initial_remainder,
                                                                               final_xor_value,
                                                                               reflect_data, reflect_remainder))

        self.set_crc_parameters_common(name, polynomial, initial_remainder,
                                       final_xor_value, reflect_data, reflect_remainder, 32)
