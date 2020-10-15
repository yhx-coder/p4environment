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

struct metadata_t {
}
