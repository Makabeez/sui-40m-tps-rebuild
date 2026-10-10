"""Fetch every SettledOutcomeRecord referenced by ArenaTunnelSettled events.

Usage: python3 fetch_records.py SETTLED_JSONL OUT_JSONL
"""
import json, os, ssl, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = "https://graphql.mainnet.sui.io/graphql"
CTX = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
Q = "query($k:[ObjectKey!]!){ multiGetObjects(keys:$k){ address asMoveObject{ contents{ json } } } }"
KEEP = ["tunnel_id", "protocol_id", "disposition", "terminal_nonce", "terminal_timestamp", "receipt_count",
        "outcome", "entitlements", "total_settled", "settled_at_ms", "evidence_class", "transcript_root"]


def gql(ids):
    body = json.dumps({"query": Q, "variables": {"k": [{"address": i} for i in ids]}}).encode()
    for attempt in range(8):
        try:
            req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, context=CTX, timeout=90) as r:
                d = json.load(r)
            if "errors" in d:
                raise RuntimeError(str(d["errors"])[:300])
            return d["data"]["multiGetObjects"]
        except Exception as e:  # noqa: BLE001
            print("retry", attempt, e, file=sys.stderr, flush=True)
            time.sleep(3 * (attempt + 1))
    return []


def main():
    src, dst = sys.argv[1], sys.argv[2]
    ids = [json.loads(l)["record_id"] for l in open(src)]
    chunks = [ids[i:i + 50] for i in range(0, len(ids), 50)]
    done = 0
    with open(dst, "w") as f, ThreadPoolExecutor(4) as ex:
        for res in ex.map(gql, chunks):
            for o in res:
                if not o or not o.get("asMoveObject"):
                    continue
                j = o["asMoveObject"]["contents"]["json"]
                f.write(json.dumps({"record_id": o["address"], **{k: j.get(k) for k in KEEP}}) + "\n")
            done += 1
            if done % 50 == 0:
                print("chunks", done, "/", len(chunks), file=sys.stderr, flush=True)
    print("done", len(ids))


if __name__ == "__main__":
    main()
