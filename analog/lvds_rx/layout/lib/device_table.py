"""device_table.py -- read layout/device_table.json (written by sizing/lvds_rx_sizing.py).

Layout generators take W/L/nf from here by stem, never from literals, so layout and netlist cannot drift.
W_um in the table is the TOTAL width (Netgen style, `w=` of the schematic line); Wf_um is the width of ONE finger
(the Magic gencell `w`).  Check: W_um == nf * Wf_um (asserted on load).
"""
import json
import os
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(os.path.dirname(HERE), "device_table.json")


@dataclass(frozen=True)
class Dev:
    stem: str
    model: str       # nfet_03v3 | pfet_03v3
    W: float         # total width, um
    L: float
    nf: int
    Wf: float        # finger width, um
    role: str = ""
    block: str = ""

    @property
    def kind(self):  # 'n' | 'p'
        return "n" if self.model.startswith("nfet") else "p"


class DeviceTable:
    def __init__(self, path=DEFAULT_PATH):
        self.path = path
        with open(path) as f:
            self.raw = json.load(f)
        self.flags = self.raw.get("flags", {})
        self.hashes = self.raw.get("hashes", {})
        self.devs = {}
        for d in self.raw["devices"]:
            dev = Dev(d["stem"], d["model"], float(d["W_um"]), float(d["L_um"]), int(d["nf"]), float(d["Wf_um"]),
                      d.get("role", ""), d.get("block", ""))
            if abs(dev.W - dev.nf * dev.Wf) > 0.011:
                raise ValueError(f"device table: {dev.stem} W {dev.W} != nf*Wf {dev.nf * dev.Wf}")
            self.devs[dev.stem] = dev
        self.res = {r["stem"]: r for r in self.raw.get("resistors", [])}
        self.dio = {r["stem"]: r for r in self.raw.get("diodes", [])}

    def __getitem__(self, stem):
        return self.devs[stem]

    def get(self, stem):
        return self.devs[stem]

    @staticmethod
    def spice(inst, dev, d, g, s, b, nf=None):
        """Netgen-style schematic line for `nf` fingers of `dev` (w = nf * Wf; matches the extraction after parallel merge)."""
        n = dev.nf if nf is None else nf
        return f"X{inst} {d} {g} {s} {b} {dev.model} w={n * dev.Wf:g}u l={dev.L:g}u"

    @staticmethod
    def spice_dummy(inst, dev, d, rail, b, n=1):
        """Explicit dummy finger(s): gate = source = rail, drain = the neighbouring net."""
        return f"X{inst} {d} {rail} {rail} {b} {dev.model} w={n * dev.Wf:g}u l={dev.L:g}u"
