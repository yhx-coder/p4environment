traffic_profiles = {
    # 'flow_routing_1_70flows': {'flow_batch_size': 7,
                               # 'flow_batch_interval': 10,
                               # one seed for each experiment iteration
                               # 'seeds': [4221],
                               # individual seeds for each experiment iteration
                               # 'seeds': [42, 21, 4221, 2142, 1337, 3713, 9876, 7698, 7395, 9573],
                               # 'flow_data': [{'src_host': 'h1',
                               #                'dst_host': 'h11',
                               #                'number_flows': 70,
                               #                'flow_distribution_mode': 'static',
                               #                'classes_distribution': [15, 10, 5, 4, 1, 1, 4, 5, 10, 15],
                               #                'flow_throughput': 'generated',
                               #                'link_bw_interval_fraction_percent': 10}]},
    # 'flow_routing_1_50flows': {'flow_batch_size': 5,
                               # 'flow_batch_interval': 10,
                               # one seed for each experiment iteration
                               # 'seeds': [4221],
                               # individual seeds for each experiment iteration
                               # 'seeds': [42, 21, 4221, 2142, 1337, 3713, 9876, 7698, 7395, 9573],
                               # 'flow_data': [{'src_host': 'h1',
                               #                'dst_host': 'h11',
                               #                'number_flows': 50,
                               #                'flow_distribution_mode': 'static',
                               #                'classes_distribution': [10, 7, 5, 2, 1, 1, 2, 5, 7, 10],
                               #                'flow_throughput': 'generated',
                               #                'link_bw_interval_fraction_percent': 15}]},
    'flow_routing_2_70flows': {'flow_batch_size': 7,
                               'flow_batch_interval': 10,
                               # one seed for each experiment iteration
                               'seeds': [4221],
                               # individual seeds for each experiment iteration
                               # 'seeds': [42, 21, 4221, 2142, 1337, 3713, 9876, 7698, 7395, 9573],
                               'flow_data': [{'src_host': 'h1',
                                              'dst_host': 'h7',
                                              'number_flows': 70,
                                              'flow_distribution_mode': 'static',
                                              'classes_distribution': [15, 10, 5, 4, 1, 1, 4, 5, 10, 15],
                                              'flow_throughput': 'generated',
                                              'link_bw_interval_fraction_percent': 10}]},
    'flow_routing_2_50flows': {'flow_batch_size': 5,
                               'flow_batch_interval': 10,
                               # one seed for each experiment iteration
                               'seeds': [4221],
                               # individual seeds for each experiment iteration
                               # 'seeds': [42, 21, 4221, 2142, 1337, 3713, 9876, 7698, 7395, 9573],
                               'flow_data': [{'src_host': 'h1',
                                              'dst_host': 'h7',
                                              'number_flows': 50,
                                              'flow_distribution_mode': 'static',
                                              'classes_distribution': [10, 7, 5, 2, 1, 1, 2, 5, 7, 10],
                                              'flow_throughput': 'generated',
                                              'link_bw_interval_fraction_percent': 15}]},
}
