/****************************************************************************
 * Copyright 2020-present Christoph Hardegen
 *                        (christoph.hardegen@cs.hs-fulda.de)
 *                        Fulda University of Applied Sciences
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 ****************************************************************************/

#include <core.p4>
#include <v1model.p4>

#include "include/preambel.p4"
#include "include/headers.p4"
#include "include/parsers.p4"
#include "include/checksum.p4"

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   ********************
*************************************************************************/
control MyIngress(inout headers_t hdr,
                  inout metadata_t meta,
                  inout standard_metadata_t standard_metadata) {

    bool dropped = false;

    action drop_action() {
        mark_to_drop(standard_metadata);
        dropped = true;
    }

    action to_port_action(bit<9> port) {
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
        standard_metadata.egress_spec = port;
    }

    action update_nexthop_mac_action(EthernetAddress nexthop_mac) {
        hdr.ethernet.dst_addr = nexthop_mac;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table ipv4_match_table {
        key = {
            hdr.ipv4.dst_addr: lpm;
        }
        actions = {
            drop_action;
            to_port_action;
        }
        size = TABLE_SIZE_L3_FORWARDING;
        default_action = drop_action;
    }

    table nexthop_mac_update_table {
        key = {
            standard_metadata.egress_spec: exact;
        }
        actions = {
            drop_action;
            update_nexthop_mac_action;
        }
        size = TABLE_SIZE_NEXTHOP_UPDATE;
    }

    apply {
        if (hdr.ipv4.isValid() && hdr.ipv4.ttl > 0) {
            ipv4_match_table.apply();
            nexthop_mac_update_table.apply();
        }
        if (dropped) return;
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   ********************
*************************************************************************/
control MyEgress(inout headers_t hdr,
                 inout metadata_t meta,
                 inout standard_metadata_t standard_metadata) {

    action update_source_mac_action(EthernetAddress source_mac) {
        hdr.ethernet.src_addr = source_mac;
    }

    table source_mac_update_table {
        actions = {
            update_source_mac_action;
            NoAction;
        }
        size = TABLE_SIZE_SOURCE_UPDATE;
        default_action = NoAction();
    }

    apply {
        source_mac_update_table.apply();
    }
}

/*************************************************************************
***********************  S W I T C H  ************************************
*************************************************************************/
V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
