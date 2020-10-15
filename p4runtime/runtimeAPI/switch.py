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
# see https://github.com/p4lang/tutorials/blob/master/utils/p4runtime_lib/switch.py #
# see https://github.com/p4lang/tutorials/blob/master/utils/p4runtime_lib/bmv2.py   #
#####################################################################################

from Queue import Queue
from abc import abstractmethod
from datetime import datetime

import grpc
from p4.v1 import p4runtime_pb2
from p4.v1 import p4runtime_pb2_grpc
from p4.tmp import p4config_pb2


MSG_LOG_MAX_LEN = 2048


class SwitchConnection(object):

    def __init__(self, switch_addr, device_id, runtime_gRPC_log=None, name=None):
        self.name = name
        self.switch_addr = switch_addr
        self.device_id = int(device_id)
        self.p4info = None
        self.channel = grpc.insecure_channel(self.switch_addr)
        if runtime_gRPC_log is not None:
            interceptor = GrpcRequestLogger(runtime_gRPC_log)
            self.channel = grpc.intercept_channel(self.channel, interceptor)
        self.client_stub = p4runtime_pb2_grpc.P4RuntimeStub(self.channel)
        self.requests_stream = IterableQueue()
        self.stream_message_response = self.client_stub.StreamChannel(iter(self.requests_stream))
        self.proto_dump_file = runtime_gRPC_log

    @abstractmethod
    def build_device_config(self):
        return p4config_pb2.P4DeviceConfig()

    def shutdown(self):
        self.requests_stream.close()
        self.stream_message_response.cancel()

    def master_arbitration_update(self):
        request = p4runtime_pb2.StreamMessageRequest()
        request.arbitration.device_id = self.device_id
        request.arbitration.election_id.high = 0
        request.arbitration.election_id.low = 1

        self.requests_stream.put(request)

        # for response in self.stream_message_response:
        #     yield response

        return self.stream_message_response

    def set_forwarding_pipeline_config(self, p4info, bmv2_json_file):
        device_config = self.build_device_config(bmv2_json_file)
        request = p4runtime_pb2.SetForwardingPipelineConfigRequest()
        request.election_id.low = 1
        request.device_id = self.device_id
        config = request.config

        config.p4info.CopyFrom(p4info)
        config.p4_device_config = device_config.SerializeToString()

        request.action = p4runtime_pb2.SetForwardingPipelineConfigRequest.VERIFY_AND_COMMIT
        self.client_stub.SetForwardingPipelineConfig(request)

    def write_table_entry(self, table_entry):
        request = p4runtime_pb2.WriteRequest()
        request.device_id = self.device_id
        request.election_id.low = 1
        update = request.updates.add()

        if table_entry.is_default_action:
            update.type = p4runtime_pb2.Update.MODIFY
        else:
            update.type = p4runtime_pb2.Update.INSERT

        update.entity.table_entry.CopyFrom(table_entry)

        self.client_stub.Write(request)

    def remove_table_entry(self, table_entry):
        request = p4runtime_pb2.WriteRequest()
        request.device_id = self.device_id
        request.election_id.low = 1

        update = request.updates.add()
        update.type = p4runtime_pb2.Update.DELETE
        update.entity.table_entry.CopyFrom(table_entry)

        self.client_stub.Write(request)

    def write_multicast_group_entry(self, multicast_entry):
        request = p4runtime_pb2.WriteRequest()
        request.device_id = self.device_id
        request.election_id.low = 1

        update = request.updates.add()
        update.type = p4runtime_pb2.Update.INSERT
        update.entity.packet_replication_engine_entry.CopyFrom(multicast_entry)

        self.client_stub.Write(request)

    def delete_multicast_group_entry(self, multicast_entry):
        request = p4runtime_pb2.WriteRequest()
        request.device_id = self.device_id
        request.election_id.low = 1

        update = request.updates.add()
        update.type = p4runtime_pb2.Update.DELETE
        update.entity.packet_replication_engine_entry.CopyFrom(multicast_entry)

        self.client_stub.Write(request)

    def get_table_entries(self, table_id=None):
        request = p4runtime_pb2.ReadRequest()
        request.device_id = self.device_id
        entity = request.entities.add()
        table_entry = entity.table_entry

        if table_id is not None:
            table_entry.table_id = table_id
        else:
            table_entry.table_id = 0

        for response in self.client_stub.Read(request):
            yield response

    def get_counters(self, counter_id=None, index=None):
        request = p4runtime_pb2.ReadRequest()
        request.device_id = self.device_id
        entity = request.entities.add()
        counter_entry = entity.counter_entry

        if counter_id is not None:
            counter_entry.counter_id = counter_id
        else:
            counter_entry.counter_id = 0

        if index is not None:
            counter_entry.index.index = index

        for response in self.client_stub.Read(request):
            yield response


class GrpcRequestLogger(grpc.UnaryUnaryClientInterceptor,
                        grpc.UnaryStreamClientInterceptor):

    def __init__(self, log_file):
        self.log_file = log_file

        with open(self.log_file, 'a') as grpc_interception_file:
            grpc_interception_file.write('\n\n')

    def log_message(self, method_name, body):
        with open(self.log_file, 'a') as grpc_interception_file:
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            message = str(body)
            grpc_interception_file.write('\n[{}] {}\n---\n'.format(ts, method_name))
            if len(message) < MSG_LOG_MAX_LEN:
                grpc_interception_file.write(str(body))
            else:
                grpc_interception_file.write('log message too long ({} bytes > {} bytes)\n'.format(len(message),
                                                                                                   MSG_LOG_MAX_LEN))
            grpc_interception_file.write('---\n')
            grpc_interception_file.flush()

    def intercept_unary_unary(self, continuation, client_call_details, request):
        self.log_message(client_call_details.method, request)
        return continuation(client_call_details, request)

    def intercept_unary_stream(self, continuation, client_call_details, request):
        self.log_message(client_call_details.method, request)
        return continuation(client_call_details, request)


class IterableQueue(Queue):
    _sentinel = object()

    def __iter__(self):
        return iter(self.get, self._sentinel)

    def close(self):
        self.put(self._sentinel)


class Bmv2SwitchConnection(SwitchConnection):
    def build_device_config(self, bmv2_json_file):
        device_config = p4config_pb2.P4DeviceConfig()
        device_config.reassign = True
        with open(bmv2_json_file) as json_file:
            device_config.device_data = json_file.read()
        return device_config
