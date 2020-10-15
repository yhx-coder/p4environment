/*************************************************************************
*********************** P R E A M B E L **********************************
*************************************************************************/
#define TABLE_SIZE_SOURCE_UPDATE 1
#define TABLE_SIZE_NEXTHOP_UPDATE 42
#define TABLE_SIZE_CPU 1
#define TABLE_SIZE_DROP 1
#define TABLE_SIZE_SWITCH_ID 1
#define TABLE_SIZE_CPU_DATA_FORWARDING 1
#define TABLE_SIZE_ECMP_COMPUTATION_RESULT 1

#define TABLE_SIZE_FLOW_FORWARDING 2048
#define TABLE_SIZE_ICMP_FORWARDING 2048

#define BLOOM_FILTER_ENTRIES 4096
#define BLOOM_FILTER_BIT_WIDTH 1

#define NUM_SWITCH_HOPS_MAX 42
#define NUM_SWITCH_PORTS_MAX 21
#define PORT_INDEX_OFFSET 1

#define CPU_HEADER_STACK_LENGTH_UDP 52

// const bit<16> ETHERTYPE_IPV4 = 0x0800;
enum bit<16> ether_type_t {
    IPV4 = 0x0800
}

// const bit<8> IP_PROTOCOLS_ICMP = 1;
// const bit<8> IP_PROTOCOLS_TCP  = 6;
// const bit<8> IP_PROTOCOLS_UDP  = 17;
enum bit<8> ip_proto_t {
    ICMP = 1,
    TCP  = 6,
    UDP  = 17
}

const bit<9> CPU_PORT          = 510;
const bit<9> DROP_PORT         = 511;
const bit<9> HOST_NETWORK_PORT = 1;

const bit<32> MIRROR_SESSION_ID = 99;

// const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_NORMAL        = 0;
// const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_INGRESS_CLONE = 1;
// const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_EGRESS_CLONE  = 2;
// const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_COALESCED     = 3;
// const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_RECIRCULATION = 4;
// const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_REPLICATION   = 5;
// const bit<32> BMV2_V1MODEL_INSTANCE_TYPE_RESUBMIT      = 6;
enum bit<32> bmv2_v1model_instance_t {
    NORMAL        = 0,
    INGRESS_CLONE = 1,
    EGRESS_CLONE  = 2,
    COALESCED     = 3,
    RECIRCULATION = 4,
    REPLICATION   = 5,
    RESUBMIT      = 6
}

error {
    IPv4IncorrectVersion
}
