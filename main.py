from agents import VolumeLeadAgent, EntryAgent, NoiseFilterAgent, LiquidityDepthAgent, SupervisorAgent
from data_source import SimulatedOptionsData
from ledger import PaperLedger
from report import write_signal_rows, write_daily_report


def run():
    source = SimulatedOptionsData(seed=42)
    ledger = PaperLedger()
    specialists = [VolumeLeadAgent(), EntryAgent(), NoiseFilterAgent(), LiquidityDepthAgent()]
    supervisor = SupervisorAgent()

    signal_rows = []
    decisions = []

    for snap in source.get_option_snapshots():
        results = [agent.evaluate(snap) for agent in specialists]
        decision = supervisor.evaluate(snap, results, ledger.open_positions, ledger.modeled_daily_pnl)

        score_map = {r.name: r.score for r in results}
        row = snap.as_dict()
        row.update({
            "volume_score": round(score_map["volume_lead"], 1),
            "entry_score": round(score_map["entry"], 1),
            "noise_score": round(score_map["noise_filter"], 1),
            "liquidity_score": round(score_map["liquidity_depth"], 1),
            "composite_score": round(decision.composite_score, 1),
            "approved": decision.approved,
            "entry_low": decision.entry_low,
            "entry_high": decision.entry_high,
            "max_contracts": decision.max_contracts,
        })
        signal_rows.append(row)

        decisions.append({
            "contract": snap.contract,
            "approved": decision.approved,
            "composite_score": decision.composite_score,
            "volume_score": score_map["volume_lead"],
            "entry_score": score_map["entry"],
            "noise_score": score_map["noise_filter"],
            "liquidity_score": score_map["liquidity_depth"],
            "entry_low": decision.entry_low,
            "entry_high": decision.entry_high,
            "max_contracts": decision.max_contracts,
            "supervisor_rationale": decision.rationale,
        })

        if decision.approved:
            ledger.add_trade(snap, decision)

    write_signal_rows(signal_rows)
    write_daily_report(decisions)

    approved = [d for d in decisions if d["approved"]]
    print(f"Reviewed {len(decisions)} contracts. Approved {len(approved)} paper trades.")
    for d in sorted(approved, key=lambda x: x["composite_score"], reverse=True):
        print(f"  {d['contract']}: {d['composite_score']:.1f}/100, entry ${d['entry_low']:.2f}-${d['entry_high']:.2f}, max {d['max_contracts']} contracts")
    print("Reports written to output/")


if __name__ == "__main__":
    run()
