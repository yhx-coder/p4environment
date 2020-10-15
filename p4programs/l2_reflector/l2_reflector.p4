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

    bit<48> tmp_addr;

    apply {
        tmp_addr = hdr.ethernet.dst_addr;
        hdr.ethernet.dst_addr = hdr.ethernet.src_addr;
        hdr.ethernet.src_addr = tmp_addr;

        standard_metadata.egress_spec = standard_metadata.ingress_port;
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   ********************
*************************************************************************/
control MyEgress(inout headers_t hdr,
                 inout metadata_t meta,
                 inout standard_metadata_t standard_metadata) {

    apply { }
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
