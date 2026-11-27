# Collapse loading of a transmission network with reactive limits

An electrical engineering task (power systems, voltage stability). The solver is given one small transmission
network and a specification, and has to deliver a program that computes, for that network and for six further
networks it never sees, the loading at which the operating state disappears, the bus voltages in that state and
the kind of collapse.

| Path | Content |
| --- | --- |
| `instruction.md` | the task statement |
| `environment/` | image of the working environment; `data/SPEC.md` (the specification), `data/PROVENANCE.md` (sources of the model and of the data ranges), `data/example/case.json` (the example case) |
| `solution/` | the reference solution (`tool.py`) and `solve.sh`, which installs it and writes the report of the example case |
| `tests/` | the verifier: `test.sh`, the checks, the seven cases (`cases/`), their exact values (`truth/`), the programs that produced both (`truth_source/`) and four shortcut attacks (`anticheat/`) |
| `task.toml` | configuration: time limits, resources, network modes |

## The problem

Loads grow along a fixed direction with a scalar loading. A generator holds the voltage of its bus while its
reactive output is inside its limits; at a limit the output stays at the limit and the voltage is free, and the
generator returns to voltage control if the voltage comes back to the setpoint (`SPEC.md` section 1.3 writes these
rules as three modes). The operating states form a curve in the space of voltages and loading that is smooth
between mode changes and has a corner at each of them. The collapse loading is the largest loading that the curve
reaches before it turns back. It can turn back in two ways:

- at a smooth maximum of the loading (`fold`), where the Jacobian of the power-balance equations is singular;
- at a corner (`limit`): a generator reaches its reactive limit, and on the piece of the curve on which it sits
  at the limit the loading can only decrease while its voltage stays below the setpoint. The Jacobian is regular
  on both sides.

What makes the task demanding:

- The voltage in the collapse state of a `fold` varies with the square root of the distance in loading, so a
  loading that is correct to $10^{-4}$ still leaves voltage errors of several $10^{-3}$ p.u. (measured on the
  cases: about 0.004 to 0.006 p.u. at $10^{-4}$ relative). The state has to be located on the curve, not approached
  by loading steps of ordinary size.
- A `limit` collapse is missed by a method that moves a generator to its limit and carries on: the equations
  still have a solution at higher loadings, with the voltage of that generator above its setpoint, which the
  mode forbids.
- A generator can leave a limit again. In three of the seven cases a generator is at its lower limit in the base
  state and returns to voltage control as the load grows.
- The network model has to be assembled exactly as specified (tap ratio at one end of a branch, charging split
  between the ends, shunts, the slack generator balancing the active power while the other generators follow
  their own direction).

## Reference solution

`solution/tool.py` follows the curve by pseudo-arclength continuation in the unknowns (angles, free magnitudes,
loading): a step along the tangent and a Newton correction in the plane normal to it, with the analytic Jacobian
of the complex power-balance equations. Inside every step it watches, for each regulating generator, the distance
of its reactive output from both limits; for each generator at a limit, the distance of its voltage from the
setpoint on the admissible side; and the loading component of the tangent. The first of these to reach zero is
located by root finding on the step length. If it is the loading component of the tangent, that state is the
collapse state (`fold`). Otherwise the generator changes mode, and the tangent of the new piece is oriented so
that the generator stays admissible; if the loading decreases in that direction, the corner is the collapse state
(`limit`). One case takes about 0.3 s.

## Verification

`tests/test.sh` writes a failing reward first and then runs eight checks: `test_artifacts` (the saved report
`/root/results/example_report.json` and the program file, under the contract of spec section 3) and one
`test_case[<name>]` per case, for the example case and the six further cases. Each of these runs
`/root/results/tool.py` afresh as spec section 4 states (an unprivileged user, read-only copies of the program
and of the case at other paths, a fresh empty working directory, a whitelisted environment, one thread, 120 s of
wall clock) and compares its report with the exact values of the case in `tests/truth/`. Seven runs of 120 s fit
1.5 times into the verifier timeout of 1800 s. `tests/finalize_reward.py` records success only when exactly these
eight checks are present and all of them pass.

A report is checked in `tests/task_check.py`: first the contract (exact keys, finite numbers, one magnitude per
bus, non-negative values, one of the two kinds), then the three requirements of the task statement. Failure
messages quote reported values and limits only, never an exact value.

**Exact values.** `tests/truth_source/independent_program.py` computes the exact values
(`tests/truth_source/make_truth.py` runs it on every case). It shares no code with the reference solution and
differs from it in formulation and in method: real polar equations with explicit sums over the conductance and
susceptance matrices, where the reference solution uses complex matrix products; the loading as the continuation
parameter, raised in increments, where the reference solution uses arclength; the state of a mode change as the
solution of the balance equations together with the condition itself; the decision at a mode change from the
sensitivity of the released quantity to the loading; and a smooth maximum as the solution of the point-of-collapse
equations (balance equations and a null vector of their Jacobian). The two programs agree to $1.1 \times 10^{-12}$
relative in the collapse loading and $7.2 \times 10^{-13}$ p.u. in the voltages on the seven cases, and to
$1.4 \times 10^{-12}$ in both on 178 further draws of the family that are not cases of the task (165 of the kind
`fold`, 13 of the kind `limit`; the kind agreed on all of them).

**Tolerances and their rationale.** Each tolerance accepts correct implementations, including coarse but valid
numerics, and rejects the nearest wrong method. Deviations are from the exact values of `tests/truth/`, the
largest over the seven cases.

| Requirement | Tolerance | Correct implementations | Nearest wrong methods |
| --- | --- | --- | --- |
| 1, `collapse_loading` | $10^{-4}$ relative | reference $1.1 \times 10^{-12}$; repeated power flow with mode changes located exactly and the loading increment halved down to $10^{-6}$: $7.0 \times 10^{-7}$ | a generator that reaches a limit stays there and its voltage is never compared with the setpoint: 2.2 % to 46 % on four cases; reactive limits ignored: 3.5 % to 240 % on all seven |
| 2, `bus_voltage_pu` | $10^{-3}$ p.u. | reference $7.2 \times 10^{-13}$; the same repeated power flow with increments down to $10^{-6}$: $3.5 \times 10^{-4}$ | the same repeated power flow stopped at increments of $10^{-4}$: $2.5 \times 10^{-3}$ and $3.4 \times 10^{-3}$ on two cases (its loading is within $6.5 \times 10^{-5}$); one-way limits: 0.026 to 0.19 |
| 3, `collapse_kind` | exact | both programs on all seven cases and on the 178 further draws | one-way limits and no limits report `fold` on the three `limit` cases |

Rule (c) of spec section 5 keeps the two kinds apart: no generator changes mode within 0.01 of the collapse
loading unless that change is the collapse state, so a report cannot be right in loading and voltage and still
be undecided between the kinds.

**Scored submissions.** Each of the following was installed as `/root/results/tool.py`, with the saved report
stated, and run through `tests/test.sh` in a fresh container of the tests image (one CPU, 2048 MB, no network).

| Submission | Checks passed | Reward |
| --- | --- | --- |
| Reference solution (`solution/solve.sh` run in the environment image) | 8 of 8 | 1 |
| `tests/truth_source/independent_program.py` with its own report of the example case | 8 of 8 | 1 |
| No files | 0 of 8 | 0 |
| Control: reactive limits ignored | 0 of 8 | 0 |
| Control: one-way limits (no return to voltage control, no comparison with the setpoint) | 4 of 8 (fails `further_1`, `further_4`, `further_5`, `further_6`) | 0 |
| Control: repeated power flow, the last converged level taken as the collapse state, increments down to $10^{-4}$ | 5 of 8 (fails the saved report, `example`, `further_2`) | 0 |

**Shortcut attacks.** The four programs of `tests/anticheat/` were run the same way. Each received reward 0, the
reward still read 0 thirty seconds after `test.sh` ended, and the files of `/tests` were unchanged.

- `attack_read_reference.py` looks for the exact values instead of computing (truth files, stored cases,
  `/root`, the log directory, a walk of the file system). None of these is readable by the program's user, which
  `test.sh` asserts before any run. With the reference report saved for the example case, `test_artifacts`
  passes and all seven runs fail.
- `attack_replay_example.py` writes the reference report of the example case for every case. `test_artifacts`
  and the run on the example case pass; the six further cases fail.
- `attack_link_reference.py` makes its report a hard or symbolic link to the truth file of its case, and its
  saved report is a symbolic link to the truth file of the example case. Links are rejected (reports are opened
  as regular files only, without following links): all eight checks fail.
- `attack_tamper_harness.py` tries to write a passing reward, to overwrite the grading files and to leave state
  and a detached process behind. Every write is refused and no process of the program's user survives the run;
  the six further cases fail.

## The cases

`tests/truth_source/generate_cases.py` draws networks from the family of spec section 5 with one random stream
of fixed seed, keeps the draws that meet the three rules stated there, and takes the first kept draw of the kind
`fold` as the example case and, of the kept draws after it, the first three of each kind as the further cases.
Spec section 5 states the rules and the three-and-three composition.

| Case | Buses | Generators besides the slack (base modes) | Mode changes before collapse | Collapse |
| --- | --- | --- | --- | --- |
| `example` | 8 | 3 (all regulating) | three reach the upper limit | `fold` at 0.7795 |
| `further_1` | 7 | 3 (one at the lower limit) | one to the upper limit, one back from the lower limit to regulating, two to the upper limit | `fold` at 1.7793 |
| `further_2` | 9 | 3 (all regulating) | three reach the upper limit | `fold` at 0.8099 |
| `further_3` | 6 | 3 (all regulating) | three reach the upper limit | `fold` at 3.7637 |
| `further_4` | 7 | 2 (both regulating) | none | `limit` at 0.9231 |
| `further_5` | 6 | 2 (one at the lower limit) | one back from the lower limit to regulating, one to the upper limit | `limit` at 2.9061 |
| `further_6` | 8 | 3 (one at the lower limit) | one to the upper limit, one back to regulating, one to the upper limit | `limit` at 1.5707 |

## Reproducing

```
python tests/truth_source/generate_cases.py --check    # the cases, byte for byte
python tests/truth_source/make_truth.py --check        # the exact values, byte for byte
```

Both need Python 3.11 with NumPy 1.26.4 and SciPy 1.11.4. The verifier itself runs in the image built from
`tests/`, with the delivered files in `/root/results`: `bash /tests/test.sh` writes `/logs/verifier/reward.txt`.
