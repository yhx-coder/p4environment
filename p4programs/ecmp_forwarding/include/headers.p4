/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<48>  mac_address_t;
typedef bit<32>  ipv4_address_t;

header ethernet_t {
    mac_address_t dst_addr;
    mac_address_t src_addr;
    bit<16>       ether_type;
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
    ipv4_address_t src_addr;
    ipv4_address_t dst_addr;
}

header tcp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<32> seq_num;
    bit<32> ack_num;
    bit<4>  data_offset;
    bit<4>  reserved;
    bit<8>  flags;
    bit<16> window;
    bit<16> checksum;
    bit<16> urgent_ptr;
}

header udp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> len;
    bit<16> checksum;
}

struct metadata_t {
    bit<9> ecmp_result;
    bit<7> padding;
}

struct headers_t {
    ethernet_t ethernet;
    ipv4_t     ipv4;
    tcp_t      tcp;
    udp_t      udp;
}
