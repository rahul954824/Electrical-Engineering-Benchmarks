# Collapse loading of a transmission network with reactive limits: specification

A transmission network supplies loads that grow in a fixed direction, and its generators hold the voltage of their
buses only while their reactive output stays inside its limits. The quantity wanted is the loading at which the
operating state of the network ceases to exist. All electrical quantities are in per unit on a base of 100 MVA.
Angles are in rad in the formulas and in degrees in the case file.

## 1. Definitions

### 1.1 Network

The network has $N$ buses, numbered from 0. Bus $i$ has the complex voltage $U_i = V_i e^{j\theta_i}$ with the
magnitude $V_i > 0$ and the angle $\theta_i$.

A branch runs from a bus $f$ to a bus $t$. It has a series impedance $r + jx$, a total charging susceptance $b$ and
a tap ratio $a$ at its end $f$. With $y = 1/(r + jx)$, the currents that enter the branch at its two ends are

$$ I_f = \frac{y + j\,b/2}{a^2}\,U_f - \frac{y}{a}\,U_t, \qquad I_t = -\frac{y}{a}\,U_f + \left(y + j\,\frac{b}{2}\right) U_t . $$

A bus $i$ may carry a shunt of admittance $g^s_i + j\,b^s_i$ to ground, which draws the current
$(g^s_i + j\,b^s_i)\,U_i$. The power that bus $i$ delivers to the network is

$$ S_i = P_i + jQ_i = U_i\,\overline{I_i}, $$

where $I_i$ is the sum of the currents that enter the branches at bus $i$ and of the current of its shunt, and the
bar denotes the complex conjugate.

### 1.2 Loads and generators

The loading is a number $\lambda \ge 0$. At loading $\lambda$ the load of bus $i$ draws the active power
$P^d_i + \lambda\,\Delta P^d_i$ and the reactive power $Q^d_i + \lambda\,\Delta Q^d_i$, whatever the voltage.

One bus carries the slack generator. It holds the magnitude of its bus at its setpoint and the angle of its bus
at zero, and it supplies whatever active and reactive power this takes.

Every other generator $g$ sits at a bus $i_g$, and no bus carries more than one generator. At loading $\lambda$ it
supplies the active power $P^g + \lambda\,\Delta P^g$. It has a voltage setpoint $V^{set}_g$ and the reactive
limits $Q^{min}_g < Q^{max}_g$.

### 1.3 States

A state at loading $\lambda$ consists of the magnitudes and angles of all buses, with the magnitude of the slack
bus at its setpoint and its angle zero, such that every bus $i$ other than the slack bus meets both of the
following.

Active power: $P_i$ equals the active power of the generator at bus $i$, if there is one, minus the active power
of its load.

Reactive power: let $Q^g_i = Q_i + Q^d_i + \lambda\,\Delta Q^d_i$, the reactive power that a generator at bus $i$
has to supply. If bus $i$ carries no generator, $Q^g_i = 0$. If it carries the generator $g$, one of three modes
holds:

- `regulating`: $V_i = V^{set}_g$ and $Q^{min}_g \le Q^g_i \le Q^{max}_g$;
- `max`: $Q^g_i = Q^{max}_g$ and $V_i \le V^{set}_g$;
- `min`: $Q^g_i = Q^{min}_g$ and $V_i \ge V^{set}_g$.

### 1.4 Collapse loading

The base state is the state at loading 0 in which every generator is in the mode that the case lists for it, and
whose magnitudes and angles are the listed base values up to their rounding.

A loading $\bar\lambda \ge 0$ is attainable if there is a continuous map $\lambda \mapsto s(\lambda)$ on
$[0, \bar\lambda]$ such that $s(0)$ is the base state and $s(\lambda)$ is a state at loading $\lambda$ for every
$\lambda$ in $[0, \bar\lambda]$.

The collapse loading $\lambda_c$ is the supremum of the attainable loadings. The collapse state is the limit of
$s(\lambda)$ as $\lambda \to \lambda_c$ from below along such a map.

The kind of collapse is `limit` if, in the collapse state, some generator has its magnitude at its setpoint and
its reactive power $Q^g$ at one of its two limits at the same time. Otherwise it is `fold`.

For every case of the family of section 5, the base state exists and is unique, $\lambda_c$ is finite and
positive, and the collapse state exists.

## 2. The case

A case is a directory with the single file `case.json`, a JSON object with exactly these keys:

- `case_id`: a string, the name of the case;
- `units`: a string naming the units (informative);
- `buses`: a list of $N$ objects, one per bus in the order of the bus numbers, with the keys `pd` and `qd`
  ($P^d_i$ and $Q^d_i$), `dpd` and `dqd` ($\Delta P^d_i$ and $\Delta Q^d_i$), `gs` and `bs` ($g^s_i$ and
  $b^s_i$), and `voltage_base_pu` and `angle_base_deg` (the magnitude and the angle of the bus in the base state,
  rounded to $10^{-4}$ p.u. and $10^{-4}$ degrees);
- `branches`: a list of objects, one per branch, with the keys `from` and `to` (the buses $f$ and $t$), `r`, `x`,
  `b` and `tap` (the tap ratio $a$);
- `generators`: a list of objects, one per generator. Every object has the keys `bus`, `slack` (`true` for the
  slack generator, `false` otherwise) and `vset` (the setpoint). Every generator other than the slack generator
  also has the keys `pg` and `dpg` ($P^g$ and $\Delta P^g$), `qmin` and `qmax` (its reactive limits) and
  `mode_base` (its mode in the base state: `regulating`, `max` or `min`).

## 3. The report

The report of a case is a JSON object with exactly these keys:

- `collapse_loading`: the collapse loading $\lambda_c$ of section 1.4;
- `bus_voltage_pu`: a list of $N$ numbers, the magnitudes $V_i$ of the buses in the collapse state, in the order
  of the bus numbers;
- `collapse_kind`: the string `fold` or the string `limit`, the kind of collapse of section 1.4.

Every number is a finite JSON number (not a string, boolean or null); objects have no other and no duplicate keys.
`collapse_loading` and every entry of `bus_voltage_pu` are non-negative. Round-off: a reported value may lie at
most $10^{-9}$ outside one of these bounds; such a value stands for the bound itself, and a value further outside
violates the bound. Every report file and the program file `/root/results/tool.py` is a regular, non-empty file
(not a symbolic link) of at most 100,000 bytes, UTF-8 without a byte-order mark.

## 4. The program

`/root/results/tool.py` computes the report of section 3 for the example case and for the further cases of
section 5, cases of the format of section 2. Its command line is

```
python <program> --data <case_dir> --output <report.json>
```

and it writes the report of the case in `<case_dir>` to `<report.json>`. The two options may come in either order.

Conditions the program must work under:

- The program must work when started afresh, once per case, on the example case and on the six further cases of
  section 5 (seven runs).
- Each run must exit with status 0 within **120 s of wall-clock time**, from process start to exit, on one CPU.
- Each run takes place in a separate environment with Python 3.11, NumPy 1.26.4, SciPy 1.11.4 and the standard
  library only, no network access, one CPU and 2048 MB of memory, with `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS` and
  `MKL_NUM_THREADS` set to 1. The environment holds only `PATH`, `HOME`, `TMPDIR`, `LANG` and those three variables;
  `HOME` and `TMPDIR` are the working directory.
- The program runs as an unprivileged user, from a read-only copy at a different path, with a fresh, empty, writable
  working directory as its current directory, which is the only writable location; `<case_dir>` is a read-only copy
  of a case directory and `<report.json>` is a path inside the working directory. Standard input is empty; standard
  output and standard error are discarded. `/root/data` and `/root/results` are not readable: the program must not
  need any file other than its own source and the case directory.
- Every run starts afresh: nothing written by this session or by an earlier run is available.

## 5. Further cases

Besides the example case, the program must handle six further cases that are not shipped. They have the format of
section 2 and were produced like the example case, each from a draw of the following family.

- The number of buses $N$ is 6, 7, 8 or 9 with equal probability. Bus 0 carries the slack generator, with a
  setpoint uniform in $[1.02, 1.05]$, and no load.
- There are 2 or 3 further generators, with equal probability, at distinct buses drawn uniformly from the buses 1
  to $N - 1$.
- Every bus $i \ge 1$ is joined by a branch to a bus drawn uniformly from the buses 0 to $i - 1$. Then 1, 2 or 3
  more branches, with equal probability, are added between pairs of buses drawn uniformly among the pairs that are
  not yet joined. In every branch `from` is the bus with the lower number.
- Two of the branches, drawn uniformly, are transformers: $r = 0$, $x$ uniform in $[0.04, 0.12]$, $b = 0$ and a tap
  ratio uniform in $[0.94, 1.06]$. The others are lines: $x$ uniform in $[0.06, 0.24]$, $r$ equal to $x$ times a
  factor uniform in $[0.08, 0.30]$, $b$ uniform in $[0.01, 0.08]$ and tap ratio 1.
- Every bus without a generator carries a load, and so does every bus with a generator other than bus 0 with
  probability 0.5. A load has $P^d$ uniform in $[0.25, 0.90]$ and a power factor uniform in $[0.85, 0.98]$,
  lagging, which gives $Q^d$. Its increase has $\Delta P^d$ equal to $P^d$ times a factor uniform in $[0.5, 1.5]$,
  and a power factor of its own, uniform in $[0.85, 0.98]$, lagging, which gives $\Delta Q^d$.
- One or two, with equal probability, of the loaded buses without a generator carry a shunt capacitor with $b^s$
  uniform in $[0.05, 0.25]$; no bus has a shunt conductance.
- The generators other than the slack generator share a fraction, uniform in $[0.5, 0.8]$, of the total base
  load $\sum_i P^d_i$ in proportion to weights uniform in $[0.5, 1.5]$, which gives $P^g$. They share a fraction,
  uniform in $[0.4, 0.8]$, of the total increase $\sum_i \Delta P^d_i$ in proportion to the same weights, which
  gives $\Delta P^g$. Each has a setpoint uniform in $[1.00, 1.05]$, an upper limit $Q^{max}$ equal to $P^g$ times
  a factor uniform in $[0.6, 1.6]$, and a lower limit $Q^{min}$ equal to $-Q^{max}$ times a factor uniform in
  $[0.2, 0.5]$.
- The base state was computed by starting with every generator regulating and moving each generator whose
  condition was violated to the mode of the violated condition until no condition was violated. Its modes are the
  `mode_base` entries of the case.

Tap ratios are rounded to $10^{-3}$ and all other data to $10^{-4}$.

A draw was kept only if it met three rules: (a) the base state was found and all of its magnitudes lie in
$[0.94, 1.08]$; (b) $\lambda_c \ge 0.2$; (c) every state of the path of section 1.4 in which a generator changes
its mode, other than the collapse state, has a loading of at most $\lambda_c - 0.01$.

Three of the six further cases have the kind of collapse `fold` and three have the kind `limit`.

The provenance of the model and of these ranges is in `/root/data/PROVENANCE.md`.
