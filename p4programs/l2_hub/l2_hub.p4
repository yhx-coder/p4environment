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

    action drop_action() {
        mark_to_drop(standard_metadata);
    }

    action broadcast_action() {
        standard_metadata.mcast_grp = 1;
    }

    action to_port_action(bit<9> port) {
        standard_metadata.egress_spec = port;
    }

    table ethernet_match_table {
        key = {
            hdr.ethernet.dst_addr: exact;
        }
        actions = {
            drop_action;
            broadcast_action;
            to_port_action;
        }
        size = TABLE_SIZE_L2_FORWARDING;
        default_action = broadcast_action;
    }

    apply {
        ethernet_match_table.apply();
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   ********************
*************************************************************************/
control MyEgress(inout headers_t hdr,
                 inout metadata_t meta,
                 inout standard_metadata_t standard_metadata) {

    apply {
        if (standard_metadata.mcast_grp == 1)
        {
            if (standard_metadata.egress_port == standard_metadata.ingress_port)
            {
                mark_to_drop(standard_metadata);
            }
        }
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
