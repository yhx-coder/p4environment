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
 *
 * Part of the publication "Prediction-based Flow Routing in Programmable Networks with P4" accepted as
 * short paper and poster at the 16th International Conference on Network and Service Management (CNSM) 2020.
 *
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
control FlowForwardingIngress(inout headers_t hdr,
                              inout metadata_t meta,
                              inout standard_metadata_t standard_metadata) {

    register<bit<BLOOM_FILTER_BIT_WIDTH>>(BLOOM_FILTER_ENTRIES) bloom_filter;

    counter(NUM_SWITCH_PORTS_MAX - PORT_INDEX_OFFSET, CounterType.packets_and_bytes) rx_port_counter;   // CounterType.bytes

    action compute_ecmp_result_action(bit<16> ecmp_base, bit<32> ecmp_count) {
        hash(meta.ecmp_result,
             HashAlgorithm.crc32,   // HashAlgorithm.crc16
             ecmp_base,
             { hdr.ipv4.src_addr,
               hdr.ipv4.dst_addr,
               hdr.ipv4.protocol,
               hdr.udp.src_port,
               hdr.udp.dst_port },
             ecmp_count);
    }

    action compute_flow_hashes_action() {
        hash(meta.flow_hash_one,
             HashAlgorithm.crc16,
             (bit<16>)0,
             {hdr.ipv4.src_addr,
              hdr.ipv4.dst_addr,
              hdr.udp.src_port,
              hdr.udp.dst_port,
              hdr.ipv4.protocol},
             (bit<16>)BLOOM_FILTER_ENTRIES);

        hash(meta.flow_hash_two,
             HashAlgorithm.crc32,
             (bit<32>)0,
             {hdr.ipv4.src_addr,
              hdr.ipv4.dst_addr,
              hdr.udp.src_port,
              hdr.udp.dst_port,
              hdr.ipv4.protocol},
             (bit<32>)BLOOM_FILTER_ENTRIES);
    }

    action drop_action() {
        mark_to_drop(standard_metadata);
    }

    action to_port_action(bit<9> port) {
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
        standard_metadata.egress_spec = port;
    }

    action to_cpu_action() {
        standard_metadata.egress_spec = CPU_PORT;
        //clone(CloneType.I2E, MIRROR_SESSION_ID);
    }

    action update_source_mac_action(mac_address_t source_mac) {
        hdr.ethernet.src_addr = source_mac;
    }

    action update_nexthop_mac_action(mac_address_t nexthop_mac) {
        hdr.ethernet.dst_addr = nexthop_mac;
    }

    table ecmp_result_computation_table {
        actions = {
            compute_ecmp_result_action;
            NoAction;
        }
        size = TABLE_SIZE_ECMP_COMPUTATION_RESULT;
        default_action = NoAction();
    }

    table flow_forwarding_table {
        key = {
            meta.flow_hash_one: exact;
            meta.flow_hash_two: exact;
        }
        actions = {
            drop_action;
            to_port_action;
            NoAction;
        }
        size = TABLE_SIZE_FLOW_FORWARDING;
        default_action = NoAction();
    }

    table source_mac_update_table {
        actions = {
            update_source_mac_action;
            NoAction;
        }
        size = TABLE_SIZE_SOURCE_UPDATE;
        default_action = NoAction();
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

    table cpu_table_forwarding {
        actions = {
            to_cpu_action;
            NoAction;
        }
        size = TABLE_SIZE_CPU;
        default_action = to_cpu_action();
    }

    table icmp_forwarding_table {
        key = {
            hdr.ipv4.src_addr: exact;
            hdr.ipv4.dst_addr: exact;
        }
        actions = {
            to_port_action;
            drop_action;
            NoAction;
        }
        size = TABLE_SIZE_ICMP_FORWARDING;
        default_action = drop_action();
    }

    apply {
        if (standard_metadata.ingress_port != CPU_PORT && standard_metadata.ingress_port != DROP_PORT) {
            rx_port_counter.count((bit<32>) standard_metadata.ingress_port - PORT_INDEX_OFFSET);
        }

        if (hdr.ethernet.ether_type == ether_type_t.IPV4) {
            if (hdr.ipv4.isValid() && hdr.ipv4.ttl > 1) {
                if(hdr.ipv4.protocol == ip_proto_t.ICMP) {
                    icmp_forwarding_table.apply();
                    return;
                }

                compute_flow_hashes_action();

                if (flow_forwarding_table.apply().hit) {
                    source_mac_update_table.apply();
                    nexthop_mac_update_table.apply();
                }
                else {
                    bloom_filter.read(meta.result_val_one, (bit<32>)meta.flow_hash_one);
                    bloom_filter.read(meta.result_val_two, meta.flow_hash_two);

                    if (meta.result_val_one == 1 && meta.result_val_two == 1) {
                        drop_action();
                    }
                    else {
                        bloom_filter.write((bit<32>)meta.flow_hash_one, 1);
                        bloom_filter.write(meta.flow_hash_two, 1);

                        ecmp_result_computation_table.apply();
                        cpu_table_forwarding.apply();
                    }
                }
            }
            else {
                drop_action();
            }
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   ********************
*************************************************************************/
control FlowForwardingEgress(inout headers_t hdr,
                             inout metadata_t meta,
                             inout standard_metadata_t standard_metadata) {

    counter(NUM_SWITCH_PORTS_MAX - PORT_INDEX_OFFSET, CounterType.packets_and_bytes) tx_port_counter;

    action write_cpu_data_forwarding() {
        hdr.cpu.setValid();
        hdr.cpu.ingress_port = (bit<8>)standard_metadata.ingress_port;
        hdr.cpu.flow_hash_one = meta.flow_hash_one;
        hdr.cpu.flow_hash_two = meta.flow_hash_two;
        hdr.cpu.ecmp_result = meta.ecmp_result;
    }

    table cpu_forwarding_data_table {
        actions = {
            write_cpu_data_forwarding;
            NoAction;
        }
        size = TABLE_SIZE_CPU_DATA_FORWARDING;
        default_action = write_cpu_data_forwarding;
    }

    apply {
        if (hdr.ethernet.ether_type == ether_type_t.IPV4) {
            if (hdr.ipv4.isValid()) {
                // if (standard_metadata.instance_type == bmv2_v1model_instance_t.INGRESS_CLONE) {
                //     hdr.cpu.setValid();
                //     hdr.cpu.ingress_port = (bit<8>)standard_metadata.ingress_port;
                //     hdr.cpu.flow_hash_one = meta.flow_hash_one;
                //     hdr.cpu.flow_hash_two = meta.flow_hash_two;
                //     hdr.cpu.ecmp_result = meta.ecmp_result;
                //
                //     truncate((bit<32>)CPU_HEADER_STACK_LENGTH_UDP);
                // }
                if (standard_metadata.egress_port == CPU_PORT) {
                    cpu_forwarding_data_table.apply();
                }

                if (standard_metadata.instance_type == bmv2_v1model_instance_t.NORMAL &&
                    standard_metadata.egress_port != CPU_PORT && standard_metadata.egress_port != DROP_PORT) {
                    tx_port_counter.count((bit<32>) standard_metadata.egress_port - PORT_INDEX_OFFSET);
                }
            }
        }
    }
}

/*************************************************************************
***********************  S W I T C H  ************************************
*************************************************************************/
V1Switch(
FlowForwardingParser(),
FlowForwardingVerifyChecksum(),
FlowForwardingIngress(),
FlowForwardingEgress(),
FlowForwardingComputeChecksum(),
FlowForwardingDeparser()
) main;
