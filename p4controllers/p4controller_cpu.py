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

from p4controllers.p4controller import P4Controller

import grpc

from enum import Enum

from scapy.sendrecv import AsyncSniffer
import threading

from tools.log.log import log
from p4runtime.runtimeAPI import error_utils
import traceback


class SnifferMode(Enum):
    SINGLE_SNIFFER = 0
    SWITCH_LEVEL_SNIFFER = 1


class P4ControllerCPU(P4Controller):
    P4_SWITCH_CPU_PORT_PATTERN = 'cpu-{}'
    # P4_SWITCH_CPU_PORT_ID = 510
    P4_SWITCH_MIRROR_ID = 99

    def __init__(self, *args, **kwargs):
        P4Controller.__init__(self, *args, **kwargs)

        # self.sniffer_mode = SnifferMode.SINGLE_SNIFFER
        self.sniffer_mode = SnifferMode.SWITCH_LEVEL_SNIFFER

        self.switch_cpu_ports = dict()
        if self.sniffer_mode == SnifferMode.SINGLE_SNIFFER:
            self.sniffer = None
        if self.sniffer_mode == SnifferMode.SWITCH_LEVEL_SNIFFER:
            self.switch_sniffer = dict()
            self.lock = threading.Lock()

    def _run_cpu_port_handler(self, sniff_filter=None):
        self._add_cpu_mirrors()
        self._run_sniffer(sniff_filter=sniff_filter)

    def _stop_cpu_port_handler(self):
        self._stop_sniffer()

    @abstractmethod
    def _handle_cpu_packet(self, cpu_packet):
        pass

    def _receive_cpu_packet(self, cpu_packet):
        try:
            if self.sniffer_mode == SnifferMode.SWITCH_LEVEL_SNIFFER:
                self.lock.acquire()
            self._handle_cpu_packet(cpu_packet)
            if self.sniffer_mode == SnifferMode.SWITCH_LEVEL_SNIFFER:
                self.lock.release()
        except grpc.RpcError as error:
            error_utils.print_grpc_error(error)
        except Exception:
            log.error('terminate p4controller: {}'.format(self.__class__.__name__))
            log.error(traceback.format_exc())

    def _run_sniffer(self, sniff_filter=None):
        if self.sniffer_mode == SnifferMode.SINGLE_SNIFFER:
            for p4switch in self.p4switch_configurations:
                cpu_port = P4ControllerCPU.P4_SWITCH_CPU_PORT_PATTERN.format(p4switch)
                self.switch_cpu_ports[p4switch] = cpu_port
            self.sniffer = AsyncSniffer(iface=self.switch_cpu_ports.values(),
                                        filter=sniff_filter,
                                        prn=self._receive_cpu_packet)
            self.sniffer.start()

        if self.sniffer_mode == SnifferMode.SWITCH_LEVEL_SNIFFER:
            for p4switch in self.p4switch_configurations:
                cpu_port = P4ControllerCPU.P4_SWITCH_CPU_PORT_PATTERN.format(p4switch)
                self.switch_cpu_ports[p4switch] = cpu_port
                sniffer = AsyncSniffer(iface=cpu_port,
                                       filter=sniff_filter,
                                       prn=self._receive_cpu_packet)
                self.switch_sniffer[p4switch] = sniffer
                sniffer.start()

    def _stop_sniffer(self):
        if self.sniffer_mode == SnifferMode.SINGLE_SNIFFER:
            self.sniffer.stop()
            self.sniffer.join()
        if self.sniffer_mode == SnifferMode.SWITCH_LEVEL_SNIFFER:
            for sniffer in self.switch_sniffer.values():
                sniffer.stop()
                sniffer.join()

    def _add_cpu_mirrors(self):
        for p4switch, sw_config in self.p4switch_configurations.items():
            self.p4switch_connections_thrift[p4switch].mirroring_add(self.P4_SWITCH_MIRROR_ID,
                                                                     sw_config['ports']['cpu_port'])
