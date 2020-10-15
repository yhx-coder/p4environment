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

from p4monitors.p4monitor import P4Monitor


class FlowMonitor(P4Monitor):

    def __init__(self, *args, **kwargs):
        P4Monitor.__init__(self, *args, **kwargs)

        raise NotImplementedYetException('FlowMonitor with P4-based flow management/export not implemented yet')

    def run_monitor(self, *args, **kwargs):
        pass

    def _handle_cpu_packet(self, cpu_packet):
        pass


class NotImplementedYetException(Exception):

    def __init__(self, message):
        super(NotImplementedYetException, self).__init__(self.__class__.__name__ + ': ' + message)
