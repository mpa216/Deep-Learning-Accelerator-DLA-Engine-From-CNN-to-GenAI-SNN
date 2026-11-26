#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Build the power-connected A56/ACV block WITH the LVDS receiver macro
# (branch lvds-integration).  Same three steps as librelane/build_acv_connected.sh
# (which builds the signed-off chip), on config_acv_lvds.yaml:
#   1) harden RTL -> placement -> CTS -> routing -> fill, stop before streamout;
#   2) weld the template DVDD/DVSS pins to the PDN core ring (connect_power.py,
#      edge-agnostic; it refuses to write if any finger cannot be welded safely);
#   3) resume streamout -> Magic/KLayout DRC -> XOR -> extraction -> Netgen LVS.
# Then (not here): SPEF STA on the connected design, the KLayout foundry deck,
# the via-array check, gate-level simulation and librelane/lvds/check_integration.py.
#
# Run inside apic_headless:
#   docker exec apic_headless bash -lc 'cd /foss/designs/.claude/worktrees/lvds-rx/librelane && bash lvds/build_acv_lvds_connected.sh acv_lvds1'
# Any further arguments go to BOTH librelane calls (e.g. -c KEY=VALUE overrides), so the harden and
# the sign-off resume always run with the same settings.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."
TAG=${1:-acv_lvds}
shift || true
EXTRA=("$@")
CFG=config_acv_lvds.yaml

# 1) everything up to fill insertion + cell tables; stop BEFORE streamout
librelane "$CFG" --run-tag "$TAG" --to Odb.CellFrequencyTables "${EXTRA[@]}"

RUN="runs/$TAG"
CLEAN_ODB=$(ls "$RUN"/*-odb-cellfrequencytables/dla_engine_chip.odb)   # pristine, pre-streamout
FILL=$(ls -d "$RUN"/*-openroad-fillinsertion)

# 2) power-pin weld (always from the PRISTINE odb, never a patched one: re-patching stacks vias)
openroad-librelane -no_init -exit -python connect_power.py \
    "$CLEAN_ODB" "$RUN/_connected.odb" "$RUN/_connected.def"

# 3) sign-off tail on the connected design (pnl/nl from fill insertion, not final/)
librelane "$CFG" --run-tag "$TAG" --from Magic.StreamOut \
    -e odb="$(realpath "$RUN/_connected.odb")" \
    -e def="$(realpath "$RUN/_connected.def")" \
    -e pnl="$(realpath "$FILL"/dla_engine_chip.pnl.v)" \
    -e nl="$(realpath "$FILL"/dla_engine_chip.nl.v)" "${EXTRA[@]}"

echo "Done. Power-connected views in $RUN/final/ (gds/def/nl)."
