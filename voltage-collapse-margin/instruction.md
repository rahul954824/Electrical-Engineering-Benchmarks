# Collapse loading of a transmission network

A system planner needs the loading margin of small transmission networks. Each case describes one network: its buses, lines and transformers, its loads and the direction in which they grow, and its generators, which hold the voltage of their buses only while their reactive output stays inside its limits. The loading is raised slowly from zero. For each case, compute three quantities:

- the collapse loading, which is the supremum of the loadings that can be reached from the base state through operating states that vary continuously with the loading;
- the voltage magnitude of every bus in the state reached at the collapse loading;
- the kind of collapse.

The computation is to be delivered as a program that also handles further cases of the same kind.

The example case is the directory `/root/data/example/`, which holds the case file `/root/data/example/case.json`. The specification `/root/data/SPEC.md` is authoritative for the model of the network, its loads and its generators, the definitions of a state, of the base state, of the collapse loading, of the state reached at it and of the kind of collapse, the case file, the report, the conditions under which the program runs, and the further cases.

Write two files:

1. `/root/results/tool.py`: the program of spec section 4.
2. `/root/results/example_report.json`: the report of spec section 3 for the example case.

## Requirements

The task is complete only when every requirement below holds for `/root/results/example_report.json` and for the report that the program writes, in a fresh run, for each of the seven cases: the example case and the six further cases of spec section 5. Exact values are the values that the definitions of spec section 1 give for the case. A value is within $ x $ relative of its exact value when $ |\text{reported} - \text{exact}| \le x\,|\text{exact}| $.

1. `collapse_loading` is within $ 1 \times 10^{-4} $ relative of its exact value.
2. Every entry of `bus_voltage_pu` is within $ 1 \times 10^{-3} $ p.u. of its exact value.
3. `collapse_kind` is the kind of collapse of the case.
4. On each of the seven cases, the program exits with status 0 within 120 s under the conditions of spec section 4 and writes the report of spec section 3, and that report meets requirements 1 to 3.

You have 18000 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
