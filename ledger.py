from pathlib import Path
from datetime import datetime
import csv


class PaperLedger:
    def __init__(self, output_dir="output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.positions = []
        self.modeled_daily_pnl = 0.0

    @property
    def open_positions(self):
        return sum(1 for p in self.positions if p.get("status") == "OPEN")

    def add_trade(self, snapshot, decision):
        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "symbol": snapshot.symbol,
            "contract": snapshot.contract,
            "side": "BUY",
            "contracts": decision.max_contracts,
            "entry_low": decision.entry_low,
            "entry_high": decision.entry_high,
            "score": round(decision.composite_score, 1),
            "status": "OPEN",
        }
        self.positions.append(row)
        path = self.output_dir / "paper_trades.csv"
        write_header = not path.exists()
        with path.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=row.keys())
            if write_header:
                w.writeheader()
            w.writerow(row)
