/********************************************************************************
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
 *
 *********************************************************************************
 *
 * adapted from nsg-ethz/p4-learning
 * see https://github.com/nsg-ethz/p4-learning/tree/master/examples/04-L2_Learning
 *
 ********************************************************************************/

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

    // action drop_action() {
    //     mark_to_drop(standard_metadata);
    // }

    action mac_learn_action() {
        meta.ingress_port = standard_metadata.ingress_port;
        clone3(CloneType.I2E, MIRROR_SESSION_ID, meta);
    }

    // action broadcast_action() {
    //     standard_metadata.mcast_grp = 1;
    // }

    action to_port_action(bit<9> port) {
        standard_metadata.egress_spec = port;
    }

    action set_multicast_group(bit<16> mcast_grp) {
        standard_metadata.mcast_grp = mcast_grp;
    }

    table ethernet_src_match_table {
        key = {
            hdr.ethernet.src_addr: exact;
        }
        actions = {
            mac_learn_action;
            NoAction;
        }
        size = TABLE_SIZE_L2_FORWARDING;
        default_action = mac_learn_action;
    }

    table ethernet_dst_match_table {
        key = {
            hdr.ethernet.dst_addr: exact;
        }
        actions = {
            // drop_action;
            // broadcast_action;
            to_port_action;
            NoAction;
        }
        size = TABLE_SIZE_L2_FORWARDING;
        // default_action = broadcast_action;
        default_action = NoAction;
    }

    table broadcast_table {
        key = {
            standard_metadata.ingress_port: exact;
        }

        actions = {
            set_multicast_group;
            NoAction;
        }
        size = TABLE_SIZE_L2_FORWARDING;
        default_action = NoAction;
    }

    apply {
        ethernet_src_match_table.apply();
        // ethernet_dst_match_table.apply()
        if (ethernet_dst_match_table.apply().hit){
            ;
        }
        else {
            broadcast_table.apply();
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   ********************
*************************************************************************/
control MyEgress(inout headers_t hdr,
                 inout metadata_t meta,
                 inout standard_metadata_t standard_metadata) {

    apply {
        if (standard_metadata.instance_type == 1){
            hdr.cpu.setValid();
            hdr.cpu.src_addr = hdr.ethernet.src_addr;
            hdr.cpu.ingress_port = (bit<16>)meta.ingress_port;
            hdr.ethernet.ether_type = L2_LEARN_ETHER_TYPE;
            truncate((bit<32>)22);  // Ethernet + CPU Header
        }
        // else
        // {
        //     if (standard_metadata.mcast_grp == 1)
        //     {
        //         if (standard_metadata.egress_port == standard_metadata.ingress_port)
        //         {
        //             mark_to_drop(standard_metadata);
        //         }
        //     }
        // }
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
