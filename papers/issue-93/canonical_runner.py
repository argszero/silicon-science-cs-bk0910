#!/usr/bin/env python3
"""
Issue #93 canonical runner (self-contained).
Regenerates every number reported in the manuscript; deterministic; stdlib.
Panels: P0 open-loop equilibrium / P1 single-class / P2 three regimes /
P3 boundary curve Nc*(Nl) / P4 2D field / P5 service ablation /
P6 plateau law / P7 Tc-independence / P8 buffer-independence / P9 robustness.
Core model: dual-class mean-field fluid, FIFO arrival-share backlog, dualQ PI.
"""
import json, math, os, time
C   = 10000.0
TAU = 0.05
T_C = C * 0.015   # classic virtual target (15 ms -> 150 pkts)
T_L = C * 0.001   # L4S virtual target (1 ms -> 10 pkts)
B   = C * TAU * 5.0
DT  = 2e-4
T_RUN = 30.0
T_SETTLE = 10.0
PMIN, PMAX = 0.0, 0.5
KPP_C, KPI_C = 1e-3, 0.20
KPP_L, KPI_L = 5e-3, 0.30

def clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)

def deriv(st, N_c, N_l, p_c_fixed, p_l_fixed, g):
    W_c, W_l, q_c, q_l, I_c, I_l = st
    q_tot = q_c + q_l
    R = TAU + q_tot / C
    x_c = N_c * W_c / R
    x_l = N_l * W_l / R
    X = x_c + x_l
    p_drop = max(0.0, X - C) / X if X > 0 else 0.0
    # FIFO per-class backlog dynamics
    if X >= C and X > 0:
        dq_c = x_c * (1.0 - C / X)
        dq_l = x_l * (1.0 - C / X)
    elif q_tot > 0:
        extra = C - X
        dq_c = -extra * q_c / q_tot
        dq_l = -extra * q_l / q_tot
    else:
        dq_c = 0.0
        dq_l = 0.0
    dq_c = dq_c if (q_c > 0 or dq_c > 0) else 0.0
    dq_l = dq_l if (q_l > 0 or dq_l > 0) else 0.0
    e_c = q_c - T_C
    e_l = q_l - T_L
    if p_c_fixed is not None:
        p_c = p_c_fixed; dI_c = 0.0
    else:
        l4s_press = clamp(KPI_L * I_l, 0.0, PMAX)   # RFC9332: L4S sustained pressure
        p_c = clamp(KPP_C * e_c + KPI_C * I_c + g * l4s_press, PMIN, PMAX)
        dI_c = 0.0 if ((p_c >= PMAX and e_c > 0.0) or (p_c <= PMIN and e_c < 0.0)) else e_c
    if p_l_fixed is not None:
        p_l = p_l_fixed; dI_l = 0.0
    else:
        p_l = clamp(KPP_L * e_l + KPI_L * I_l, PMIN, PMAX)
        dI_l = 0.0 if ((p_l >= PMAX and e_l > 0.0) or (p_l <= PMIN and e_l < 0.0)) else e_l
    p_c_tot = p_c + p_drop - p_c * p_drop
    p_l_tot = p_l + p_drop - p_l * p_drop
    if N_c > 0:
        dW_c = (1.0 - p_c_tot * W_c * W_c / 2.0) / R
    else:
        dW_c = 0.0
    if N_l > 0:
        dW_l = (1.0 - p_l_tot * W_l / 2.0) / R
    else:
        dW_l = 0.0
    return (dW_c, dW_l, dq_c, dq_l, dI_c, dI_l, p_drop)

def step_rk4(st, N_c, N_l, p_c_fixed, p_l_fixed, g, dt=DT):
    k1 = deriv(st, N_c, N_l, p_c_fixed, p_l_fixed, g)
    mid = tuple(s + 0.5 * dt * k for s, k in zip(st, k1))
    k2 = deriv(mid, N_c, N_l, p_c_fixed, p_l_fixed, g)
    mid = tuple(s + 0.5 * dt * k for s, k in zip(st, k2))
    k3 = deriv(mid, N_c, N_l, p_c_fixed, p_l_fixed, g)
    end = tuple(s + dt * k for s, k in zip(st, k3))
    k4 = deriv(end, N_c, N_l, p_c_fixed, p_l_fixed, g)
    out = []
    for s, k1_, k2_, k3_, k4_ in zip(st, k1, k2, k3, k4):
        s2 = s + dt * (k1_ + 2 * k2_ + 2 * k3_ + k4_) / 6.0
        out.append(max(0.0, s2))
    return tuple(out)

def run(N_c, N_l, p_c_fixed=None, p_l_fixed=None, g=1.0, name='',
        T_RUN_=None, T_SETTLE_=None):
    T_RUN_l = T_RUN if T_RUN_ is None else T_RUN_
    T_SET_l = T_SETTLE if T_SETTLE_ is None else T_SETTLE_
    W0_c = max(1.0, (C * TAU) / max(1, N_c))
    W0_l = max(1.0, (C * TAU) / max(1, N_l))
    st = (W0_c, W0_l, 0.0, 0.0, 0.0, 0.0)
    n = int(T_RUN_l / DT)
    ns = int(T_SET_l / DT)
    acc = {'W_c': 0.0, 'W_l': 0.0, 'q_c': 0.0, 'q_l': 0.0, 'x_c': 0.0, 'x_l': 0.0,
           'q': 0.0, 'd_l_ms': 0.0, 'p_drop': 0.0}
    drop_total = 0.0
    max_q = 0.0
    q_hist = []
    cnt = 0
    for i in range(n):
        st = step_rk4(st, N_c, N_l, p_c_fixed, p_l_fixed, g)
        W_c, W_l, q_c, q_l, I_c, I_l = st
        q_tot = q_c + q_l
        if q_tot > B:
            excess = q_tot - B
            drop_total += excess
            if q_c > 0 and q_l > 0:
                share = q_c / q_tot
                q_c = max(0.0, q_c - excess * share)
                q_l = max(0.0, q_l - excess * (1.0 - share))
            elif q_c > 0:
                q_c = max(0.0, q_c - excess)
            else:
                q_l = max(0.0, q_l - excess)
            st = (W_c, W_l, q_c, q_l, I_c, I_l)
            q_tot = B
        max_q = max(max_q, q_tot)
        if i >= ns:
            R = TAU + q_tot / C
            x_c = N_c * W_c / R
            x_l = N_l * W_l / R
            X = x_c + x_l
            acc['W_c'] += W_c; acc['W_l'] += W_l
            acc['q_c'] += q_c; acc['q_l'] += q_l
            acc['x_c'] += x_c; acc['x_l'] += x_l
            acc['q'] += q_tot
            acc['d_l_ms'] += (q_tot / C) * 1000.0
            acc['p_drop'] += (max(0.0, X - C) / X if X > 0 else 0.0)
            q_hist.append((q_tot / C) * 1000.0)
            cnt += 1
    nq = len(q_hist)
    q_hist_s = sorted(q_hist)
    out = {k: v / cnt for k, v in acc.items()}
    out['drop_total_pkts'] = drop_total
    out['max_q_pkts'] = max_q
    out['p99_d_ms'] = q_hist_s[int(nq * 0.99)] if nq else float('nan')
    out['p50_d_ms'] = q_hist_s[int(nq * 0.50)] if nq else float('nan')
    out['util'] = (out['x_c'] + out['x_l']) / C
    return out

def check_openloop():
    """A. textbook equilibria at fixed mark prob (no AQM; N sized so x* < C)."""
    res = {}
    cells = [('classic_p1e-3', 8, 1e-3, 'c', 60.0, 58.0),
             ('classic_p1e-2', 8, 1e-2, 'c', 60.0, 58.0),
             ('scalable_p1e-2', 2, 1e-2, 'l', 120.0, 118.0),
             ('scalable_p1e-1', 12, 1e-1, 'l', 60.0, 58.0)]
    for tag, N, p, mode, T, Ts in cells:
        pc = p if mode == 'c' else None
        pl = p if mode == 'l' else None
        st = run(N if mode == 'c' else 0, N if mode == 'l' else 0,
                 p_c_fixed=pc, p_l_fixed=pl, g=0.0, name=tag, T_RUN_=T, T_SETTLE_=Ts)
        W_meas = st['W_c'] if mode == 'c' else st['W_l']
        W_pred = math.sqrt(2.0 / p) if mode == 'c' else 2.0 / p
        rel = abs(W_meas - W_pred) / W_pred
        res[tag] = {'W_meas': W_meas, 'W_pred': W_pred, 'rel_err': rel,
                    'p': p, 'N': N, 'pass': rel < 0.05}
    return res

def measure_boundary(N_l, pmax=None, tc_ms=None, bh=None, g=0.0, ncs=None):
    global PMAX, T_C, B
    _save = (PMAX, T_C, B)
    ncs = ncs if ncs is not None else NCS
    if pmax is not None:
        PMAX = pmax
    if tc_ms is not None:
        T_C = C * tc_ms / 1000.0
    if bh is not None:
        B = bh * C * TAU
    ds = [run(nc, N_l, g=g)['d_l_ms'] for nc in ncs]
    bd = boundary_nc(ncs, ds)
    PMAX, T_C, B = _save
    return bd, ds

def boundary_nc(ncs, ds):
    prev = None
    for nc, d in zip(ncs, ds):
        if prev is not None:
            d0, nc0 = prev
            if (d0 <= T_ISO < d) or (d > T_ISO >= d0):
                f = (T_ISO - d0) / (d - d0) if d != d0 else 0.5
                return nc0 + f * (nc - nc0)
        if d > T_ISO and prev is None:
            return None
        prev = (d, nc)
    return None

T_ISO = 5.0
NCS = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 25, 30, 40, 60, 80, 100]

def run_dt(N_c, N_l, g, dt, t0s=10.0, t1s=30.0, bh=5.0):
    B_ = bh * C * TAU
    W0_c = max(1.0, (C * TAU) / max(1, N_c))
    W0_l = max(1.0, (C * TAU) / max(1, N_l))
    st = (W0_c, W0_l, 0.0, 0.0, 0.0, 0.0)
    n = int(t1s / dt); ns = int(t0s / dt)
    acc = 0.0; cnt = 0
    for i in range(n):
        st = step_rk4(st, N_c, N_l, None, None, g, dt=dt)
        q_tot = st[2] + st[3]
        if q_tot > B_:
            excess = q_tot - B_
            share = st[2] / q_tot if q_tot > 0 else 0.5
            st = (st[0], st[1], max(0.0, st[2] - excess * share),
                  max(0.0, st[3] - excess * (1 - share)), st[4], st[5])
            q_tot = B_
        if i >= ns:
            acc += (q_tot / C) * 1000.0; cnt += 1
    return acc / cnt

def run_ic(N_c, N_l, g, w0_scale):
    W0_c = max(1.0, (C * TAU) / max(1, N_c)) * w0_scale
    W0_l = max(1.0, (C * TAU) / max(1, N_l)) * w0_scale
    st = (W0_c, W0_l, 0.0, 0.0, 0.0, 0.0)
    n = int(T_RUN / DT); ns = int(25.0 / DT)
    acc = 0.0; cnt = 0
    for i in range(n):
        st = step_rk4(st, N_c, N_l, None, None, g)
        q_tot = st[2] + st[3]
        if q_tot > B:
            excess = q_tot - B
            share = st[2] / q_tot if q_tot > 0 else 0.5
            st = (st[0], st[1], max(0.0, st[2] - excess * share),
                  max(0.0, st[3] - excess * (1 - share)), st[4], st[5])
            q_tot = B
        if i >= ns:
            acc += (q_tot / C) * 1000.0; cnt += 1
    return acc / cnt

def main():
    global T_C, B
    t0 = time.time()
    R = {'meta': {'model': 'mean-field 2-class fluid (AIMD classic + DCTCP-class scalable) '
                 'shared FIFO; dualQ PI marking + RFC9332 integral coupling g; overflow '
                 'drops = marks; delay = q_tot/C for both classes',
                 'C_pkt_s': C, 'TAU_s': TAU, 'T_L_ms': 1.0, 'dt': DT, 'T_run_s': T_RUN,
                 'T_settle_s': T_SETTLE, 'script': 'canonical_runner.py',
                 'deterministic': True}}
    # P0 open-loop equilibrium anchors
    R['P0_openloop'] = check_openloop()
    # P1 single-class closed loops
    R['P1_single'] = {'classic_only': run(10, 0, g=0.0), 'l4s_only': run(0, 20, g=1.0)}
    # P2 three-regime rows (N_l=20)
    R['P2_regimes'] = {}
    for nc in (5, 10, 20, 40, 80, 160):
        for g in (0.0, 1.0):
            r = run(nc, 20, g=g)
            R['P2_regimes']['Nc%d_g%d' % (nc, int(g))] = {
                'd_l_ms': r['d_l_ms'], 'q_c': r['q_c'], 'q_l': r['q_l'],
                'util': r['util'], 'drops': r['drop_total_pkts']}
    # P3 boundary curve N_c*(N_l) g=0
    R['P3_boundary'] = {}
    for N_l in (5, 10, 15, 20, 25, 30, 35, 40, 50, 60, 80, 100):
        bd, ds = measure_boundary(N_l)
        R['P3_boundary'][str(N_l)] = {'Nc_star': bd, 'd_row': ds}
    # P4 2D field (figure data)
    R['P4_field'] = {}
    NCS2 = [2, 5, 8, 10, 12, 15, 20, 30, 40, 60]
    NLS2 = [5, 10, 20, 40, 80]
    for g in (0.0, 1.0):
        mat = []
        for N_l in NLS2:
            mat.append([round(run(nc, N_l, g=g)['d_l_ms'], 4) for nc in NCS2])
        R['P4_field'][str(int(g))] = {'NCS': NCS2, 'NLS': NLS2, 'delay_ms': mat}
    # P5 service ablation (shared vs per-class delay; same runs)
    R['P5_ablation'] = {}
    for nc in (10, 12, 20, 40, 80):
        r = run(nc, 20, g=0.0)
        R['P5_ablation']['Nc%d' % nc] = {'d_shared_ms': r['d_l_ms'],
                                          'd_own_ms': r['q_l'] / C * 1000.0,
                                          'q_c': r['q_c'], 'q_l': r['q_l']}
    # P6 plateau law incl T_C=30
    R['P6_plateau'] = {}
    for tc in (15.0, 30.0):
        T_C = C * tc / 1000.0
        for N_l in (20, 40):
            r = run(40, N_l, g=0.0)
            R['P6_plateau']['TC%d_Nl%d' % (int(tc), N_l)] = {
                'd_meas': r['d_l_ms'], 'q_l': r['q_l'],
                'pred': (T_C + r['q_l']) / C * 1000.0}
    T_C = C * 0.015
    # P7 T_C-independence of boundary (N_l=20)
    bd30, _ = measure_boundary(20, tc_ms=30.0)
    R['P7_Tc_boundary'] = {'Nc_star_TC15': measure_boundary(20)[0], 'Nc_star_TC30': bd30}
    # P8 buffer independence of boundary (N_l=20)
    bd_b1, _ = measure_boundary(20, bh=1.0)
    bd_b10, _ = measure_boundary(20, bh=10.0)
    R['P8_buffer_boundary'] = {'Bh1': bd_b1, 'Bh5': measure_boundary(20, bh=5.0)[0], 'Bh10': bd_b10}
    # P9 robustness: dt convergence + IC late-window
    R['P9_robust'] = {}
    for nc in (5, 11, 40):
        d1 = run_dt(nc, 20, 0.0, 2e-4)
        d2 = run_dt(nc, 20, 0.0, 1e-4)
        R['P9_robust']['dt_Nc%d' % nc] = {'d_2e-4': d1, 'd_1e-4': d2,
                                           'pct_change': abs(d2 - d1) / d1 * 100.0}
    for nc in (5, 40):
        s05 = run_ic(nc, 20, 0.0, 0.5)
        s10 = run_ic(nc, 20, 0.0, 1.0)
        s20 = run_ic(nc, 20, 0.0, 2.0)
        R['P9_robust']['ic_Nc%d' % nc] = {'d_0_5x': s05, 'd_1x': s10, 'd_2x': s20,
                                           'spread_pct': max(abs(s05 - s10) / s10 * 100.0,
                                                             abs(s20 - s10) / s10 * 100.0)}
    R['runtime_s'] = round(time.time() - t0, 1)
    return R

if __name__ == '__main__':
    import json
    results = main()
    results.pop('runtime_s', None)  # runtime is not part of the deterministic artifact
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'canonical_results.json')
    with open(out, 'w') as f:
        json.dump(results, f, indent=1, sort_keys=True)
    print('wrote', out, '| sha256:')
    import hashlib
    print(hashlib.sha256(open(out, 'rb').read()).hexdigest())
