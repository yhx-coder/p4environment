# P4Environment
**P4Environment** is a framework that allows to startup predefined **P4 Topologies** (virtual P4-based networks) that are monitored by **P4 Monitors** (collecting topology information *passively*) and controlled by **P4 Controllers** (controlling topology (switch) behaviour *actively*).
The current limitation/assumption is that there is at most one **P4 Controller** and exactly one **P4 Monitor** running for a deployed **P4 Topology**.  
In general, a **P4 Controller** may implement functionalities of a **P4 Monitor** (hybrid entity).

**NOTE (1):** **P4Environment** is initially based on the framework provided for the official P4 language tutorials ([p4lang/tutorials](https://github.com/p4lang/tutorials)).

**NOTE (2):** If you are directly interested in aspects refering to our publication at [**CNSM 2020**](http://www.cnsm-conf.org/2020/index.html) please scroll to the [bottom of this page](#cnsm).

## Setup
**P4Environment** code is expecting Python 2.7 as the supported runtime. In order to install a fully functional P4 setup, we recommend the installation scripts provided at [jafingerhut/p4-guide](https://github.com/jafingerhut/p4-guide/tree/master/bin). 
Especially using [https://github.com/jafingerhut/p4-guide/blob/master/bin/install-p4dev-v2.sh](https://github.com/jafingerhut/p4-guide/blob/master/bin/install-p4dev-v2.sh) installs [mininet](https://github.com/mininet/mininet), [p4c](https://github.com/p4lang/p4c), [behavioral model](https://github.com/p4lang/behavioral-model) including P4 runtime capabilities (simple_switch, simple_switch_grpc) and required dependencies (e.g., [protobuf](https://github.com/protocolbuffers/protobuf), [gRPC](https://github.com/grpc/grpc) and [PI](https://github.com/p4lang/PI)) on a Ubuntu 18.04 system.
You may also have a look at [https://github.com/jafingerhut/p4-guide/blob/master/bin/README-install-troubleshooting.md](https://github.com/jafingerhut/p4-guide/blob/master/bin/README-install-troubleshooting.md) for further details.

**NOTE (1):** 
Right after running the above mentioned setup script(s) you should be able to clone and use **P4Environment** on your system.

**NOTE (2):**
The testbed, in which the experiments for [**CNSM 2020**](http://www.cnsm-conf.org/2020/index.html) were performed, is based on the following software versions (commits):
- *install-p4dev-v2.sh*: 65a761cd0748e1f38fb98a70ddbc3d26626053b4
- *p4c*: bf5d4bac9e78ae7405aca801fad6df97b123ab84
- *behavioral-model*: 3b7b1ff13860aa7e2d8c08d18342aae928bd2a97
- *PI*: 771d5c46106f14f33777e70f39df2ae772cdfe17
- *gRPC*: c7cc34e2d76afe67528ac5b20c5ccbe0692757e8 (tags/v1.17.2)
- *protobuf*: 48cb18e5c419ddd23d9badcfe4e9df7bde1979b2 (v3.6.1)
- *mininet*: bfc42f6d028a9d5ac1bc121090ca4b3041829f86

You might want to slightly adapt the mentioned setup script(s) to consider the above versions (checkout) in order to reproduce the experiments.


## Repository Structure
- [*p4controllers*](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4controllers): 
**P4 Controllers** that can be used to *reactively* and/or *proactively control* a running **P4 Topology**.
    - **P4 Connector** ([p4controllers/p4connector.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4controllers/p4connector.py)) is a connection handler for management connections to each **P4 Switch** within a running **P4 Topology** and it is the essential base class for both **P4 Controllers** and **P4 Monitors**.
    - There is a base class for each **P4 Controller** (see [p4controllers/p4controller.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4controllers/p4controller.py)) that implements basic controller functions. 
      Both the use of the **P4 Switches** gRPC-APIs (runtime_API) as well as their thrift-APIs (runtime_CLI) are supported.
    - Furthermore, there is an additional intermediate class for a **P4 Controller** that supports the use of CPU ports on the **P4 Switches** ([p4controllers/p4controller_cpu.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4controllers/p4controller_cpu.py)).
      A similar implementation of an intermediate class for a digest-based **P4 Controller** is also available ([p4controllers/p4controller_digest.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4controllers/p4controller_digest.py)).
    - Keep in mind that a **P4 Controller** requires the support of specific functions that need to be implemented on the **P4 Switch** side in the deployed/installed **P4 Program(s)**.
    - The provided (example) implementations give a good overview/starting point on how to implement another respectively your own **P4 Controller**, i.e., *Flow Forwarding* ([p4controllers/flow_forwarding.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4controllers/flow_forwarding.py)).  
- [*p4monitors*](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4monitors): 
**P4 Monitors** that can be used to *continuously monitor* a running **P4 Topology**.
    - There is a base class for each **P4 Monitor** ([p4monitors/p4monitor.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4monitors/p4monitor.py)) that implements basic monitor functions and maintains a graph-based model of the principal architecture and state/configuration of the **P4 Topology**.
      Additionally, a set of APIs allows to query and/or modify stored topology information.  
    - Keep in mind that a **P4 Monitor** requires the support of specific functions that need to be implemented on the **P4 Switch** side in the deployed/installed **P4 Program(s)**.
    - The provided (example) implementations give a good overview/starting point on how to implement another respectively your own **P4 Monitor**, i.e., *P4 Counters* ([p4monitors/p4counter.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4monitors/p4counter.py)).  
- [*p4nodes*](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4nodes): 
**P4 Hosts** ([p4nodes/p4host.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4nodes/p4host.py)) and **P4 Switches** (either *P4* or *P4Runtime Switch* ([p4nodes/p4switch.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4nodes/p4switch.py))) as the fundamental structural building blocks of a **P4 Topology**. 
- [*p4topos*](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4topos): 
A **P4 Topology** ([p4topos/p4topo.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4topos/p4topo.py)) is started based on a set of predefined topology parameters ([p4topos/p4topo_params.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4topos/p4topo_params.py)) and CLI-provided parameters ([p4topos/p4topo_parser.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4topos/p4topo_parser.py)) as well as a basic configuration for **P4 Hosts** and **P4 Switches** respectively their links (topology-specific sub-directories in [p4topos](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4topos/)).
    - The build process of a **P4 Topology** outputs a configuration file (*topology.json*) that contains a comprehensive topology configuration ([p4topos/p4topo_generator.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4topos/p4topo_generator.py)).
      This file is used to start a **P4 Topology** and all of its components (e.g., topology and node configuations) and can be further used for sharing or as a comprehensive information source regarding the topology itself (e.g., also for topology visualization).
    - The topology architecture itself (not the potential initialization of **P4 Hosts** and/or **P4 Switches**) is defined by a required link configuration file, whereby you can choose between a static and automatic link respectively switch port configuration mode (each mode uses an individual file specification format (*links_auto.json* and *links_static.json* of the examples provided in [p4topos](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4topos/))). 
    - The provided (example) topologies show an exemplary definition for the links of an **P4 Topology**, i.e., *flow_routing_1* ([p4topos/flow_routing_1](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4topos%2Fflow_routing_1)) and *flow_routing_2* ([p4topos/flow_routing_2](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4topos%2Fflow_routing_2)). 
- [*p4programs*](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4programs): 
**P4 Programs** that can be deployed respectively run on a **P4 Switch**. 
    - All **P4 Programs** that are specified to run on a **P4 Switch** within the **P4 Topology** are automatically compiled during the startup process ([p4programs/p4program_compiler.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4programs/p4program_compiler.py)). 
    - The provided (example) implementations contain **P4 Programs** that either require (dynamic configurations/initializations, e.g., [p4programs/flow_forwarding](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4programs%2Fflow_forwarding)) or do not need (static configurations/initializations, e.g., [p4programs/l2_forwarding_static](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4programs%2Fl2_forwarding_static), [p4programs/l3_forwarding_static](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4programs%2Fl3_forwarding_static) or [p4programs/ecmp_forwarding](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4programs%2Fecmp_forwarding)) an operating **P4 Controller** or **P4 Monitor**. 
- [*p4runtime*](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4runtime): 
Basic **P4 Runtime** functions that support the connection to and configuration of a **P4 Runtime Switch** (gRPC (runtime_API) and Thrift (runtime_API) interfaces).
- [*p4init*](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4init): 
**P4 Initializations** can be used to initially configure **P4 Hosts** (CLI) and **P4 Switches** (P4Runtime, CLI or even both). 
  The initialization files are always specified for a combination of a **P4 Topology** (1st level) and a **P4 Program** that is deployed to the **P4 Switches** (2nd level).
    - The provided examples in [p4init](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4init) illustrate how to specify initial configuration for both **P4 Hosts** and **P4 Switches**.
- [*tools*](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/tools):
Tools and scripts to ...
    - ...send and receive network messages within a running topology (testing purposes, [tools/communication_test](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/tools%2Fcommunication_test)).
    - ...manually (not programatically) interact with a running **P4 Switch** through CLI (simple_switch_CLI, [tools/bmv2_runtime_CLI](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/tools%2Fbmv2_runtime_CLI)).
      Another option to interact with **P4 Switches** having **P4 Runtime** capabilities is to use a runtime shell ([p4runtime-shell](https://github.com/p4lang/p4runtime-shell)).
    - ...log events during the execution of a P4-based virtual network and for consuming nanolog messages from **P4 Switches** ([tools/log](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/tools%2Flog)).
* [*p4env.py*](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4env.py):
Listings of the supported **P4 Topologies**, **P4 Programs** and **P4 Initializations** (strings) as well as the available **P4 Hosts**, **P4 Switches**, **P4 Controllers** and **P4 Monitors** (classes).
* [*p4runner.py*](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4runner.py):
Runner for the construction, execution and configuration respectively initialization of a **P4 Topology**.

## Basic Workflow for Projects within P4Environment
The general workflow to be able to run a **P4 Topology** with **P4Environment** is as follows:
1. Implement your **P4 Program(s)** that should run on any **P4 Switch** and provide a subdirectory with the implementation(s) in [p4programs](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4programs). 
2. Optionally (if required), implement your **P4 Controller** and/or **P4 Monitor** and provide the implementations in [p4controllers](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4controllers) respectively [p4monitors](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4monitors).
3. Specify the architecture of your **P4 Topology** by providing a corresponding subdirectory in [p4topos](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4topos) with a link configuration file.
4. Review the (default) parameters for the **P4 Topology** ([p4topos/p4topo_params.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4topos/p4topo_params.py)) as well as the arguments for the execution of the **P4 Topology** ([p4topos/p4topo_parser.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4topos/p4topo_parser.py)) and maybe change them to your needs.
5. Optionally (if required), provide a **P4 Initialization** subdirectory in [p4init](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4init) with initial configuration options regarding both the **P4 Hosts** and **P4 Switches**.  
6. Run the **P4 Topology**.

**NOTE:**
Added **P4 Resources** (**P4 Topology**, **P4 Program**, **P4 Controller** and **P4 Monitor**) have to be registered to **P4 Environment** by specifying them in the corresponding resource listings in [p4env.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4env.py).

If you (just) want to try **P4Environment** respectively the behaviour of its basic concepts, you can have a look at the provided examples instead of implementing your own project within **P4Environment**. 
There are examples for **P4 Programs**, **P4 Controllers**, **P4 Monitors**, **P4 Topologies** and finally for **P4 Initializations**.

## Example Usage
* Running a **P4 Topology** without a **P4 Controller** (example: ECMP forwarding):
```
sudo python p4runner.py --topology diamond_shape --link_config auto \
                        --p4program ecmp_forwarding \
                        --switch P4RuntimeSwitch --switch_init p4runtime_API \ 
                        --host P4Host --host_init False \
                        --loglevel info
```
* Running a **P4 Topology** with a **P4 Controller** (example: flow forwarding):    //TODO: check/update
```
sudo python p4runner.py --topology diamond_shape_v2 --link_config auto \
                        --p4program flow_forwarding \
                        --switch P4RuntimeSwitch --switch_init hybrid \
                        --host P4Host --host_init False \
                        --p4monitor PortCounterMonitor \
                        --p4controller FlowForwardingController --p4controller_flow_forwarding_strategy ecmp --p4controller_flow_forwarding_metric random \
                        --loglevel info
```
**NOTE:** Notice that -- when you do not use a more specific one -- a basic **P4 Monitor** is always started for each **P4 Topology** implicitly (e.g., discovery), whereas a **P4 Controller** always has to be specified explicitly.

In addition, looking at the provided L2 learning examples is a good entry point for understanding and implementing CPU port- or digest-based solutions in a **P4 Controller**:
- CPU port-based L2 learning for **P4 Switches**
    - [p4programs/l2_learn_cpu/l2_learn_cpu.p4](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4programs/l2_learn_cpu/l2_learn_cpu.p4)
    - [p4controllers/l2_learn_cpu.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4controllers/l2_learn_cpu.py)
 
    Running a **P4 Topology** with the respective L2 learning **P4 Controller**:
    ```
    sudo python p4runner.py --topology linear_switches --link_config auto \ 
                            --p4program l2_learn_cpu \
                            --switch P4RuntimeSwitch --switch_init None \
                            --host P4Host --host_init False \    
                            --p4monitor P4Monitor \ 
                            --p4controller L2LearnControllerCPU \
                            --loglevel info
    ```
- Digest-based L2 learning for **P4 Switches**
    - [p4programs/l2_learn_digest/l2_learn_digest.p4](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4programs/l2_learn_digest/l2_learn_digest.p4)
    - [p4controllers/l2_learn_digest.py](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4controllers/l2_learn_digest.py)

    Running a **P4 Topology** with the respective L2 learning **P4 Controller**:
    ```
    sudo python p4runner.py --topology linear_switches --link_config auto \
                            --p4program l2_learn_digest \
                            --switch P4Switch --switch_init None \
                            --host P4Host --host_init False \
                            --p4monitor P4Monitor \
                            --p4controller L2LearnControllerDigest \
                            --loglevel info
    ```

## Example P4 Programs
A lot of good examples for some P4 concepts and their implementation can be found at [p4-learning/examples](https://github.com/nsg-ethz/p4-learning/tree/master/examples) or at [jafingerhut/p4-guide](https://github.com/jafingerhut/p4-guide).

## CNSM 2020 
<a name="cnsm" id="cnsm"></a>
Besides the general concepts of **P4 Environment**, the following aspects refer to the publication *"Prediction-based Flow Routing in Programmable Networks with P4"* accepted as short paper and poster at the [*16th International Conference on Network and Service Management (CNSM) 2020*](http://www.cnsm-conf.org/2020/index.html):
- **P4 Program**: [**Flow Forwarding**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4programs/flow_forwarding)
- **P4 Controller**: [**Flow Forwarding**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4controllers/flow_forwarding.py)
- **P4 Monitor**: [**Port Counter**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4monitors/p4port_counter.py)
- **P4 Topologies**: [**flow_routing_1**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4topos/flow_routing_1), [**flow_routing_2**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/tree/master/p4topos/flow_routing_2)
- **Traffic Profiles**: [**Traffic Profile Generator**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/tools/traffic_profiles/traffic_profiles_generator.py), [**Traffic Profile Replay**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/p4topos/p4topo_traffic.py) 
- **Experiments**: [**Experiment Generator**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/tools/experiments/experiments_generator.py), [**Experiment Runner**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/exp_runner.py), [**Experiment Evaluator (Visualization)**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/tools/experiments/visualization/experiments_visualization.py), [**Experiment Evaluator (Time Measure)**](https://gitlab.cs.hs-fulda.de/flow-routing/cnsm2020/p4environment/-/blob/master/tools/experiments/time_measure/experiments_time_measure.py) 

**NOTE:** The *Traffic Profile Generator* and the *Experiment Generator* output all required files and CLI commands to run (cf. *Experiment Runner*) and evaluate the experiments performed for [CNSM 2020](http://www.cnsm-conf.org/2020/index.html).

## Contact
Feel free to drop us an email regarding **P4Environment**:
* [Christoph Hardegen](mailto:christoph.hardegen@cs.hs-fulda.de)
* [Sebastian Rieger](mailto:sebastian.rieger@cs.hs-fulda.de)