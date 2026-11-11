#!/usr/bin/env python3
"""summarize.py  one line per leaf result: verdict and the observed numbers (reads results/*.json, host or container)."""
import glob
import json
import os

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
for f in sorted(glob.glob(R + "/t_*.json")):
    r = json.load(open(f))
    s = r["steps"]
    if "locator" in s:
        print(f"{r['cell']:14s} {r['verdict']:6s} LVS fails={s['lvs_fails']['ok']} locator ok={s['locator']['ok']} "
              f"distance_to_fault={s['locator']['distance_to_fault_um']} um  wall {r['wall_s']} s")
        continue
    k = s.get("klayout", {})
    lv = s["lvs"]
    sc = s["selfcheck"]
    neg = s["negctl"]
    print(f"{r['cell']:14s} {r['verdict']:6s} fingers {sc.get('n_mos')} res {sc.get('n_res')} | magic {s['magic_drc']['mag']['total']}/{s['magic_drc']['gds_readback']['total']}"
          f" | KL main {k.get('main')} ant {k.get('antenna')} dbu {k.get('dbu')} | LVS clean={lv['clean']} dev {lv['devices']} nets {lv['nets']}"
          f" | readback {s['finger_readback']['ok']} | neg " + " ".join(f"{n}={v['detected']}" for n, v in neg.items() if n != "ok")
          + f" | wall {r['wall_s']} s")
