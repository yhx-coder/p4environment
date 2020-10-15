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

from abc import abstractmethod
import threading

from p4controllers.p4controller import P4Controller

from tools.log.log import log
from p4runtime.runtimeAPI import error_utils
import traceback

import grpc
import nnpy
import struct


class P4ControllerDigest(P4Controller):
    # https://docs.python.org/2.7/library/struct.html?highlight=unpack#struct.unpack
    DIGEST_HEADER_STRUCTURE = '<iQiiQi'
    # https://github.com/p4lang/behavioral-model/blob/master/include/bm/bm_sim/learning.h#L56
    DIGEST_HEADER_LENGTH = 32  # bytes

    def __init__(self, *args, **kwargs):
        P4Controller.__init__(self, *args, **kwargs)

        self.notifications_sockets = dict()
        self.notifications_handler = dict()

        self.digest_listen_flag = True

    @abstractmethod
    def _unpack_message_digest(self, p4switch, message, num_samples):
        pass

    @abstractmethod
    def _process_message_digest(self, message_data):
        pass

    def _listen_message_digest(self, *args, **kwargs):
        p4switch = kwargs['sw']

        while self.digest_listen_flag:
            try:
                message = self.notifications_sockets[p4switch].recv()
                self._handle_message_digest(p4switch, message)
            except:
                pass

    def _handle_message_digest(self, p4switch, message):
        try:
            # https://github.com/p4lang/behavioral-model/blob/master/include/bm/bm_sim/learning.h#L56
            # http://lists.p4.org/pipermail/p4-dev_lists.p4.org/2017-September/003110.html
            topic, device_id, cxt_id, list_id, buffer_id, num = struct.unpack(self.DIGEST_HEADER_STRUCTURE,
                                                                              message[:self.DIGEST_HEADER_LENGTH])
            log.info('received notification topic:'
                     '{}, device_id: {}, ctx_id: {}, list_id: {}, buffer_if: {}, num: {}'.format(topic,
                                                                                                 device_id,
                                                                                                 cxt_id,
                                                                                                 list_id,
                                                                                                 buffer_id,
                                                                                                 num))

            message = message[self.DIGEST_HEADER_LENGTH:]
            messages = self._unpack_message_digest(p4switch, message, num)
            self._process_message_digest(messages)

            self.p4switch_connections_thrift[p4switch].client.bm_learning_ack_buffer(cxt_id, list_id, buffer_id)

        except grpc.RpcError as error:
            error_utils.print_grpc_error(error)
        except Exception:
            log.error('terminate p4controller: {}'.format(self.__class__.__name__))
            log.error(traceback.format_exc())

    def _run_digest_handler(self):
        for p4switch in self.p4switch_configurations:
            notifications = self.p4switch_configurations[p4switch]['notifications_ipc']

            if not notifications:
                raise P4DigestHandlingException('digest handling for p4 switches is not possible '
                                                'because notifications support is disabled')

            notifications_socket = nnpy.Socket(nnpy.AF_SP, nnpy.SUB)
            notifications_socket.connect(str(notifications))
            # sw_connection = self.p4switch_connections_thrift[p4switch]
            # notifications_socket.connect(sw_connection.client.bm_mgmt_get_info().notifications_socket)
            notifications_socket.setsockopt(nnpy.SUB, nnpy.SUB_SUBSCRIBE, '')
            self.notifications_sockets[p4switch] = notifications_socket

            notifications_handler = threading.Thread(target=self._listen_message_digest,
                                                     kwargs={'sw': p4switch})
            notifications_handler.start()
            self.notifications_handler[p4switch] = notifications_handler

    def _stop_digest_handler(self):
        self.digest_listen_flag = False
        for notifications_socket in self.notifications_sockets.values():
            notifications_socket.close()
        for notifications_handler in self.notifications_handler.values():
            notifications_handler.join()


class P4DigestHandlingException(Exception):

    def __init__(self, message):
        super(P4DigestHandlingException, self).__init__(self.__class__.__name__ + ': ' + message)
