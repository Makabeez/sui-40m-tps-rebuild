"""Gas, senders and settlement lag of the live MillionTPS run.

Usage: python3 footprint.py DATA_DIR OUT_JSON
"""
import collections, json, os, ssl, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

d, outp = sys.argv[1], sys.argv[2]
URL = "https://graphql.mainnet.sui.io/graphql"
CTX = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
Q = """query($k:[String!]!){ multiGetTransactions(keys:$k){ digest sender{address}
  effects{ status timestamp gasEffects{ gasSummary{ computationCost storageCost storageRebate nonRefundableStorageFee } } } } }"""

load = lambda n: [json.loads(l) for l in open(os.path.join(d, "events", n + ".jsonl"))]
cre = {c["tunnel_id"]: c for c in load("ArenaTunnelCreated")}
live = lambda t: t in cre and "2026-10-07T08:30" <= cre[t]["ts"][:16] < "2026-10-07T09:30"
phase_tx = collections.defaultdict(set)
for name in ("ArenaTunnelCreated", "ArenaTunnelActivated", "ArenaTunnelSettled", "ArenaDisputeOpened", "ArenaSeatFunded"):
    for r in load(name):
        if live(r["tunnel_id"]):
            phase_tx[name].add(r["tx"])
alltx = sorted(set().union(*phase_tx.values()))


def gql(keys):
    body = json.dumps({"query": Q, "variables": {"k": keys}}).encode()
    for attempt in range(8):
        try:
            req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, context=CTX, timeout=90) as r:
                j = json.load(r)
            if "errors" in j:
                raise RuntimeError(str(j["errors"])[:300])
            return j["data"]["multiGetTransactions"]
        except Exception as e:  # noqa: BLE001
            print("retry", attempt, e, file=sys.stderr, flush=True)
            time.sleep(3 * (attempt + 1))
    return []


txs = {}
with ThreadPoolExecutor(4) as ex:
    for res in ex.map(gql, [alltx[i:i + 50] for i in range(0, len(alltx), 50)]):
        for t in res or []:
            if t:
                txs[t["digest"]] = t

def gas(t):
    g = t["effects"]["gasEffects"]["gasSummary"]
    return int(g["computationCost"]) + int(g["storageCost"]) - int(g["storageRebate"])

per_phase = {}
for name, s in phase_tx.items():
    got = [txs[x] for x in s if x in txs]
    per_phase[name] = {"txs": len(s), "fetched": len(got), "net_gas_SUI": sum(map(gas, got)) / 1e9,
                       "senders": collections.Counter(t["sender"]["address"] for t in got).most_common(3),
                       "failed": sum(1 for t in got if t["effects"]["status"] != "SUCCESS")}

recs = [json.loads(l) for l in open(os.path.join(d, "records.jsonl"))]
lag = collections.defaultdict(list)
for r in recs:
    if live(r["tunnel_id"]):
        t, s = int(r["terminal_timestamp"]), int(r["settled_at_ms"])
        if 0 <= s - t < 86_400_000:
            lag[r["disposition"]].append((s - t) / 1000)
lagstats = {}
for k, v in lag.items():
    v.sort()
    lagstats[f"disp{k}"] = {"n": len(v), "p50_s": v[len(v) // 2], "p90_s": v[int(len(v) * .9)], "max_s": v[-1]}

out = {"unique_txs": len(alltx), "fetched": len(txs),
       "net_gas_SUI_total": sum(map(gas, txs.values())) / 1e9,
       "senders_top": collections.Counter(t["sender"]["address"] for t in txs.values()).most_common(5),
       "per_phase": per_phase, "settlement_lag_seconds_by_disposition": lagstats}
json.dump(out, open(outp, "w"), indent=2)
print(json.dumps(out, indent=2))

# --- distinct senders per phase (appended) ---
for name, s in phase_tx.items():
    got = [txs[x] for x in s if x in txs]
    c = collections.Counter(t["sender"]["address"] for t in got)
    print(name, "distinct_senders", len(c), "txs_from_top2", sum(v for _, v in c.most_common(2)), "of", len(got))
