"""stimulus.py -- PRBS7, PWL writers, triangle ramp and clock pattern (handoff 9.5).

All times in seconds, all voltages in volts.  Functions return plain Python lists / strings, so
they can be unit-tested without ngspice.  `write_pwl_source` and `write_diff_prbs` emit an
ngspice include file with continuation lines (no giant single line).
"""


def prbs7(n, seed=0x7F):
    """PRBS7, x^7 + x^6 + 1, 127-bit period.  Returns a list of n bits (0/1)."""
    if seed & 0x7F == 0:
        raise ValueError("PRBS seed must be non-zero")
    s = seed & 0x7F
    out = []
    for _ in range(n):
        b = ((s >> 6) ^ (s >> 5)) & 1
        s = ((s << 1) | b) & 0x7F
        out.append(b)
    return out


def pwl_points(bits, ui, tr, vhi, vlo, t0=5e-9):
    """Return (t, v) lists for a bit sequence: bit i starts at t0 + i*ui, linear edge of
    duration tr (10-90 % is 0.8*tr for a linear ramp).  The first bit is the initial level."""
    if tr >= ui:
        raise ValueError("rise time tr must be shorter than the unit interval")
    t = [0.0]
    v = [vhi if bits[0] else vlo]
    for i, b in enumerate(bits):
        lvl = vhi if b else vlo
        if lvl != v[-1]:
            tt = t0 + i * ui
            t += [tt, tt + tr]
            v += [v[-1], lvl]
    return t, v


def pwl_string(t, v, per_line=4):
    """'t v t v ...' text with ngspice continuation lines."""
    pairs = ["%.6e %.6f" % (a, b) for a, b in zip(t, v)]
    lines = [" ".join(pairs[i:i + per_line]) for i in range(0, len(pairs), per_line)]
    return "\n+ ".join(lines)


def diff_prbs(bits, ui, tr, vos, vod, t0=5e-9):
    """Complementary P/N PWL point lists around common mode vos with differential amplitude
    vod (= VP - VN when bit=1: P = vos + vod/2, N = vos - vod/2)."""
    tp, vp = pwl_points(bits, ui, tr, vos + vod / 2.0, vos - vod / 2.0, t0)
    tn, vn = pwl_points(bits, ui, tr, vos - vod / 2.0, vos + vod / 2.0, t0)
    return (tp, vp), (tn, vn)


def write_pwl_source(path, name, node_p, node_m, t, v, per_line=4):
    """Write 'Vname node_p node_m PWL( ... )' to path.  Returns the text."""
    text = "V%s %s %s PWL(\n+ %s)\n" % (name, node_p, node_m, pwl_string(t, v, per_line))
    with open(path, "w") as f:
        f.write(text)
    return text


def diff_prbs_text(bits, ui, tr, vos, vod, t0=5e-9, nodes=("inp", "inn"), names=("P", "N")):
    (tp, vp), (tn, vn) = diff_prbs(bits, ui, tr, vos, vod, t0)
    return ("V%s %s 0 PWL(\n+ %s)\nV%s %s 0 PWL(\n+ %s)\n"
            % (names[0], nodes[0], pwl_string(tp, vp), names[1], nodes[1], pwl_string(tn, vn)))


def write_diff_prbs(path, bits, ui, tr, vos, vod, t0=5e-9, nodes=("inp", "inn"), names=("P", "N")):
    """Include file with two sources, VP and VN, driving nodes[0], nodes[1] to ground."""
    text = diff_prbs_text(bits, ui, tr, vos, vod, t0, nodes, names)
    with open(path, "w") as f:
        f.write(text)
    return text


def triangle(vlo, vhi, period, ncycles=1, t0=0.0, start_low=True):
    """Triangle wave (t, v) points: vlo -> vhi -> vlo per period (slow sweep for hysteresis).
    ngspice PWL is held at the last value after the last point."""
    t, v = [], []
    a, b = (vlo, vhi) if start_low else (vhi, vlo)
    for c in range(ncycles):
        base = t0 + c * period
        t += [base, base + period / 2.0]
        v += [a, b]
    t.append(t0 + ncycles * period)
    v.append(a)
    return t, v


def clock_pwl(period, vlo, vhi, tr, tf=None, duty=0.5, ncycles=10, t0=0.0, delay=0.0):
    """Clock (t, v) points; high time = duty*period measured edge-centre to edge-centre."""
    tf = tr if tf is None else tf
    th = duty * period
    t = [0.0]
    v = [vlo]
    for c in range(ncycles):
        r = t0 + delay + c * period
        t += [r, r + tr, r + th, r + th + tf]
        v += [vlo, vhi, vhi, vlo]
    return t, v


def clock_source_line(name, node, vlo, vhi, period, tr, tf=None, duty=0.5, delay=0.0):
    """One-line ngspice PULSE clock:  V<name> node 0 PULSE(...)  (width = high plateau)."""
    tf = tr if tf is None else tf
    width = duty * period - 0.5 * (tr + tf)
    if width <= 0:
        raise ValueError("clock edges longer than the high time")
    return "V%s %s 0 PULSE(%g %g %g %g %g %g %g)" % (name, node, vlo, vhi, delay, tr, tf, width, period)
