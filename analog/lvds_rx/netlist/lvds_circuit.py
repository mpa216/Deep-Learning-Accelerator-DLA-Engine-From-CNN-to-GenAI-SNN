"""lvds_circuit.py -- the connectivity of lvds_rx_x3, written ONCE, emitted twice:

    emit_sim()   -> netlist/lvds_rx_core.spice   (simulation netlist: W/L/nf/R come from the parameters of sizing/sizes.spice)
    emit_lvs()   -> netlist/lvds_rx_lvs_ref.spice (LVS reference: numeric values read from layout/device_table.json, gf180mcuD names)

Sizes never appear here: every device names a `stem`, and the sizing script writes `w_<stem> l_<stem> nf_<stem>` (devices) or
`rw_<stem> rl_<stem>` (poly resistors).  Matched devices are ONE device with nf fingers (never m).

Item formats (all nets are lowercase names; ports of a subckt are listed in `SUBCKTS`):
    ('n'|'p', inst, d, g, s, b, stem, cond)       MOS, model nfet_03v3 / pfet_03v3
    ('r1k', inst, a, b, bulk, stem, cond)          ppolyf_u_1k  (r_width=rw_<stem>, r_length=rl_<stem>)
    ('rp', inst, a, b, bulk, stem, cond)           ppolyf_u     (secondary ESD: rw_<stem> rl_<stem> from rw_esd/rl_esd)
    ('dh'|'dl', inst, anode, cathode, stem, cond)  diode_pd2nw_03v3 / diode_nd2ps_03v3 (dw_esd, dl_esd)
    ('cap', inst, top, bottom, stem, cond)         cap_nmos_03v3 (cap_vref_w, cap_vref_l)
    ('x', inst, [nets], subckt, cond)              subcircuit instance
cond: None | 'nmos_pair' | '!nmos_pair' | 'dump' | 'nmos_pair&dump'   (build flags, PLAN_V2 4.1)
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))

FLAG_PARAM = {'nmos_pair': 'flag_nmos_pair', 'dump': 'flag_dump_devices'}

SUBCKTS = {}
ORDER = []


def sub(name, ports, items):
    SUBCKTS[name] = (ports, items)
    ORDER.append(name)


# ---------------------------------------------------------------------------------------------------- bias
sub('lvds_bias', ['VDD', 'VSS', 'EN', 'VBN', 'VBP', 'VB2', 'VREF'], [
    ('p', 'men_p', 'enb', 'EN', 'VDD', 'VDD', 'men_p', None),          # ENB inverter
    ('n', 'men_n', 'enb', 'EN', 'VSS', 'VSS', 'men_n', None),
    ('p', 'msw', 'nrb', 'enb', 'VDD', 'VDD', 'msw', None),              # series switch of the Rb branch (ON when ENB = 0)
    ('r1k', 'rrb', 'nrb', 'VBN', 'VSS', 'rb', None),                    # Rb: VDD -> diode
    ('n', 'mbn', 'VBN', 'VBN', 'VSS', 'VSS', 'mbn', None),             # NMOS reference diode (VBN)
    ('n', 'mpd_n', 'VBN', 'enb', 'VSS', 'VSS', 'mpd_n', None),          # parks VBN low when EN = 0
    ('n', 'mbs', 'VBP', 'VBN', 'VSS', 'VSS', 'mbs', None),              # sink 1:1 with MBN: pulls the reference current through the PMOS diode
    ('p', 'mbp', 'VBP', 'VBP', 'VDD', 'VDD', 'mbp', None),             # PMOS reference diode (VBP)
    ('p', 'mpu_p', 'VBP', 'EN', 'VDD', 'VDD', 'mpu_p', None),           # parks VBP high when EN = 0
    ('p', 'mb2p', 'VB2', 'VBP', 'VDD', 'VDD', 'mb2p', None),            # VB2 branch current source
    ('n', 'mb2', 'VB2', 'VB2', 'vf', 'VSS', 'mb2', None),               # replica of the M5 cascode (1 finger) on Vf
    ('r1k', 'rrf', 'vf', 'VSS', 'VSS', 'rf', None),                     # Vf = I * Rf
    ('n', 'mpd_2', 'VB2', 'enb', 'VSS', 'VSS', 'mpd_2', None),          # parks VB2 low when EN = 0
    ('r1k', 'rrdt', 'VDD', 'VREF', 'VSS', 'rdt', None),                 # Vref divider (0.48 VDD), EN-gated at the bottom
    ('r1k', 'rrdb', 'VREF', 'nmid', 'VSS', 'rdb', None),
    ('n', 'mvs', 'nmid', 'EN', 'VSS', 'VSS', 'mvs', None),
    ('cap', 'cvref', 'VREF', 'VSS', 'cap_vref', None),                  # decoupling of the dump-gate net
])

# ---------------------------------------------------------------------------------------------------- secondary ESD (swappable cell, fixed pins)
sub('lvds_esd2', ['A', 'B', 'VDD', 'VSS'], [
    ('rp', 'resd', 'A', 'B', 'VDD', 'esd', None),                       # ppolyf_u sits in an n-well tied to VDD (layout cookbook)
    ('dh', 'desd_h', 'B', 'VDD', 'esd', None),                          # P+/Nwell diode to VDD
    ('dl', 'desd_l', 'VSS', 'B', 'esd', None),                          # N+/Psub diode to VSS
])

# ---------------------------------------------------------------------------------------------------- stage 1
sub('lvds_pre', ['VDD', 'VSS', 'INP', 'INN', 'VBN', 'VBP', 'VB2', 'VREF', 'OA', 'OB'], [
    ('r1k', 'rla', 'VDD', 'OA', 'VSS', 'rl', None),                     # load resistors RL (ppolyf_u_1k, body VSS)
    ('r1k', 'rlb', 'VDD', 'OB', 'VSS', 'rl', None),
    ('p', 'mpt', 'tp', 'VBP', 'VDD', 'VDD', 'mpt', None),              # PMOS tail
    ('p', 'mp1a', 'fa', 'INP', 'tp', 'tp', 'mp1', None),               # PMOS pair, own n-well = tail node
    ('p', 'mp1b', 'fb', 'INN', 'tp', 'tp', 'mp1', None),
    ('p', 'mpda', 'fa', 'VREF', 'tp', 'tp', 'mpd', 'dump'),            # dump twins: gate at Vref, drains on the same fold nodes
    ('p', 'mpdb', 'fb', 'VREF', 'tp', 'tp', 'mpd', 'dump'),
    ('n', 'm3a', 'fa', 'VBN', 'VSS', 'VSS', 'm3', 'nmos_pair'),         # fold sinks (hybrid)
    ('n', 'm3b', 'fb', 'VBN', 'VSS', 'VSS', 'm3', 'nmos_pair'),
    ('n', 'm3a', 'fa', 'VBN', 'VSS', 'VSS', 'm3a', '!nmos_pair'),       # PMOS-only variant (T1 variant A): sinks reduced so RL carries the same current
    ('n', 'm3b', 'fb', 'VBN', 'VSS', 'VSS', 'm3a', '!nmos_pair'),
    ('n', 'm5a', 'OA', 'VB2', 'fa', 'VSS', 'm5', None),                # fold cascodes
    ('n', 'm5b', 'OB', 'VB2', 'fb', 'VSS', 'm5', None),
    ('n', 'mnt', 'tn', 'VBN', 'VSS', 'VSS', 'mnt', 'nmos_pair'),        # NMOS tail
    ('n', 'mn1a', 'OA', 'INP', 'tn', 'VSS', 'mn1', 'nmos_pair'),        # NMOS pair pulls straight from the load nodes
    ('n', 'mn1b', 'OB', 'INN', 'tn', 'VSS', 'mn1', 'nmos_pair'),
    ('n', 'mnda', 'OA', 'VREF', 'tn', 'VSS', 'mnd', 'nmos_pair&dump'),
    ('n', 'mndb', 'OB', 'VREF', 'tn', 'VSS', 'mnd', 'nmos_pair&dump'),
])

# ---------------------------------------------------------------------------------------------------- stage 2: hysteresis comparator
sub('lvds_hyst', ['VDD', 'VSS', 'OA', 'OB', 'VBN', 'EN', 'D2A', 'D2B'], [
    ('n', 'mt2', 'ts', 'VBN', 'VSS', 'VSS', 'mt2', None),
    ('n', 'ms1', 'D2A', 'OA', 'sa', 'VSS', 'ms', None),                # input pair, side A gate = OA
    ('n', 'ms2', 'D2B', 'OB', 'sb', 'VSS', 'ms', None),
    ('r1k', 'rs1', 'sa', 'ts', 'VSS', 'rs', None),                      # source degeneration (ratio-metric trip)
    ('r1k', 'rs2', 'sb', 'ts', 'VSS', 'rs', None),
    ('p', 'mld1', 'D2A', 'D2A', 'VDD', 'VDD', 'mld', None),            # diode loads
    ('p', 'mld2', 'D2B', 'D2B', 'VDD', 'VDD', 'mld', None),
    ('p', 'mlc1', 'D2A', 'D2B', 'VDD', 'VDD', 'mlc', None),            # cross-coupled loads (alpha = nf_c / nf_d)
    ('p', 'mlc2', 'D2B', 'D2A', 'VDD', 'VDD', 'mlc', None),
    ('p', 'mpu1', 'D2A', 'EN', 'VDD', 'VDD', 'mpu2', None),            # park d2a/d2b high when EN = 0
    ('p', 'mpu2', 'D2B', 'EN', 'VDD', 'VDD', 'mpu2', None),
])

# ---------------------------------------------------------------------------------------------------- stage 3 + output chain
sub('lvds_out', ['VDD', 'VSS', 'D2A', 'D2B', 'EN', 'OUT'], [
    ('p', 'mp3a', 'n3a', 'D2A', 'VDD', 'VDD', 'mp3', None),            # PMOS copies of the stage-2 load diodes
    ('p', 'mp3b', 'd3', 'D2B', 'VDD', 'VDD', 'mp3', None),
    ('n', 'mn3a', 'n3a', 'n3a', 'VSS', 'VSS', 'mn3', None),            # NMOS mirror: copy of side A subtracted from copy of side B at d3
    ('n', 'mn3b', 'd3', 'n3a', 'VSS', 'VSS', 'mn3', None),
    ('p', 'mnandp1', 'nd', 'd3', 'VDD', 'VDD', 'nand_p', None),        # NAND2(d3, EN)
    ('p', 'mnandp2', 'nd', 'EN', 'VDD', 'VDD', 'nand_p', None),
    ('n', 'mnandn1', 'nd', 'd3', 'nm', 'VSS', 'nand_n', None),
    ('n', 'mnandn2', 'nm', 'EN', 'VSS', 'VSS', 'nand_n', None),
    ('p', 'minv1p', 'i1', 'nd', 'VDD', 'VDD', 'inv1_p', None),         # three inverters: NAND + 3 INV = AND(EN, d3)
    ('n', 'minv1n', 'i1', 'nd', 'VSS', 'VSS', 'inv1_n', None),
    ('p', 'minv2p', 'i2', 'i1', 'VDD', 'VDD', 'inv2_p', None),
    ('n', 'minv2n', 'i2', 'i1', 'VSS', 'VSS', 'inv2_n', None),
    ('p', 'minv3p', 'OUT', 'i2', 'VDD', 'VDD', 'inv3_p', None),
    ('n', 'minv3n', 'OUT', 'i2', 'VSS', 'VSS', 'inv3_n', None),
])

# ---------------------------------------------------------------------------------------------------- lane and macro
sub('lvds_lane', ['VDD', 'VSS', 'INP', 'INN', 'EN', 'VBN', 'VBP', 'VB2', 'VREF', 'OUT'], [
    ('x', 'xesdp', ['INP', 'gp', 'VDD', 'VSS'], 'lvds_esd2', None),
    ('x', 'xesdn', ['INN', 'gn', 'VDD', 'VSS'], 'lvds_esd2', None),
    ('x', 'xpre', ['VDD', 'VSS', 'gp', 'gn', 'VBN', 'VBP', 'VB2', 'VREF', 'oa', 'ob'], 'lvds_pre', None),
    ('x', 'xhyst', ['VDD', 'VSS', 'oa', 'ob', 'VBN', 'EN', 'd2a', 'd2b'], 'lvds_hyst', None),
    ('x', 'xout', ['VDD', 'VSS', 'd2a', 'd2b', 'EN', 'OUT'], 'lvds_out', None),
])

sub('lvds_rx_x3', ['VDD', 'VSS', 'RX0_P', 'RX0_N', 'RX1_P', 'RX1_N', 'RX2_P', 'RX2_N', 'EN', 'RX0_O', 'RX1_O', 'RX2_O'], [
    ('x', 'xbias', ['VDD', 'VSS', 'EN', 'vbn', 'vbp', 'vb2', 'vref'], 'lvds_bias', None),
    ('x', 'xl0', ['VDD', 'VSS', 'RX0_P', 'RX0_N', 'EN', 'vbn', 'vbp', 'vb2', 'vref', 'RX0_O'], 'lvds_lane', None),
    ('x', 'xl1', ['VDD', 'VSS', 'RX1_P', 'RX1_N', 'EN', 'vbn', 'vbp', 'vb2', 'vref', 'RX1_O'], 'lvds_lane', None),
    ('x', 'xl2', ['VDD', 'VSS', 'RX2_P', 'RX2_N', 'EN', 'vbn', 'vbp', 'vb2', 'vref', 'RX2_O'], 'lvds_lane', None),
])

UNIMPLEMENTED_FLAGS = ('extra_gain_stage', 'bias_constgm', 'failsafe', 'on_die_term')


# ====================================================================================================
def _cond_expr(cond):
    parts = []
    for t in cond.split('&'):
        neg = t.startswith('!')
        t = t.lstrip('!')
        parts.append('(%s %s 1)' % (FLAG_PARAM[t], '!=' if neg else '=='))
    return ' && '.join(parts)


def _mos_sim(it):
    kind, inst, d, g, s, b, stem, _ = it
    model = 'nfet_03v3' if kind == 'n' else 'pfet_03v3'
    return ("X%s %s %s %s %s %s L={l_%s} W={w_%s} nf={nf_%s} "
            "ad='int((nf+1)/2) * W/nf * 0.18u' as='int((nf+2)/2) * W/nf * 0.18u' "
            "pd='2*int((nf+1)/2) * (W/nf + 0.18u)' ps='2*int((nf+2)/2) * (W/nf + 0.18u)' "
            "nrd='0.18u / W' nrs='0.18u / W' sa=0 sb=0 sd=0" % (inst, d, g, s, b, model, stem, stem, stem))


def _line_sim(it):
    k = it[0]
    if k in ('n', 'p'):
        return _mos_sim(it)
    if k == 'r1k':
        _, inst, a, b, bulk, stem, _c = it
        return 'X%s %s %s %s ppolyf_u_1k r_width={rw_%s} r_length={rl_%s}' % (inst, a, b, bulk, stem, stem)
    if k == 'rp':
        _, inst, a, b, bulk, stem, _c = it
        return 'X%s %s %s %s ppolyf_u r_width={rw_%s} r_length={rl_%s}' % (inst, a, b, bulk, stem, stem)
    if k == 'dh':
        _, inst, a, c, stem, _c = it
        return 'D%s %s %s diode_pd2nw_03v3 area={dw_%s*dl_%s} pj={2*(dw_%s+dl_%s)}' % (inst, a, c, stem, stem, stem, stem)
    if k == 'dl':
        _, inst, a, c, stem, _c = it
        return 'D%s %s %s diode_nd2ps_03v3 area={dw_%s*dl_%s} pj={2*(dw_%s+dl_%s)}' % (inst, a, c, stem, stem, stem, stem)
    if k == 'cap':
        _, inst, t, b, stem, _c = it
        return 'X%s %s %s cap_nmos_03v3 c_length={cap_vref_l} c_width={cap_vref_w}' % (inst, t, b)
    if k == 'x':
        _, inst, nets, sname, _c = it
        return '%s %s %s' % (inst, ' '.join(nets), sname)
    raise ValueError(k)


def _cond_of(it):
    return it[-1]


def emit_sim():
    out = ['* lvds_rx_core.spice -- LVDS receiver macro lvds_rx_x3 (3 lanes + shared bias), gf180mcuD 3.3 V devices.',
           '* GENERATED by netlist/gen_core.py from netlist/lvds_circuit.py -- do not edit by hand.',
           '* Every W/L/nf and poly size comes from the parameters of sizing/sizes.spice: the deck must  .include  sizes.spice BEFORE this file',
           '* and the PDK sections (header of sim/harness).  Matched devices are one device with nf fingers (never m).',
           '* Build flags (parameters of sizes.spice, redefine AFTER the include to switch): flag_nmos_pair flag_dump_devices (implemented);',
           '*   flag_extra_gain_stage flag_bias_constgm flag_failsafe flag_on_die_term (NOT implemented in v0: setting one aborts the parse).',
           '* Instance names are hierarchical, e.g. xl0.xpre.xmp1a; the BSIM device inside is  @m.<path>.m0[...] .',
           '']
    for name in ORDER:
        ports, items = SUBCKTS[name]
        out.append('.subckt %s %s' % (name, ' '.join(ports)))
        if name == 'lvds_rx_x3':
            out.append('* unimplemented build flags must not be set: the resistor below, whose value is an undefined parameter, makes ngspice stop at parse time (an unknown subckt would fail even in a false .if)')
            for f in UNIMPLEMENTED_FLAGS:
                out.append('.if (flag_%s != 0)' % f)
                out.append('Rflag_%s_not_implemented 0 0 FLAG_%s_NOT_IMPLEMENTED_set_it_back_to_0' % (f, f))
                out.append('.endif')
        cur = None
        for it in items:
            c = _cond_of(it)
            if c != cur:
                if cur is not None:
                    out.append('.endif')
                if c is not None:
                    out.append('.if (%s)' % _cond_expr(c))
                cur = c
            out.append(_line_sim(it))
        if cur is not None:
            out.append('.endif')
        out.append('.ends %s' % name)
        out.append('')
    return '\n'.join(out)


# ====================================================================================================
def load_table(root=ROOT):
    with open(os.path.join(root, 'layout', 'device_table.json')) as f:
        t = json.load(f)
    dev = {d['stem']: d for d in t['devices']}
    res = {d['stem']: d for d in t['resistors']}
    return t, dev, res


def cond_true(cond, flags):
    if cond is None:
        return True
    for tok in cond.split('&'):
        neg = tok.startswith('!')
        v = bool(flags[{'nmos_pair': 'nmos_pair', 'dump': 'dump_devices'}[tok.lstrip('!')]])
        if v == neg:
            return False
    return True


def _num(x):
    return ('%.4f' % x).rstrip('0').rstrip('.')


def _line_lvs(it, dev, res, tab):
    k = it[0]
    if k in ('n', 'p'):
        _, inst, d, g, s, b, stem, _c = it
        v = dev[stem]
        model = v['model']
        nfp = ' nf=%d' % v['nf'] if v['nf'] > 1 else ''
        return 'X%s %s %s %s %s %s w=%su%s l=%su' % (inst.upper(), d, g, s, b, model, _num(v['W_um']), nfp, _num(v['L_um']))
    if k == 'r1k':
        _, inst, a, b, bulk, stem, _c = it
        v = res[stem]
        return 'X%s %s %s %s ppolyf_u_1k r_width=%su r_length=%su' % (inst.upper(), a, b, bulk, _num(v['r_width_um']), _num(v['r_length_um']))
    if k == 'rp':
        _, inst, a, b, bulk, stem, _c = it
        v = res['resd']
        return 'X%s %s %s %s ppolyf_u r_width=%su r_length=%su' % (inst.upper(), a, b, bulk, _num(v['r_width_um']), _num(v['r_length_um']))
    if k in ('dh', 'dl'):
        _, inst, a, c, stem, _c = it
        v = [d for d in tab['diodes'] if d['stem'] == ('desd_h' if k == 'dh' else 'desd_l')][0]
        return 'D%s %s %s %s area=%sp pj=%su' % (inst.upper(), a, c, v['model'], _num(v['area_um2']), _num(2 * (v['w_um'] + v['l_um'])))
    if k == 'cap':
        _, inst, t, b, stem, _c = it
        v = tab['cap_vref']
        # LVS reference: the layout draws the Vref capacitor as an nfet_03v3 with drain = source = bulk = bottom net (gate = top net), because the PDK
        # MOS-capacitor cell fails foundry DRC (T8b report, decision 1).  The simulation netlist (emit_sim) keeps cap_nmos_03v3.
        return 'X%s %s %s %s %s nfet_03v3 w=%su l=%su' % (inst.upper(), b, t, b, b, _num(v['c_width_um']), _num(v['c_length_um']))
    if k == 'x':
        _, inst, nets, sname, _c = it
        return '%s %s %s' % (inst.upper(), ' '.join(nets), sname)
    raise ValueError(k)


def emit_lvs(flags=None, flat=False, root=ROOT):
    tab, dev, res = load_table(root)
    flags = dict(tab['flags'] if flags is None else flags)
    out = ['* lvds_rx_lvs_ref.spice -- LVS reference netlist of lvds_rx_x3 (%s), gf180mcuD device names, total w with nf (Magic/Netgen style).' % ('flat' if flat else 'hierarchical'),
           '* GENERATED by netlist/gen_lvs_ref.py from netlist/lvds_circuit.py + layout/device_table.json -- do not edit by hand.',
           '* flags: %s' % ' '.join('%s=%s' % (k, v) for k, v in flags.items()),
           '* Dummy devices (end fingers, guard/tap) are NOT here: the layout tasks (T8-T10) add them explicitly (Netgen merges parallel fingers, so dummies must be listed).',
           '* Diodes use the PDK device names; the Vref cap is an nfet_03v3 with D = S = bulk = VSS (the way the layout draws it; the sim netlist keeps cap_nmos_03v3).',
           '']
    if not flat:
        for name in ORDER:
            ports, items = SUBCKTS[name]
            out.append('.subckt %s %s' % (name, ' '.join(ports)))
            for it in items:
                if cond_true(_cond_of(it), flags):
                    out.append(_line_lvs(it, dev, res, tab))
            out.append('.ends %s' % name)
            out.append('')
        return '\n'.join(out)
    # flat: expand lvds_rx_x3 recursively; net names of internal nets are prefixed with the instance path
    ports, items = SUBCKTS['lvds_rx_x3']
    out.append('.subckt lvds_rx_x3 %s' % ' '.join(ports))

    def expand(name, mapping, prefix):
        for it in SUBCKTS[name][1]:
            if not cond_true(_cond_of(it), flags):
                continue
            def mp(n):
                if n in mapping:
                    return mapping[n]
                return (prefix + n) if prefix else n
            if it[0] == 'x':
                _, inst, nets, sname, _c = it
                sp = SUBCKTS[sname][0]
                expand(sname, dict(zip(sp, [mp(n) for n in nets])), prefix + inst + '.')
                continue
            it2 = list(it)
            if it[0] in ('n', 'p'):
                it2[2:6] = [mp(n) for n in it[2:6]]
            elif it[0] in ('r1k', 'rp'):
                it2[2:5] = [mp(n) for n in it[2:5]]
            elif it[0] in ('dh', 'dl'):
                it2[2:4] = [mp(n) for n in it[2:4]]
            elif it[0] == 'cap':
                it2[2:4] = [mp(n) for n in it[2:4]]
            it2[1] = prefix + it[1]
            out.append(_line_lvs(tuple(it2), dev, res, tab))
    expand('lvds_rx_x3', {p: p for p in ports}, '')
    out.append('.ends lvds_rx_x3')
    return '\n'.join(out) + '\n'
