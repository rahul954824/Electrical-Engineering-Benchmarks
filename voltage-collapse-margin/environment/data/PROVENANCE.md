# Provenance of the model and of the cases

The model is the steady-state (power-flow) description of a transmission network that is used for long-term voltage
stability studies: loads of constant power that grow in a fixed direction, generators that hold the voltage of
their buses while their reactive output is inside its capability, and a slack generator that balances the active
power. The quantity computed is the loading margin of the network in that direction.

## The model

- Bus power balance in per unit and the nodal admittance description of lines, transformers and shunts: Kundur
  (1994), chapter 6; Grainger and Stevenson (1994). The branch of section 1.1 of the
  specification is the usual pi model with half of the charging susceptance at each end and an ideal transformer
  of ratio $a$ at one end, the convention of Zimmerman, Murillo-Sanchez and Thomas (2011).
- Loads that grow in a fixed direction with a scalar loading, and the loading margin as the distance to the
  point at which the operating state disappears: Van Cutsem and Vournas (1998); Taylor (1994).
- Generators as voltage-controlled buses with reactive limits; a generator that reaches a limit keeps its
  reactive output at the limit and no longer holds its voltage, and returns to voltage control when its voltage
  comes back to the setpoint: Kundur (1994), chapter 6; Van Cutsem and Vournas (1998). The three modes of section 1.3 of the specification are these rules written as conditions on a
  state.
- Disappearance of the operating state at a smooth maximum of the loading (saddle-node bifurcation, the nose of the
  curve of voltage against loading): Ajjarapu and Christy (1992); Canizares and Alvarado (1993).
- Disappearance of the operating state at the loading at which a generator reaches its reactive limit, without a
  smooth maximum (limit-induced bifurcation): Dobson and Lu (1992).

## The cases

| Quantity | Family | Source or reason |
| --- | --- | --- |
| Base | 100 MVA | the usual system base of transmission studies (Kundur 1994) |
| Line reactance | 0.06 to 0.24 p.u. | 138 kV to 230 kV overhead lines of about 25 to 250 km on 100 MVA; comparable with the line data of the IEEE 14-bus test system (Christie 1993) |
| Line resistance | 0.08 to 0.30 of the reactance | $X/R$ of 3 to 12, the range of overhead lines of these voltages (Grainger and Stevenson 1994) |
| Line charging | 0.01 to 0.08 p.u. | comparable with the same test system |
| Transformer reactance and tap | 0.04 to 0.12 p.u., 0.94 to 1.06, no resistance | leakage reactances of network transformers on 100 MVA and the usual range of off-nominal taps; the transformers of the IEEE 14-bus system have taps of 0.932 to 0.978 |
| Load | 25 to 90 MW per bus, power factor 0.85 to 0.98 lagging | bulk supply points; power factors of transmission-level loads (Taylor 1994) |
| Direction of the load increase | 0.5 to 1.5 of the base load per bus, with a power factor of its own | a load growth that is not proportional, the general case of a loading direction (Van Cutsem and Vournas 1998) |
| Shunt capacitors | 0.05 to 0.25 p.u. at one or two load buses | reactive compensation of 5 to 25 Mvar at bulk supply points |
| Voltage setpoints | 1.00 to 1.05 p.u.; slack 1.02 to 1.05 p.u. | the usual range of generator terminal schedules |
| Reactive limits | upper limit 0.6 to 1.6 of the base active output, lower limit 0.2 to 0.5 of the upper limit in magnitude | a generator of rated power factor 0.85 to 0.9 can supply reactive power of about 0.5 to 0.6 of its rating and absorb much less (Kundur 1994, section 5.4); the base output of a unit is a part of its rating |
| Base voltages | 0.94 to 1.08 p.u. | a normal operating band of transmission voltages, slightly widened |

## References

- Ajjarapu, V. and Christy, C. (1992). The continuation power flow: a tool for steady state voltage stability
  analysis. IEEE Transactions on Power Systems 7 (1), 416-423.
- Canizares, C. A. and Alvarado, F. L. (1993). Point of collapse and continuation methods for large AC/DC systems.
  IEEE Transactions on Power Systems 8 (1), 1-8.
- Christie, R. D. (1993). Power Systems Test Case Archive. University of Washington.
- Dobson, I. and Lu, L. (1992). Voltage collapse precipitated by the immediate change in stability when generator
  reactive power limits are encountered. IEEE Transactions on Circuits and Systems I 39 (9), 762-766.
- Grainger, J. J. and Stevenson, W. D. (1994). Power System Analysis. McGraw-Hill.
- Kundur, P. (1994). Power System Stability and Control. McGraw-Hill.
- Taylor, C. W. (1994). Power System Voltage Stability. McGraw-Hill.
- Van Cutsem, T. and Vournas, C. (1998). Voltage Stability of Electric Power Systems. Kluwer.
- Zimmerman, R. D., Murillo-Sanchez, C. E. and Thomas, R. J. (2011). MATPOWER: steady-state operations, planning,
  and analysis tools for power systems research and education. IEEE Transactions on Power Systems 26 (1), 12-19.
