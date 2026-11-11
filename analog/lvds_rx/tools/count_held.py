import json, sys, collections
r = json.load(open(sys.argv[1]))
c = collections.Counter()
for x in r["runs"]:
    m = x["metrics"]
    c[(x["params"].get("term"), m.get("n_high"), m.get("n_mid"))] += 1
for k, v in sorted(c.items(), key=str):
    print("term=%s n_high=%s n_mid=%s : %d runs" % (k + (v,)))
