#!/usr/bin/env python3
"""Independent computation of the collapse loading (SPEC.md), sharing no code with the reference solution.

Formulation. Real polar power-balance equations with explicit sums over the conductance and susceptance
matrices, assembled branch by branch, and their textbook partial derivatives. The loading is the continuation
parameter: it is raised in increments and the equations are solved by Newton iteration at each level. After
every level the admissibility of every generator is checked. A violated condition means that a generator changed
mode inside the increment; the state of the change is the solution of the balance equations together with the
condition itself (reactive output equal to the limit, or magnitude equal to the setpoint), with the loading as
an additional unknown. After a mode change the sensitivity of the released quantity to the loading on the new
piece decides whether the path continues to higher loadings. When the Newton iteration at a level fails for a
small increment, the smooth maximum of the loading is computed directly as the solution of the balance equations
together with the condition that their Jacobian has a null vector (the point-of-collapse equations).
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

TOL = 1e-12


def read_case(case):
    n = len(case['buses'])
    G = np.zeros((n, n))
    B = np.zeros((n, n))
    for br in case['branches']:
        f, t, a = br['from'], br['to'], br['tap']
        den = br['r'] ** 2 + br['x'] ** 2
        g, b = br['r'] / den, -br['x'] / den
        half = 0.5 * br['b']
        G[f, f] += g / a ** 2
        B[f, f] += (b + half) / a ** 2
        G[t, t] += g
        B[t, t] += b + half
        G[f, t] -= g / a
        B[f, t] -= b / a
        G[t, f] -= g / a
        B[t, f] -= b / a
    for i, bus in enumerate(case['buses']):
        G[i, i] += bus['gs']
        B[i, i] += bus['bs']
    return n, G, B


class Model:
    def __init__(self, case):
        self.case = case
        self.n, self.G, self.B = read_case(case)
        self.slack = next(g['bus'] for g in case['generators'] if g['slack'])
        self.vslack = next(g['vset'] for g in case['generators'] if g['slack'])
        self.units = [dict(g) for g in case['generators'] if not g['slack']]
        self.mode = [g['mode_base'] for g in self.units]

    def specified(self, lam):
        p = np.zeros(self.n)
        q = np.zeros(self.n)
        for i, bus in enumerate(self.case['buses']):
            p[i] -= bus['pd'] + lam * bus['dpd']
            q[i] -= bus['qd'] + lam * bus['dqd']
        for g, mode in zip(self.units, self.mode):
            p[g['bus']] += g['pg'] + lam * g['dpg']
            if mode == 'max':
                q[g['bus']] += g['qmax']
            elif mode == 'min':
                q[g['bus']] += g['qmin']
        return p, q

    def flows(self, th, v):
        """Injected active and reactive power of every bus and the four blocks of partial derivatives."""
        n, G, B = self.n, self.G, self.B
        p = np.zeros(n)
        q = np.zeros(n)
        pth = np.zeros((n, n))
        pv = np.zeros((n, n))
        qth = np.zeros((n, n))
        qv = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if G[i, j] == 0.0 and B[i, j] == 0.0:
                    continue
                d = th[i] - th[j]
                c, s = math.cos(d), math.sin(d)
                p[i] += v[i] * v[j] * (G[i, j] * c + B[i, j] * s)
                q[i] += v[i] * v[j] * (G[i, j] * s - B[i, j] * c)
                if i != j:
                    pth[i, j] = v[i] * v[j] * (G[i, j] * s - B[i, j] * c)
                    qth[i, j] = -v[i] * v[j] * (G[i, j] * c + B[i, j] * s)
                    pv[i, j] = v[i] * (G[i, j] * c + B[i, j] * s)
                    qv[i, j] = v[i] * (G[i, j] * s - B[i, j] * c)
        for i in range(n):
            pth[i, i] = -q[i] - B[i, i] * v[i] ** 2
            qth[i, i] = p[i] - G[i, i] * v[i] ** 2
            pv[i, i] = p[i] / v[i] + G[i, i] * v[i]
            qv[i, i] = q[i] / v[i] - B[i, i] * v[i]
        return p, q, pth, pv, qth, qv

    def unknowns(self):
        ang = [i for i in range(self.n) if i != self.slack]
        held = {self.slack} | {g['bus'] for g, m in zip(self.units, self.mode) if m == 'regulating'}
        mag = [i for i in range(self.n) if i not in held]
        return ang, mag

    def system(self, th, v, lam):
        """Residual of the balance equations, its Jacobian in the unknowns and its derivative in the loading."""
        ang, mag = self.unknowns()
        p, q, pth, pv, qth, qv = self.flows(th, v)
        ps, qs = self.specified(lam)
        r = np.concatenate([(p - ps)[ang], (q - qs)[mag]])
        J = np.block([[pth[np.ix_(ang, ang)], pv[np.ix_(ang, mag)]], [qth[np.ix_(mag, ang)], qv[np.ix_(mag, mag)]]])
        dps, dqs = np.zeros(self.n), np.zeros(self.n)
        for i, bus in enumerate(self.case['buses']):
            dps[i] -= bus['dpd']
            dqs[i] -= bus['dqd']
        for g in self.units:
            dps[g['bus']] += g['dpg']
        rl = np.concatenate([-dps[ang], -dqs[mag]])
        return r, J, rl

    def put(self, th, v, x):
        ang, mag = self.unknowns()
        th, v = th.copy(), v.copy()
        th[ang] = x[:len(ang)]
        v[mag] = x[len(ang):]
        return th, v

    def get(self, th, v):
        ang, mag = self.unknowns()
        return np.concatenate([th[ang], v[mag]])

    def solve(self, th, v, lam, iterations=25):
        x = self.get(th, v)
        for _ in range(iterations):
            th, v = self.put(th, v, x)
            r, J, _ = self.system(th, v, lam)
            if np.max(np.abs(r)) < TOL:
                return th, v
            try:
                dx = np.linalg.solve(J, -r)
            except np.linalg.LinAlgError:
                return None
            if not np.all(np.isfinite(dx)) or np.max(np.abs(dx)) > 0.3:
                return None
            x = x + dx
        return None

    def output(self, th, v, lam, k):
        """Reactive output of unit k and its gradient in the unknowns and in the loading."""
        ang, mag = self.unknowns()
        _, q, _, _, qth, qv = self.flows(th, v)
        i = self.units[k]['bus']
        bus = self.case['buses'][i]
        grad = np.concatenate([qth[i, ang], qv[i, mag]])
        return q[i] + bus['qd'] + lam * bus['dqd'], grad, bus['dqd']

    def violations(self, th, v, lam, slack=1e-11):
        out = []
        for k, (g, mode) in enumerate(zip(self.units, self.mode)):
            if mode == 'regulating':
                qg = self.output(th, v, lam, k)[0]
                if qg > g['qmax'] + slack:
                    out.append((k, 'max'))
                if qg < g['qmin'] - slack:
                    out.append((k, 'min'))
            elif mode == 'max' and v[g['bus']] > g['vset'] + slack:
                out.append((k, 'regulating'))
            elif mode == 'min' and v[g['bus']] < g['vset'] - slack:
                out.append((k, 'regulating'))
        return out

    def change_state(self, th, v, lam, k, target):
        """State on the present piece at which unit k meets the condition of the mode `target`."""
        ang, mag = self.unknowns()
        g = self.units[k]
        x = np.concatenate([self.get(th, v), [lam]])
        for _ in range(40):
            th, v = self.put(th, v, x[:-1])
            r, J, rl = self.system(th, v, x[-1])
            if target == 'regulating':
                e = v[g['bus']] - g['vset']
                grad = np.zeros(len(x))
                grad[len(ang) + mag.index(g['bus'])] = 1.0
            else:
                qg, gq, gl = self.output(th, v, x[-1], k)
                e = qg - (g['qmax'] if target == 'max' else g['qmin'])
                grad = np.concatenate([gq, [gl]])
            res = np.concatenate([r, [e]])
            if np.max(np.abs(res)) < TOL:
                return th, v, float(x[-1])
            A = np.vstack([np.hstack([J, rl[:, None]]), grad])
            x = x + np.linalg.solve(A, -res)
        raise RuntimeError('the state of a mode change did not converge')

    def continues(self, th, v, lam, k, came_from):
        """After unit k changed mode at this state: does the path continue to higher loadings on the new piece?"""
        ang, mag = self.unknowns()
        g = self.units[k]
        _, J, rl = self.system(th, v, lam)
        dx = np.linalg.solve(J, -rl)                      # sensitivity of the unknowns to the loading
        if self.mode[k] == 'max':
            return dx[len(ang) + mag.index(g['bus'])] < 0.0     # the magnitude must fall below the setpoint
        if self.mode[k] == 'min':
            return dx[len(ang) + mag.index(g['bus'])] > 0.0
        _, gq, gl = self.output(th, v, lam, k)
        rate = gq @ dx + gl                                # the reactive output must move inside the limits
        return rate < 0.0 if came_from == 'max' else rate > 0.0

    def fold(self, th, v, lam):
        """Smooth maximum of the loading on the present piece: balance equations and a null vector of their
        Jacobian, by Newton iteration (the derivative of the null-vector condition by central differences)."""
        ang, mag = self.unknowns()
        x = self.get(th, v)
        m = len(x)
        _, J, _ = self.system(th, v, lam)
        w = np.linalg.svd(J)[2][-1]
        pivot = int(np.argmax(np.abs(w)))
        w = w / w[pivot]
        y = np.concatenate([x, [lam], w])

        def equations(y):
            t2, v2 = self.put(th, v, y[:m])
            r, J, rl = self.system(t2, v2, y[m])
            return np.concatenate([r, J @ y[m + 1:], [y[m + 1 + pivot] - 1.0]]), J, rl

        for _ in range(60):
            res, J, rl = equations(y)
            if np.max(np.abs(res)) < 1e-11:
                t2, v2 = self.put(th, v, y[:m])
                return t2, v2, float(y[m])
            A = np.zeros((2 * m + 1, 2 * m + 1))
            A[:m, :m] = J
            A[:m, m] = rl
            A[m:2 * m, m + 1:] = J
            A[2 * m, m + 1 + pivot] = 1.0
            h = 1e-6
            for c in range(m):
                e = np.zeros(2 * m + 1)
                e[c] = h
                A[m:2 * m, c] = (equations(y + e)[0][m:2 * m] - equations(y - e)[0][m:2 * m]) / (2 * h)
            step = np.linalg.solve(A, -res)
            scale = min(1.0, 0.2 / max(np.max(np.abs(step[:m + 1])), 1e-300))
            y = y + scale * step
        raise RuntimeError('the point-of-collapse equations did not converge')


def collapse(case, trace=None):
    model = Model(case)
    n = model.n
    th = np.radians([b['angle_base_deg'] for b in case['buses']])
    v = np.array([b['voltage_base_pu'] for b in case['buses']], dtype=float)
    v[model.slack] = model.vslack
    th[model.slack] = 0.0
    for g, mode in zip(model.units, model.mode):
        if mode == 'regulating':
            v[g['bus']] = g['vset']
    lam = 0.0
    th, v = model.solve(th, v, lam, iterations=60)
    step = 0.02
    for _ in range(200000):
        trial = model.solve(th, v, lam + step)
        if trial is None and step > 2e-4:
            step *= 0.5
            continue
        if trial is not None:
            bad = model.violations(trial[0], trial[1], lam + step)
            if not bad:
                th, v, lam = trial[0], trial[1], lam + step
                step = min(0.02, 1.5 * step)
                continue
        else:
            # the increment is small and the iteration still fails: the loading is close to a smooth maximum
            ft, fv, fl = model.fold(th, v, lam)
            bad = model.violations(ft, fv, fl)
            if not bad:
                return finish(fv, fl, 'fold')
        # at least one generator changes mode between the present state and the trial state
        best = None
        for k, target in bad:
            ct, cv, cl = model.change_state(th, v, lam, k, target)
            if cl >= lam - 1e-12 and (best is None or cl < best[2]):
                best = (ct, cv, cl, k, target)
        if best is None:
            raise RuntimeError('no admissible mode change was found')
        th, v, lam, k, target = best
        came_from = model.mode[k]
        model.mode[k] = target
        v[model.units[k]['bus']] = model.units[k]['vset']     # both conditions of the unit hold at this state
        if trace is not None:
            trace.append((k, target, lam))
        if not model.continues(th, v, lam, k, came_from):
            return finish(v, lam, 'limit')
        # leave the state of the change by a short step so that the released quantity is strictly admissible
        nudge = 1e-7
        moved = model.solve(th, v, lam + nudge)
        if moved is None:
            ft, fv, fl = model.fold(th, v, lam)
            return finish(fv, fl, 'fold')
        th, v, lam = moved[0], moved[1], lam + nudge
        step = min(step, 0.005)
    raise RuntimeError('no collapse state was found')


def finish(v, lam, kind):
    return {'collapse_loading': float(lam), 'bus_voltage_pu': [float(x) for x in v], 'collapse_kind': kind}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    case = json.loads((Path(args.data) / 'case.json').read_text(encoding='utf-8'))
    Path(args.output).write_text(json.dumps(collapse(case), indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
