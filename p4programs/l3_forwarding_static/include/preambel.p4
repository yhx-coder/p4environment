/*************************************************************************
*********************** P R E A M B E L **********************************
*************************************************************************/

#define TABLE_SIZE_L3_FORWARDING 1024
#define TABLE_SIZE_NEXTHOP_UPDATE 5
#define TABLE_SIZE_SOURCE_UPDATE 1

const bit<16> ETHERTYPE_IPV4 = 0x800;

error {
    IPv4IncorrectVersion,
    IPv4OptionsNotSupported
}
