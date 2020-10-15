experiments = {
    'run_mode': 'experiment',
    'p4program': 'flow_forwarding',
    'p4monitor': 'PortCounterMonitor',
    'p4controller': 'FlowForwardingController',
    'p4controller_flow_forwarding_strategy': {
        'shortest_path': {
            'p4controller_flow_forwarding_metric': ['hops']
        },
        'ecmp': {
            'p4controller_flow_forwarding_metric': ['hash', 'round_robin', 'random']
        },
        'path_property': {
            'p4controller_flow_forwarding_metric': ['load_port_counter']
        },
        'flow_prediction': {
            'p4controller_flow_forwarding_metric': ['throughput']
        },
        'p4controller_time_measurement': True,
    },
    'topology': {
        # 'flow_routing_1': {
        #     'traffic_profile': ['flow_routing_1_50flows', 'flow_routing_1_70flows']
        # },
        'flow_routing_2': {
            'traffic_profile': ['flow_routing_2_50flows', 'flow_routing_2_70flows']
        },
    },
}
