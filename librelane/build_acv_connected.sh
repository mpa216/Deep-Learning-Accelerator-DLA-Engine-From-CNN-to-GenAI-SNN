#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Build the power-connected A56/ACV block GDS (design: dla_engine_chip) from RTL.
#
# WHY THIS EXISTS: the gf180 I/O cells hand power to a project block as Metal2
# pins sitting in the die margin (this block: DVDD on the WEST edge, DVSS on the
# NORTH edge -- see librelane/A56_ACV.def). LibreLane's PDN, however, delivers
# power on a Metal4/Metal5 core ring ~33 um inland, so a straight harden leaves
# the template DVDD/DVSS pins electrically islanded -> chip LVS reports them
# disconnected (each net splits into a main net + isolated pin pieces).
# Metal5-only power is NOT acceptable for chip integration (the pad power lands
# on Metal2), so the block must itself bridge Metal2 -> ... -> Metal5.
#
# THE FIX (this script): after detailed routing + fill, weld each template power
# pin to its OWN-net PDN ring with a short Metal2 reach + a via stack, run through
# the EMPTY die margins (not the congested core edge, which shorts). Each via
# lands in a clean ring gap between the existing strap->ring PDN vias. This is the
# in-flow "power connector" the chipathon organizers endorsed (powerpin_solution.txt),
# welded directly as top-level PDN geometry so the GDS is self-contained -- no
# separate connector cell, no connect-by-label needed.
#
# RESULT (verified): Magic DRC 0, Netgen LVS "Circuits match uniquely" (0 errors,
# 0 shorts), Magic<->KLayout XOR 0. DVDD/DVSS are matched top-level pins.
#
# Run inside the chipathon container (apic_headless), from the librelane/ dir:
#   docker exec apic_headless bash -lc 'cd /foss/designs/librelane && ./build_acv_connected.sh'
# ---------------------------------------------------------------------------
set -euo pipefail
TAG=${1:-acv_connected}

# 1) Synthesis -> placement -> CTS -> routing -> fill. Stop BEFORE streamout so
#    we can inject the power connector into the routed database.
librelane config_acv.yaml --run-tag "$TAG" --to Odb.CellFrequencyTables

RUN="runs/$TAG"
CLEAN_ODB=$(ls "$RUN"/*-odb-cellfrequencytables/dla_engine_chip.odb)   # pristine, pre-streamout
FILL=$(ls -d "$RUN"/*-openroad-fillinsertion)

# 2) Weld the DVDD/DVSS template pins to the PDN ring. IMPORTANT: always patch the
#    PRISTINE pre-streamout ODB above -- never final/odb or an already-patched odb
#    (the resume's save-views overwrites final/odb, and re-patching stacks vias ->
#    a phantom "abut/overlap between subcells" DRC).
openroad-librelane -no_init -exit -python connect_power_v3.py \
    "$CLEAN_ODB" "$RUN/_connected.odb" "$RUN/_connected.def"

# 3) Resume: streamout -> Magic/KLayout DRC -> XOR -> SPICE extract -> Netgen LVS
#    -> rest of signoff. pnl/nl come from fill insertion (not final/, else the
#    save-views step self-copies and errors).
librelane config_acv.yaml --run-tag "$TAG" --from Magic.StreamOut \
    -e odb="$(realpath "$RUN/_connected.odb")" \
    -e def="$(realpath "$RUN/_connected.def")" \
    -e pnl="$(realpath "$FILL"/dla_engine_chip.pnl.v)" \
    -e nl="$(realpath "$FILL"/dla_engine_chip.nl.v)"

echo "Done. Power-connected views in $RUN/final/ (gds/def/nl)."
echo "Submission artifacts (repo root): copy final/gds/dla_engine_chip.gds -> gds/,"
echo "  final/nl/dla_engine_chip.nl.v -> verilog/  (lvs_config.json + info.yaml already point at them)."
