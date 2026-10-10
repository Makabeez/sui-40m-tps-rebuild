#!/usr/bin/env sh
# Rebuild Sui's 40M TPS record from mainnet data, end to end.
set -e
cd "$(dirname "$0")"
python3 scripts/crawl_events.py data/events
python3 scripts/fetch_records.py data/events/ArenaTunnelSettled.jsonl data/records.jsonl
python3 scripts/analyze.py data out
python3 scripts/footprint.py data out/footprint.json
if python3 -c "import matplotlib" 2>/dev/null; then
  python3 scripts/chart.py out/curve_live.csv out/tps_reconstructed.png
else
  echo "matplotlib not installed; skipping chart (pip install matplotlib)"
fi
