/*************************************************************************
*********************** P A R S E R  *************************************
*************************************************************************/
parser FlowForwardingParser(packet_in packet,
                            out headers_t hdr,
                            inout metadata_t meta,
                            inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);

        transition select(hdr.ethernet.ether_type) {
            ether_type_t.IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);

        verify(hdr.ipv4.version == 4w4, error.IPv4IncorrectVersion);

        transition select(hdr.ipv4.protocol) {
            ip_proto_t.ICMP: parse_icmp;
            ip_proto_t.UDP: parse_udp;
            default: accept;
        }
    }

    state parse_icmp {
        packet.extract(hdr.icmp);

        transition accept;
    }

    state parse_udp {
        packet.extract(hdr.udp);

        transition accept;
    }
}

/*************************************************************************
***********************  D E P A R S E R  ********************************
*************************************************************************/
control FlowForwardingDeparser(packet_out packet,
                               in headers_t hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.icmp);
        packet.emit(hdr.udp);
        packet.emit(hdr.cpu);
    }
}
