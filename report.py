from pathlib import Path
from datetime import datetime
import csv


def write_signal_rows(rows, output_dir="output"):
    p = Path(output_dir)
    p.mkdir(exist_ok=True)
    path = p / "signals.csv"
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def write_daily_report(decisions, output_dir="output"):
    p = Path(output_dir)
    p.mkdir(exist_ok=True)
    approved = [d for d in decisions if d["approved"]]
    lines = [
        "MULTI-AGENT OPTIONS PAPER TRADING REPORT",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Signals reviewed: {len(decisions)}",
        f"Approved opportunities: {len(approved)}",
        "",
    ]

    for d in sorted(decisions, key=lambda x: x["composite_score"], reverse=True):
        lines += [
            f"{d['contract']} — {'APPROVED' if d['approved'] else 'REJECTED'}",
            f"  Composite: {d['composite_score']:.1f}/100",
            f"  Volume: {d['volume_score']:.1f} | Entry: {d['entry_score']:.1f} | Noise: {d['noise_score']:.1f} | Liquidity: {d['liquidity_score']:.1f}",
            f"  Entry zone: ${d['entry_low']:.2f}-${d['entry_high']:.2f}",
            f"  Max paper contracts: {d['max_contracts']}",
            f"  Supervisor: {d['supervisor_rationale']}",
            "",
        ]

    (p / "daily_report.txt").write_text("\n".join(lines))
