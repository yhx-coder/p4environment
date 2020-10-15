# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
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
##########################################################################################
# adapted from P4 language tutorials                                                     #
# see https://github.com/p4lang/tutorials/blob/master/utils/p4runtime_lib/error_utils.py #
##########################################################################################

import sys

from google.rpc import status_pb2, code_pb2
import grpc
from p4.v1 import p4runtime_pb2

from tools.log.log import log


class P4RuntimeErrorFormatException(Exception):
    def __init__(self, message):
        super(P4RuntimeErrorFormatException, self).__init__(message)


def parse_grpc_error_binary_details(grpc_error):
    if grpc_error.code() != grpc.StatusCode.UNKNOWN:
        return None

    error = None

    # the gRPC python package does not have a convenient way to access the
    # binary details for the error: they are treated as trailing metadata.
    for meta in grpc_error.trailing_metadata():
        if meta[0] == 'grpc-status-details-bin':
            error = status_pb2.Status()
            error.ParseFromString(meta[1])
            break

    if error is None:  # no binary details field
        return None

    if len(error.details) == 0:  # binary details field has empty Any details repeated field
        return None

    indexed_p4_errors = []
    for idx, one_error_any in enumerate(error.details):
        p4_error = p4runtime_pb2.Error()
        if not one_error_any.Unpack(p4_error):
            raise P4RuntimeErrorFormatException('cannot convert Any message to p4.Error')
        if p4_error.canonical_code == code_pb2.OK:
            continue
        indexed_p4_errors += [(idx, p4_error)]

    return indexed_p4_errors


def print_grpc_error(grpc_error):
    # log.error('### gRPC error ###\n {}'.format(grpc_error.details()))
    log.error('### gRPC error ###')
    status_code = grpc_error.code()
    log.error('({})'.format(status_code.name))
    traceback = sys.exc_info()[2]
    log.error('[{}:{}]'.format(traceback.tb_frame.f_code.co_filename, traceback.tb_lineno))

    if status_code != grpc.StatusCode.UNKNOWN:
        return

    p4_errors = parse_grpc_error_binary_details(grpc_error)
    if p4_errors is None:
        return

    log.error('### errors in batch ###')
    for idx, p4_error in p4_errors:
        code_name = code_pb2._CODE.values_by_number[p4_error.canonical_code].name
        log.error('\t* at index {}: {}, {}\n'.format(idx, code_name, p4_error.message))
