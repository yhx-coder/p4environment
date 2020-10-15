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
######################################################################################
# adapted from P4 language tutorials                                                 #
# see https://github.com/p4lang/tutorials/blob/master/utils/p4runtime_lib/convert.py #
######################################################################################

import re
import socket
import math
from enum import Enum

MAC_PATTERN = re.compile(r'^([\da-fA-F]{2}:){5}([\da-fA-F]{2})$')
IP_PATTERN = re.compile(r'^(\d{1,3}\.){3}(\d{1,3})$')


def is_valid_mac_address(mac_address_string):
    return MAC_PATTERN.match(mac_address_string) is not None


def encode_mac_address(mac_address_string):
    return mac_address_string.replace(':', '').decode('hex')


def decode_mac_address(encoded_mac_address):
    return ':'.join(x.encode('hex') for x in encoded_mac_address)


def is_valid_ip_address(ip_address_string):
    return IP_PATTERN.match(ip_address_string) is not None


def encode_ip_address(ip_address_string):
    return socket.inet_aton(ip_address_string)


def decode_ip_address(encoded_ip_address):
    return socket.inet_ntoa(encoded_ip_address)


def bit_width_to_bytes(bit_width):
    return int(math.ceil(bit_width / 8.0))


def encode_number(number, bit_width):
    byte_len = bit_width_to_bytes(bit_width)
    if number >= 2 ** bit_width:
        raise Exception('number {} does not fit in {} bits'.format(number, bit_width))
    # number_str = str(number)
    number_str = '%x' % number
    return ('0' * (byte_len * 2 - len(number_str)) + number_str).decode('hex')


def decode_number(encoded_number):
    return int(encoded_number.encode('hex'), 16)


def encode(x, bit_width):
    byte_len = bit_width_to_bytes(bit_width)

    if (type(x) == list or type(x) == tuple) and len(x) == 1:
        x = x[0]
    encoded_bytes = None
    if type(x) == str:
        if is_valid_mac_address(x):
            encoded_bytes = encode_mac_address(x)
        elif is_valid_ip_address(x):
            encoded_bytes = encode_ip_address(x)
        else:
            encoded_bytes = x
    elif type(x) == int:
        encoded_bytes = encode_number(x, bit_width)
    else:
        raise Exception('encoding objects of {} is not supported'.format(type(x)))

    assert (len(encoded_bytes) == byte_len)

    return encoded_bytes


class Types(Enum):
    MAC = 0
    IP = 1
    NUMBER = 2


def decode(x):
    if len(x) == 6:
        return decode_mac_address(x), Types.MAC

    if len(x) == 4:
        return decode_ip_address(x), Types.IP

    return decode_number(x), Types.NUMBER
