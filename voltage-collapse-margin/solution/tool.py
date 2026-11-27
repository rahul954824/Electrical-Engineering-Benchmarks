#!/usr/bin/env python3
"""Collapse loading of a transmission network with reactive-power limits of its generators (SPEC.md).

Method. The states of SPEC.md section 1.4 form a piecewise smooth curve in the space (angles, magnitudes,
loading). On a smooth piece every generator has one of three modes: it regulates (magnitude at the setpoint, the
reactive output free), or it sits at its upper or its lower reactive limit (output fixed, magnitude free). For a
fixed set of modes the curve is the solution set of the power-balance equations, one equation fewer than unknowns,
and it is followed by pseudo-arclength continuation: a step along the tangent and a Newton correction in the
plane normal to it. Along a step these quantities are watched:

  * for a regulating generator, the distance of its reactive output from either limit;
  * for a generator at a limit, the distance of its magnitude from the setpoint, on the admissible side;
  * the loading component of the tangent.

The first of them to reach zero inside a step is located by root finding on the step length. If it is the
loading component of the tangent, the loading has a smooth maximum there and that state is the collapse state
(`fold`). Otherwise a generator changes mode there. The curve continues on the piece of the new mode in the
direction that keeps the generator admissible (magnitude leaving the setpoint to the admissible side, or
reactive output leaving the limit inwards); if the loading decreases in that direction, no state continues the
path to a higher loading and the state of the mode change is the collapse state (`limit`).
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

STEP_MAX = 0.04        # longest step along the curve (rad, p.u. and loading units taken together)
STEP_MIN = 1e-10
NEWTON_TOL = 1e-12
ROOT_XTOL = 1e-14


class Network:
    def __init__(self, case):
        buses, branches, gens = case['buses'], case['branches'], case['generators']
        n = len(buses)
        self.n = n
        Y = np.zeros((n, n), dtype=complex)
        for br in branches:
            f, t = br['from'], br['to']
            y = 1.0 / complex(br['r'], br['x'])
            half = 0.5j * br['b']
            a = br['tap']
            Y[f, f] += (y + half) / (a * a)
            Y[t, t] += y + half
            Y[f, t] -= y / a
            Y[t, f] -= y / a
        for i, b in enumerate(buses):
            Y[i, i] += complex(b['gs'], b['bs'])
        self.Y = Y
        self.pd = np.array([b['pd'] for b in buses])
        self.qd = np.array([b['qd'] for b in buses])
        self.dpd = np.array([b['dpd'] for b in buses])
        self.dqd = np.array([b['dqd'] for b in buses])
        self.pg = np.zeros(n)
        self.dpg = np.zeros(n)
        self.gens = []
        self.slack = None
        self.v_fixed = {}
        for g in gens:
            i = g['bus']
            if g['slack']:
                self.slack = i
                self.v_slack = g['vset']
            else:
                self.pg[i] = g['pg']
                self.dpg[i] = g['dpg']
                self.gens.append(dict(bus=i, vset=g['vset'], qmin=g['qmin'], qmax=g['qmax'], mode=g['mode_base']))
        self.th0 = np.radians([b['angle_base_deg'] for b in buses])
        self.v0 = np.array([b['voltage_base_pu'] for b in buses])

    # -- layout of the unknowns for the present modes
    def layout(self):
        th_idx = [i for i in range(self.n) if i != self.slack]
        held = {self.slack} | {g['bus'] for g in self.gens if g['mode'] == 'regulating'}
        v_idx = [i for i in range(self.n) if i not in held]
        qg = np.zeros(self.n)
        for g in self.gens:
            if g['mode'] == 'max':
                qg[g['bus']] = g['qmax']
            elif g['mode'] == 'min':
                qg[g['bus']] = g['qmin']
        return th_idx, v_idx, qg

    def injections(self, th, v):
        vc = v * np.exp(1j * th)
        return vc * np.conj(self.Y @ vc)

    def residual_and_jacobian(self, th, v, lam, lay):
        th_idx, v_idx, qg = lay
        vc = v * np.exp(1j * th)
        cur = self.Y @ vc
        s = vc * np.conj(cur)
        fp = s.real - (self.pg + lam * self.dpg - self.pd - lam * self.dpd)
        fq = s.imag - (qg - self.qd - lam * self.dqd)
        ds_dth = 1j * np.diag(vc) @ np.conj(np.diag(cur) - self.Y @ np.diag(vc))
        unit = vc / v
        ds_dv = np.diag(vc) @ np.conj(self.Y @ np.diag(unit)) + np.diag(np.conj(cur)) @ np.diag(unit)
        F = np.concatenate([fp[th_idx], fq[v_idx]])
        J = np.zeros((len(F), len(F) + 1))
        nt = len(th_idx)
        J[:nt, :nt] = ds_dth.real[np.ix_(th_idx, th_idx)]
        J[:nt, nt:-1] = ds_dv.real[np.ix_(th_idx, v_idx)]
        J[nt:, :nt] = ds_dth.imag[np.ix_(v_idx, th_idx)]
        J[nt:, nt:-1] = ds_dv.imag[np.ix_(v_idx, v_idx)]
        J[:nt, -1] = -(self.dpg - self.dpd)[th_idx]
        J[nt:, -1] = self.dqd[v_idx]
        return F, J


class Curve:
    """The smooth piece of the present modes, in the unknowns z = (angles, free magnitudes, loading)."""

    def __init__(self, net, th, v):
        self.net = net
        self.th = th.copy()
        self.v = v.copy()
        self.lay = net.layout()
        for g in net.gens:
            if g['mode'] == 'regulating':
                self.v[g['bus']] = g['vset']
        self.v[net.slack] = net.v_slack
        self.th[net.slack] = 0.0

    def pack(self, lam):
        th_idx, v_idx, _ = self.lay
        return np.concatenate([self.th[th_idx], self.v[v_idx], [lam]])

    def unpack(self, z):
        th_idx, v_idx, _ = self.lay
        th, v = self.th.copy(), self.v.copy()
        th[th_idx] = z[:len(th_idx)]
        v[v_idx] = z[len(th_idx):-1]
        return th, v, z[-1]

    def fj(self, z):
        th, v, lam = self.unpack(z)
        return self.net.residual_and_jacobian(th, v, lam, self.lay)

    def tangent(self, z, along):
        """Unit tangent of the curve at z with a positive component along the vector `along`."""
        _, J = self.fj(z)
        A = np.vstack([J, along])
        rhs = np.zeros(len(z))
        rhs[-1] = 1.0
        t = np.linalg.solve(A, rhs)
        return t / np.linalg.norm(t)

    def null_vector(self, z):
        _, J = self.fj(z)
        _, _, vt = np.linalg.svd(J)
        return vt[-1]

    def correct(self, z_pred, t):
        """Newton iteration for the point of the curve in the plane through z_pred normal to t."""
        z = z_pred.copy()
        for _ in range(30):
            F, J = self.fj(z)
            G = np.concatenate([F, [t @ (z - z_pred)]])
            if np.max(np.abs(G)) < NEWTON_TOL:
                return z
            dz = np.linalg.solve(np.vstack([J, t]), -G)
            if not np.all(np.isfinite(dz)) or np.max(np.abs(dz)) > 0.5:
                return None
            z = z + dz
        return None

    def reactive_output(self, z, g):
        th, v, lam = self.unpack(z)
        i = g['bus']
        return self.net.injections(th, v)[i].imag + self.net.qd[i] + lam * self.net.dqd[i]

    def watch(self, z, t_ref):
        """Watched quantities, each positive while the state is admissible and the loading rises."""
        th, v, lam = self.unpack(z)
        out = []
        for k, g in enumerate(self.net.gens):
            if g['mode'] == 'regulating':
                q = self.reactive_output(z, g)
                out.append((('to_max', k), g['qmax'] - q))
                out.append((('to_min', k), q - g['qmin']))
            elif g['mode'] == 'max':
                out.append((('release', k), g['vset'] - v[g['bus']]))
            else:
                out.append((('release', k), v[g['bus']] - g['vset']))
        out.append((('fold', -1), self.tangent(z, t_ref)[-1]))
        return dict(out)


def solve_base(net):
    """The base state: Newton iteration at zero loading from the listed (rounded) base state."""
    curve = Curve(net, net.th0, net.v0)
    z = curve.pack(0.0)
    for _ in range(50):
        F, J = curve.fj(z)
        if np.max(np.abs(F)) < NEWTON_TOL:
            break
        z[:-1] += np.linalg.solve(J[:, :-1], -F)
    else:
        raise RuntimeError('the base state did not converge')
    return curve, z


def collapse(case, trace=None):
    net = Network(case)
    curve, z = solve_base(net)
    e_lam = np.zeros(len(z))
    e_lam[-1] = 1.0
    t = curve.tangent(z, e_lam)
    h = 0.01
    fresh = None          # the watched quantity that is zero at z because a generator has just changed mode there
    for _ in range(20000):
        w0 = curve.watch(z, t)
        z1 = curve.correct(z + h * t, t)
        if z1 is None:
            h *= 0.5
            if h < STEP_MIN:
                raise RuntimeError('the continuation step failed')
            continue
        w1 = curve.watch(z1, t)
        crossed = [key for key, value in w1.items() if value < 0.0 and key != fresh and w0[key] > 0.0]
        stale = [key for key, value in w1.items() if value < 0.0 and key not in crossed]
        if stale:             # a quantity that starts at zero must rise: a shorter step separates the events
            h *= 0.5
            if h < STEP_MIN:
                raise RuntimeError('a watched quantity is negative at the start of a step')
            continue
        if not crossed:
            t = curve.tangent(z1, t)
            z = z1
            fresh = None
            h = min(STEP_MAX, 1.5 * h)
            continue

        def point(step):
            zz = curve.correct(z + step * t, t)
            if zz is None:
                raise RuntimeError('the correction failed while an event was located')
            return zz

        first_key, first_h = None, None
        for key in crossed:
            root = brentq(lambda step, key=key: curve.watch(point(step), t)[key], 0.0, h, xtol=ROOT_XTOL, rtol=1e-15)
            if first_h is None or root < first_h:
                first_key, first_h = key, root
        z = point(first_h)
        kind, k = first_key
        if trace is not None:
            trace.append((kind, k, float(z[-1])))
        if kind == 'fold':
            return finish(curve, z, 'fold')
        g = net.gens[k]
        th, v, lam = curve.unpack(z)
        if kind == 'to_max':
            g['mode'] = 'max'
        elif kind == 'to_min':
            g['mode'] = 'min'
        else:
            was = g['mode']
            g['mode'] = 'regulating'
        new = Curve(net, th, v)
        z = new.pack(lam)
        t_new = new.null_vector(z)
        if kind in ('to_max', 'to_min'):
            # the magnitude of the generator leaves the setpoint downwards (upper limit) or upwards (lower limit)
            pos = len(new.lay[0]) + new.lay[1].index(g['bus'])
            rate = t_new[pos] if kind == 'to_min' else -t_new[pos]
            fresh = ('release', k)
        else:
            # the reactive output leaves the limit inwards
            eps = 1e-6
            dq = (new.reactive_output(z + eps * t_new, g) - new.reactive_output(z - eps * t_new, g)) / (2 * eps)
            rate = -dq if was == 'max' else dq
            fresh = ('to_max', k) if was == 'max' else ('to_min', k)
        if rate < 0.0:
            t_new = -t_new
        curve = new
        if t_new[-1] < 0.0:
            return finish(curve, z, 'limit')
        t = t_new
        h = min(h, 0.01)
    raise RuntimeError('no collapse state was found')


def finish(curve, z, kind):
    th, v, lam = curve.unpack(z)
    return {'collapse_loading': float(lam), 'bus_voltage_pu': [float(x) for x in v], 'collapse_kind': kind}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    case = json.loads((Path(args.data) / 'case.json').read_text(encoding='utf-8'))
    report = collapse(case)
    Path(args.output).write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
