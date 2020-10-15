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

from enum import Enum

from p4nodes.p4host import P4Host
from p4nodes.p4switch import P4Switch, P4RuntimeSwitch

from p4controllers.flow_forwarding import FlowForwardingController
from p4controllers.l2_learn_cpu import L2LearnControllerCPU
from p4controllers.l2_learn_digest import L2LearnControllerDigest

from p4monitors.p4monitor import P4Monitor
from p4monitors.p4port_counter import PortCounterMonitor
from p4monitors.p4probing import ProbingMonitor
from p4monitors.p4int import INTMonitor
from p4monitors.p4flow import FlowMonitor


class P4NetworkRunModes(Enum):
    CLI = 'CLI'
    EXPERIMENT = 'experiment'


class P4Topologies(Enum):
    SINGLE_SWITCH = 'single_switch'
    LINEAR_SWITCHES = 'linear_switches'
    DIAMOND_SHAPE = 'diamond_shape'
    DIAMOND_SHAPE2 = 'diamond_shape_v2'
    FLOW_ROUTING1 = 'flow_routing_1'
    FLOW_ROUTING2 = 'flow_routing_2'


class P4Hosts(Enum):
    P4Host = P4Host


class P4Switches(Enum):
    P4Switch = P4Switch
    P4RuntimeSwitch = P4RuntimeSwitch


class P4SwitchInit(Enum):
    NONE = 'None'
    P4RUNTIME_CLI = 'p4runtime_CLI'
    P4RUNTIME_API = 'p4runtime_API'
    HYBRID = 'hybrid'


class P4Programs(Enum):
    L2_REFLECTOR = 'l2_reflector'
    L2_HUB = 'l2_hub'
    L2_LEARN_CPU = 'l2_learn_cpu'
    L2_LEARN_DIGEST = 'l2_learn_digest'
    FLOW_FORWARDING = 'flow_forwarding'
    ECMP_FORWARDING = 'ecmp_forwarding'
    L2_FORWARDING_STATIC = 'l2_forwarding_static'
    L3_FORWARDING_STATIC = 'l3_forwarding_static'


class P4Controllers(Enum):
    FlowForwardingController = FlowForwardingController
    L2LearnControllerCPU = L2LearnControllerCPU
    L2LearnControllerDigest = L2LearnControllerDigest


class P4Monitors(Enum):
    P4Monitor = P4Monitor
    PortCounterMonitor = PortCounterMonitor
    ProbingMonitor = ProbingMonitor
    INTMonitor = INTMonitor
    FlowMonitor = FlowMonitor


class LinkConfig(Enum):
    STATIC = 'static'
    AUTO = 'auto'


class HostNetwork(Enum):
    INDIVIDUAL = 'individual'
    SHARED = 'shared'
