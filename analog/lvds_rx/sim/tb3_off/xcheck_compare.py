"""Compare the offset definitions of tb3_off (d2 differential zero, output VDD/2 crossing, both hysteresis OFF) with the hysteresis-ON
trip-window centre of tb3_trip under the same mismatch seeds (xcheck_trip_mc).  Prints a table; run on the host, plain python."""
import json
import os

B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load(n):
    r = json.load(open(os.path.join(B, n, "results.json")))
    return r["runs"] if isinstance(r, dict) and "runs" in r else r


a = load("tb3_off")
t = load("xcheck_trip_mc")
ta = {(x["params"]["vic"], x.get("seed")): x["metrics"] for x in t}
print("vic seed | vos_d2  vos_out | trip centre (hyst on)  vh   [mV]")
dd, do = [], []
for x in a:
    k = (x["params"]["vic"], x.get("seed"))
    m = x["metrics"]
    y = ta.get(k)
    if y is None:
        print(k, "no match")
        continue
    print("%5.2f %10s | %7.2f %7.2f | %7.2f %6.2f" % (k[0], k[1], m["vos_v"] * 1e3, m["vos_out_v"] * 1e3, y["off_v"] * 1e3, y["vh_v"] * 1e3))
    dd.append((m["vos_v"] - y["off_v"]) * 1e3)
    do.append((m["vos_out_v"] - y["off_v"]) * 1e3)
import statistics as S
print("d2-based minus trip centre:  mean %.2f  sd %.2f mV" % (S.mean(dd), S.pstdev(dd)))
print("out-based minus trip centre: mean %.2f  sd %.2f mV" % (S.mean(do), S.pstdev(do)))
