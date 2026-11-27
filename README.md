# Electrical Engineering Benchmarks

Benchmark tasks in electrical engineering for evaluating AI coding agents. Each task gives the agent a
specification and one example case, asks for a program, and checks that program on hidden cases against exact
values computed by an independent implementation.

| Task | Area | What the agent has to compute |
| --- | --- | --- |
| [`voltage-collapse-margin`](voltage-collapse-margin/) | Power systems, voltage stability | The loading at which a transmission network with generator reactive-power limits loses its operating state, the bus voltages in that state, and whether the collapse is a smooth maximum or is triggered by a generator reaching its limit |

## Layout of a task

| Path | Content |
| --- | --- |
| `instruction.md` | the task statement given to the agent |
| `environment/` | the agent's working image, the specification, the example case and the sources of the model and data |
| `solution/` | the reference solution |
| `tests/` | the verifier, the hidden cases, their exact values, the independent implementation that produced them, and shortcut attacks the verifier is tested against |
| `task.toml` | time limits, resources and network modes |
| `README.md` | design notes: why the task is demanding, how the exact values were obtained, tolerances and their rationale, and the results of wrong-method controls |

## Checking a task

Every task was validated in containers built from its own files, without network access: the reference solution
and the independent implementation each pass every check, an empty submission and each wrong-method control
receive no reward, and each shortcut attack is rejected. The task's `README.md` lists the results.
