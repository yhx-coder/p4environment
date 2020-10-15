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

    counter(NUM_SWITCH_PORTS_MAX - PORT_COUNTER_INDEX_OFFSET, CounterType.packets_and_bytes) rx_port_counter;

    action drop_action() {
        mark_to_drop(standard_metadata);
    }

    action to_port_action(bit<9> port) {
        standard_metadata.egress_spec = port;
    }

    action to_port_action_ecmp(bit<16> ecmp_base, bit<32> ecmp_count, bit<9> icmp_port) {
        bit<16> src_port = 0;
        bit<16> dst_port = 0;

        if (hdr.ipv4.protocol == IP_PROTOCOLS_TCP) {
            src_port = hdr.tcp.src_port;
            dst_port = hdr.tcp.dst_port;
        }
        else if (hdr.ipv4.protocol == IP_PROTOCOLS_UDP) {
            src_port = hdr.udp.src_port;
            dst_port = hdr.udp.dst_port;
        }

        hash(meta.ecmp_result,
             HashAlgorithm.crc16,
             ecmp_base,
             { hdr.ipv4.src_addr,
               hdr.ipv4.dst_addr,
               hdr.ipv4.protocol,
               src_port,
               dst_port },
             ecmp_count);

        if (hdr.ipv4.protocol == IP_PROTOCOLS_ICMP) {
            meta.ecmp_result = icmp_port;
        }
        standard_metadata.egress_spec = meta.ecmp_result;

    }

    action update_nexthop_mac_action(mac_address_t nexthop_mac) {
        hdr.ethernet.dst_addr = nexthop_mac;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    direct_counter(CounterType.packets_and_bytes) flow_counter;

    table ecmp_table {
        key = {
            hdr.ipv4.dst_addr: lpm;
        }
        actions = {
            drop_action;
            to_port_action;
            to_port_action_ecmp;
        }
        size = TABLE_SIZE_ECMP_FORWARDING;
        default_action = drop_action();
        counters = flow_counter;
    }

    table nexthop_mac_update_table {
        key = {
            standard_metadata.egress_spec: exact;
        }
        actions = {
            update_nexthop_mac_action;
            NoAction;
        }
        size = TABLE_SIZE_NEXTHOP_UPDATE;
        default_action = NoAction();
    }

    apply {
        if (hdr.ipv4.isValid() && hdr.ipv4.ttl > 0) {
            ecmp_table.apply();
            nexthop_mac_update_table.apply();
        }

        rx_port_counter.count((bit<32>) standard_metadata.ingress_port - PORT_COUNTER_INDEX_OFFSET);
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   ********************
*************************************************************************/
control MyEgress(inout headers_t hdr,
                 inout metadata_t meta,
                 inout standard_metadata_t standard_metadata) {

    counter(NUM_SWITCH_PORTS_MAX - PORT_COUNTER_INDEX_OFFSET, CounterType.packets_and_bytes) tx_port_counter;

    action update_source_mac_action(mac_address_t source_mac) {
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

        if (standard_metadata.egress_port != CPU_PORT && standard_metadata.egress_port != DROP_PORT){
            tx_port_counter.count((bit<32>) standard_metadata.egress_port - PORT_COUNTER_INDEX_OFFSET);
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
