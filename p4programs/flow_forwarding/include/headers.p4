/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/
typedef bit<48> mac_address_t;
typedef bit<32> ipv4_address_t;
typedef bit<8>  port_t;

header ethernet_t {
    mac_address_t dst_addr;
    mac_address_t src_addr;
    bit<16>       ether_type;
}

header ipv4_t {
    bit<4>         version;
    bit<4>         ihl;
    bit<8>         tos;
    bit<16>        total_length;
    bit<16>        identification;
    bit<3>         flags;
    bit<13>        frag_offset;
    bit<8>         ttl;
    bit<8>         protocol;
    bit<16>        hdr_checksum;
    ipv4_address_t src_addr;
    ipv4_address_t dst_addr;
}

header icmp_t {
    bit<8>  type;
    bit<8>  code;
    bit<16> checksum;
}

header udp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> len;
    bit<16> checksum;
}

header cpu_t {
    port_t  ingress_port;
    bit<16> flow_hash_one;
    bit<32> flow_hash_two;
    port_t  ecmp_result;
}

struct metadata_t {
    bit<16> flow_hash_one;
    bit<32> flow_hash_two;

    bit<1> result_val_one;
    bit<1> result_val_two;

    port_t ecmp_result;
}

struct headers_t {
    ethernet_t ethernet;     // 14 bytes
    ipv4_t     ipv4;         // 20 bytes
    icmp_t     icmp;         // 04 bytes
    udp_t      udp;          // 08 bytes
    cpu_t      cpu;          // 10 bytes
}
