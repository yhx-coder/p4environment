/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<48> EthernetAddress;

header ethernet_t {
    EthernetAddress dst_addr;
    EthernetAddress src_addr;
    bit<16>         ether_type;
}

header cpu_t {
    EthernetAddress src_addr;
    bit<16> ingress_port;
}

struct headers_t {
    ethernet_t ethernet;
    cpu_t cpu;
}

struct metadata_t {
    bit<9> ingress_port;
}
