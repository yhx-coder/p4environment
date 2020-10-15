/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   **************
*************************************************************************/
control FlowForwardingVerifyChecksum(inout headers_t hdr,
                                     inout metadata_t meta) {
    apply {
        verify_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.tos,
              hdr.ipv4.total_length,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.frag_offset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.src_addr,
              hdr.ipv4.dst_addr},
            hdr.ipv4.hdr_checksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   ***************
*************************************************************************/
control FlowForwardingComputeChecksum(inout headers_t hdr,
                                      inout metadata_t meta) {
     apply {
         update_checksum(
             hdr.ipv4.isValid(),
             { hdr.ipv4.version,
               hdr.ipv4.ihl,
               hdr.ipv4.tos,
               hdr.ipv4.total_length,
               hdr.ipv4.identification,
               hdr.ipv4.flags,
               hdr.ipv4.frag_offset,
               hdr.ipv4.ttl,
               hdr.ipv4.protocol,
               hdr.ipv4.src_addr,
               hdr.ipv4.dst_addr},
             hdr.ipv4.hdr_checksum,
             HashAlgorithm.csum16);
    }
}
