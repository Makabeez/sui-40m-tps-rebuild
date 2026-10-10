"""Crawl every event of the MillionTPS arena-tunnel package from Sui mainnet GraphQL.

Usage: python3 crawl_events.py OUT_DIR
Writes one JSONL file per event type: OUT_DIR/<EventName>.jsonl
"""
import json, os, ssl, sys, time, urllib.request

PKG = "0x9498606724aa4c03dd0e50ce508b3f5555c4915d3f8d0d4525c0f98dd1737eb1"
URL = "https://graphql.mainnet.sui.io/graphql"
EVENTS = [
    "anchor::ArenaTunnelCreated",
    "anchor::ArenaTunnelActivated",
    "anchor::ArenaTunnelSettled",
    "anchor::ArenaTunnelOpeningCancelled",
    "anchor::ArenaDisputeOpened",
    "anchor::ArenaCheckpointAdopted",
    "anchor::ArenaSeatFunded",
    "outcome_records::HandOutcomeRecordPublished",
    "outcome_records::ActionOutcomeRecordPublished",
    "agent_allowance::AllowanceCreated",
    "agent_allowance::AllowanceClaimed",
    "streaming_payment::StreamCreated",
]
CTX = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)

Q = """query($t:String!,$after:String){ events(first:50, after:$after, filter:{type:$t}) {
  pageInfo{hasNextPage endCursor}
  nodes { timestamp contents { json } transaction { digest } } } }"""


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    for attempt in range(6):
        try:
            req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
                d = json.load(r)
            if "errors" in d:
                raise RuntimeError(d["errors"])
            return d["data"]
        except Exception as e:  # noqa: BLE001
            print("retry", attempt, e, file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    raise SystemExit("giving up")


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for ev in EVENTS:
        name = ev.split("::")[1]
        path = os.path.join(out, name + ".jsonl")
        n, after = 0, None
        with open(path, "w") as f:
            while True:
                d = gql(Q, {"t": f"{PKG}::{ev}", "after": after})["events"]
                for node in d["nodes"]:
                    f.write(json.dumps({"ts": node["timestamp"], "tx": node["transaction"]["digest"],
                                        **node["contents"]["json"]}) + "\n")
                    n += 1
                if not d["pageInfo"]["hasNextPage"]:
                    break
                after = d["pageInfo"]["endCursor"]
                if n % 2000 == 0:
                    print(name, n, file=sys.stderr, flush=True)
        print(name, n, flush=True)


if __name__ == "__main__":
    main()
