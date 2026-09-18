#!/usr/bin/env bash
# Run all formal proofs. Inside the apic_headless container:
#   docker exec apic_headless bash -lc 'cd /foss/designs/formal && bash run_formal.sh'
set -uo pipefail
cd "$(dirname "$0")"
rc=0
for t in dla_controller dla_serial_bridge; do
  echo "############################################################"
  echo "# sby prove: $t"
  echo "############################################################"
  sby -f "$t.sby" > "/tmp/${t}.sbylog" 2>&1
  sby_rc=$?
  grep -E "DONE|proof by k-induction|returned (pass|FAIL)" "/tmp/${t}.sbylog" || true
  if [ "$sby_rc" -eq 0 ]; then echo ">> $t: PASS"; else echo ">> $t: FAIL (rc=$sby_rc)"; rc=1; fi
  echo ""
done
[ "$rc" -eq 0 ] && echo "ALL FORMAL PROOFS PASSED" || echo "SOME FORMAL PROOFS FAILED"
exit $rc
