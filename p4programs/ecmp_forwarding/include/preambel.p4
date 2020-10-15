/*************************************************************************
*********************** P R E A M B E L **********************************
*************************************************************************/
#define IP_PROTOCOLS_ICMP 1
#define IP_PROTOCOLS_TCP 6
#define IP_PROTOCOLS_UDP 17

#define TABLE_SIZE_ECMP_FORWARDING 1024
#define TABLE_SIZE_NEXTHOP_UPDATE 5
#define TABLE_SIZE_SOURCE_UPDATE 1

#define NUM_SWITCH_PORTS_MAX 10
#define PORT_COUNTER_INDEX_OFFSET 1

const bit<16> ETHERTYPE_IPV4 = 0x800;

const bit<9> CPU_PORT = 510;
const bit<9> DROP_PORT = 511;

error {
    IPv4IncorrectVersion,
    IPv4OptionsNotSupported
}
