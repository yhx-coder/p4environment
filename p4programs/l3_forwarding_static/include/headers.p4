/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<48> EthernetAddress;
typedef bit<32> IPv4Address;

header ethernet_t {
    EthernetAddress dst_addr;
    EthernetAddress src_addr;
    bit<16>         ether_type;
}

header ipv4_t {
    bit<4>         version;
    bit<4>         ihl;
    bit<8>         tos;
    bit<16>        total_len;
    bit<16>        identification;
    bit<3>         flags;
    bit<13>        frag_offset;
    bit<8>         ttl;
    bit<8>         protocol;
    bit<16>        hdr_checksum;
    IPv4Address    src_addr;
    IPv4Address    dst_addr;
}

struct headers_t {
    ethernet_t ethernet;
    ipv4_t     ipv4;
}

struct metadata_t {
}
