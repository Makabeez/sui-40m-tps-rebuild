"""Reconstruct the MillionTPS runs from Sui mainnet data.

Usage: python3 analyze.py DATA_DIR OUT_DIR
Inputs: DATA_DIR/events/*.jsonl (crawl_events.py), DATA_DIR/records.jsonl (fetch_records.py)
Outputs: OUT_DIR/summary.json, OUT_DIR/curve_live.csv (per-second reconstructed throughput, live run)
"""
import base64, collections, csv, datetime as dt, json, os, sys

data, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
ev = lambda n: [json.loads(l) for l in open(os.path.join(data, "events", n + ".jsonl"))]
created, activated, settled = ev("ArenaTunnelCreated"), ev("ArenaTunnelActivated"), ev("ArenaTunnelSettled")
disputes = ev("ArenaDisputeOpened")
records = {r["tunnel_id"]: r for r in map(json.loads, open(os.path.join(data, "records.jsonl")))}
act = {a["tunnel_id"]: a for a in activated}
cre = {c["tunnel_id"]: c for c in created}

def iso(ms): return dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc).isoformat(timespec="seconds")

# Live run window (Basecamp Day 1, Summit Stage, ~16:41-16:48 SGT = 08:41-08:48 UTC)
LIVE_START, LIVE_END = "2026-10-07T08:30", "2026-10-07T09:30"
def in_live(c): return LIVE_START <= c["ts"][:16] < LIVE_END

def domain(r):
    try:
        return json.loads(base64.b64decode(r["outcome"]))["domain"]
    except Exception:  # noqa: BLE001
        return "?"

# Per-tunnel session: activation -> terminal timestamp (offchain), receipts = offchain state transitions
sessions, invalid_ts = [], collections.Counter()
for tid, r in records.items():
    a = act.get(tid)
    if not a:
        continue
    start, end = int(a["activated_at_ms"]), int(r["terminal_timestamp"])
    if not (0 <= end - start <= 86_400_000):
        invalid_ts[(r["disposition"], tid in cre and in_live(cre[tid]))] += 1
        continue
    sessions.append({"tid": tid, "start": start, "end": end, "n": int(r["receipt_count"]),
                     "live": tid in cre and in_live(cre[tid]), "domain": domain(r),
                     "disp": r["disposition"], "settled": int(r["settled_at_ms"]),
                     "ev": r["evidence_class"], "outcome": r["outcome"]})

def curve(ss):
    """Spread each tunnel's receipts uniformly over its session, sum per wall-clock second."""
    per = collections.defaultdict(float)
    for s in ss:
        dur = max(s["end"] - s["start"], 1)
        rate = s["n"] / dur  # receipts per ms
        t = s["start"]
        while t < s["end"]:
            sec = t // 1000
            nxt = min((sec + 1) * 1000, s["end"])
            per[sec] += rate * (nxt - t)
            t = nxt
    return per

live = [s for s in sessions if s["live"]]
per = curve(live)
peak_sec = max(per, key=per.get)
with open(os.path.join(out, "curve_live.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["utc", "reconstructed_tps"])
    for sec in sorted(per):
        w.writerow([iso(sec * 1000), round(per[sec])])

# Concurrency at peak
conc = sum(1 for s in live if s["start"] <= peak_sec * 1000 < s["end"])
running = [s for s in live if s["n"] > 0]
durs = sorted((s["end"] - s["start"]) / 1000 for s in running)
rates = sorted(s["n"] / max((s["end"] - s["start"]) / 1000, 1e-3) for s in running)
med = lambda xs: xs[len(xs) // 2] if xs else None

# Onchain footprint of the live run
live_ids = {s["tid"] for s in live}
txs = set()
for name, rows in (("created", created), ("activated", activated), ("settled", settled)):
    for r in rows:
        if r["tunnel_id"] in live_ids:
            txs.add(r["tx"])
balances_unchanged = 0
for s in live:
    try:
        o = json.loads(base64.b64decode(s["outcome"]))
        st = o.get("state", {})
        b = st.get("balances")
        if b and len(set(b)) == 1:
            balances_unchanged += 1
    except Exception:  # noqa: BLE001
        pass

summary = {
    "tunnels_created_total": len(created),
    "tunnels_created_by_day": dict(sorted(collections.Counter(c["ts"][:10] for c in created).items())),
    "tunnels_settled_total": len(settled),
    "disputes_opened_total": len(disputes),
    "dispositions_all": dict(collections.Counter(s["disp"] for s in sessions)),
    "excluded_sentinel_timestamps_by_disp_live": {f"disp{k[0]}_live{k[1]}": v for k, v in invalid_ts.items()},
    "receipts_all_time": sum(s["n"] for s in sessions),
    "live": {
        "tunnels": len(live), "tunnels_running": len(running),
        "receipts_total": sum(s["n"] for s in live),
        "first_activation": iso(min(s["start"] for s in live)),
        "last_terminal": iso(max(s["end"] for s in live)),
        "last_settlement": iso(max(s["settled"] for s in live)),
        "peak_reconstructed_tps": round(per[peak_sec]),
        "peak_second_utc": iso(peak_sec * 1000),
        "tunnels_active_at_peak": conc,
        "seconds_above_10M": sum(1 for v in per.values() if v >= 10e6),
        "seconds_above_20M": sum(1 for v in per.values() if v >= 20e6),
        "session_seconds_median": med(durs), "session_seconds_p90": durs[int(len(durs) * .9)] if durs else None,
        "per_tunnel_tps_median": round(med(rates)), "per_tunnel_tps_p99": round(rates[int(len(rates) * .99)]),
        "receipts_max_single_tunnel": max(s["n"] for s in live),
        "domains": dict(collections.Counter(s["domain"] for s in live).most_common()),
        "receipts_by_domain": dict(sorted(((d, sum(s["n"] for s in live if s["domain"] == d)) for d in {s["domain"] for s in live}), key=lambda x: -x[1])),
        "dispositions": dict(collections.Counter(s["disp"] for s in live)),
        "evidence_class": dict(collections.Counter(s["ev"] for s in live)),
        "onchain_txs_open_activate_settle": len(txs),
        "tunnels_with_equal_final_balances": balances_unchanged,
    },
}
json.dump(summary, open(os.path.join(out, "summary.json"), "w"), indent=2)
print(json.dumps(summary, indent=2))
