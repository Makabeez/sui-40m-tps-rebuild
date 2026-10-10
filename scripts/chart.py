"""Chart: reconstructed effective TPS (from mainnet records) vs numbers called on stage.

Usage: python3 chart.py CURVE_CSV OUT_PNG
"""
import csv, datetime as dt, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0"
S1, S2 = "#2a78d6", "#eb6834"

rows = list(csv.DictReader(open(sys.argv[1])))
t = [dt.datetime.fromisoformat(r["utc"]) for r in rows]
v = [int(r["reconstructed_tps"]) / 1e6 for r in rows]
lo, hi = dt.datetime(2026, 10, 7, 8, 41, 0, tzinfo=dt.timezone.utc), dt.datetime(2026, 10, 7, 8, 54, 0, tzinfo=dt.timezone.utc)
t, v = zip(*[(a, b) for a, b in zip(t, v) if lo <= a <= hi])

# Numbers Adeniyi Abiodun called out on the Day 1 livestream (VOD 1e-cW4yBdMA), stream offset -> UTC
# using offset 03:00:22 (anchored on the "40 million" call at 05:45:48).
OFF = dt.timedelta(hours=3, seconds=22)
calls = [("05:42:26", 1.2), ("05:43:00", 2.6), ("05:43:45", 6), ("05:43:59", 13), ("05:44:23", 15),
         ("05:44:25", 17), ("05:44:37", 20), ("05:44:53", 26), ("05:45:13", 30), ("05:45:16", 34),
         ("05:45:26", 37), ("05:45:37", 39), ("05:45:48", 40)]
base = dt.datetime(2026, 10, 7, tzinfo=dt.timezone.utc)
ct = [base + dt.timedelta(hours=int(s[:2]), minutes=int(s[3:5]), seconds=int(s[6:])) + OFF for s, _ in calls]
cv = [x for _, x in calls]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13})
fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150)
fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
ax.plot(t, v, color=S1, lw=2.2, label="Rebuilt from mainnet records", zorder=2, drawstyle="steps-post")
ax.scatter(ct, cv, s=64, color=S2, edgecolor=SURF, linewidth=2, zorder=3, label="Called on stage")
ax.axhline(40.61418, color=MUTED, lw=1, ls=(0, (4, 4)), zorder=1)
ax.text(t[-1], 40.61418 + 0.7, "Official record: 40,614,180 TPS", ha="right", va="bottom", color=INK2, fontsize=11)
pk = max(range(len(v)), key=v.__getitem__)
ax.annotate(f"Reconstructed peak {v[pk]:.2f}M\n7,680 tunnels live × ~5.2k receipts/s each",
            xy=(t[pk] + dt.timedelta(seconds=60), v[pk]), xytext=(t[pk] + dt.timedelta(seconds=30), 17), color=INK, fontsize=11,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=1))
ax.annotate("Tunnels close,\nthroughput unwinds", xy=(t[-75], v[-75]), xytext=(hi - dt.timedelta(seconds=8), 27), ha="right",
            color=INK2, fontsize=11, arrowprops=dict(arrowstyle="-", color=MUTED, lw=1))
ax.set_ylim(0, 46); ax.set_xlim(lo, hi)
ax.xaxis.set_major_locator(mdates.MinuteLocator(tz=dt.timezone.utc))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=dt.timezone.utc))
ax.set_xlabel("7 Oct 2026, UTC (16:41 SGT = 08:41 UTC)", color=INK2)
ax.set_ylabel("Effective TPS (millions)", color=INK2)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color(GRID)
ax.tick_params(colors=INK2, length=0)
ax.grid(axis="y", color=GRID, lw=1); ax.set_axisbelow(True)
ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.70), frameon=False, labelcolor=INK, fontsize=11)
fig.suptitle("Sui's 40M TPS run, rebuilt from onchain data", x=0.06, ha="left", fontsize=18, color=INK, y=0.975)
ax.set_title("Each tunnel's receipt_count spread over its activation→terminal window, summed per second",
             loc="left", color=INK2, fontsize=11.5, pad=10)
fig.text(0.06, 0.015, "Data: 8,273 live tunnels, package 0x9498…7eb1 on Sui mainnet (384 zero-receipt tunnels excluded). Analysis: @GeiserJoe2",
         color=MUTED, fontsize=9.5)
fig.tight_layout(rect=(0, 0.03, 1, 0.965))
fig.savefig(sys.argv[2], facecolor=SURF)
print("ok")
