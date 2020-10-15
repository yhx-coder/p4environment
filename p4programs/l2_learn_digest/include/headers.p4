/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<48> EthernetAddress;

header ethernet_t {
    EthernetAddress dst_addr;
    EthernetAddress src_addr;
    bit<16>         ether_type;
}

struct headers_t {
    ethernet_t ethernet;
}

struct learn_t {
    EthernetAddress src_addr;
    bit<9> ingress_port;
}

struct metadata_t {
    learn_t learn;
}
