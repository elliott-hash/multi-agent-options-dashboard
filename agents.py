from config import CONFIG
from models import OptionSnapshot, AgentResult, SupervisorDecision


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


class VolumeLeadAgent:
    name = "volume_lead"

    def evaluate(self, s: OptionSnapshot) -> AgentResult:
        rv = s.relative_volume()
        accel = s.volume_5m / max(s.prior_volume_5m, 1)
        price_lag = max(0.0, 1.0 - abs(s.underlying_return_5m) / 0.01)
        ask_pressure = s.trades_at_ask_ratio if s.option_type == "CALL" else s.trades_at_bid_ratio

        score = (
            min(rv / 6.0, 1.0) * 40
            + min(accel / 3.0, 1.0) * 25
            + price_lag * 20
            + min(ask_pressure / 0.75, 1.0) * 15
        )
        passed = rv >= CONFIG.min_relative_volume and accel >= 1.25
        rationale = f"RVOL {rv:.1f}x; 5m volume acceleration {accel:.2f}x; price lag factor {price_lag:.2f}; directional print pressure {ask_pressure:.0%}."
        return AgentResult(self.name, clamp(score), passed, rationale)


class EntryAgent:
    name = "entry"

    def evaluate(self, s: OptionSnapshot) -> AgentResult:
        spread_component = max(0.0, 1.0 - s.spread_pct() / max(CONFIG.max_spread_pct, 0.001))
        vwap_component = max(0.0, 1.0 - abs(s.vwap_distance_pct) / 0.015)
        momentum_component = clamp(s.momentum_score, 0, 1)
        chase_penalty = min(abs(s.option_return_5m) / 0.20, 1.0)

        score = (
            spread_component * 30
            + vwap_component * 25
            + momentum_component * 30
            + (1.0 - chase_penalty) * 15
        )
        passed = s.spread_pct() <= CONFIG.max_spread_pct and chase_penalty < 0.85
        rationale = f"Spread {s.spread_pct():.1%}; VWAP distance {s.vwap_distance_pct:.2%}; momentum {s.momentum_score:.2f}; chase penalty {chase_penalty:.2f}."
        return AgentResult(self.name, clamp(score), passed, rationale)


class NoiseFilterAgent:
    name = "noise_filter"

    def evaluate(self, s: OptionSnapshot) -> AgentResult:
        oi_component = min(s.open_interest / 1500.0, 1.0)
        print_quality = max(0.0, 1.0 - s.single_print_share)
        iv_quality = max(0.0, 1.0 - max(s.iv_percentile - 85, 0) / 15)
        earnings_quality = 0.0 if s.earnings_flag else 1.0

        score = oi_component * 30 + print_quality * 30 + iv_quality * 20 + earnings_quality * 20
        passed = (
            s.open_interest >= CONFIG.min_open_interest
            and s.single_print_share <= 0.65
            and not s.earnings_flag
        )
        rationale = f"OI {s.open_interest}; largest-print share {s.single_print_share:.0%}; IV percentile {s.iv_percentile:.0f}; earnings flag {s.earnings_flag}."
        return AgentResult(self.name, clamp(score), passed, rationale)


class LiquidityDepthAgent:
    name = "liquidity_depth"

    def evaluate(self, s: OptionSnapshot) -> AgentResult:
        spread_component = max(0.0, 1.0 - s.spread_pct() / 0.08)
        depth_component = min(s.depth_3_levels / 250.0, 1.0)
        top_component = min((s.bid_size + s.ask_size) / 100.0, 1.0)
        slippage_component = max(0.0, 1.0 - s.estimated_slippage_pct / 0.05)

        score = spread_component * 30 + depth_component * 30 + top_component * 15 + slippage_component * 25
        passed = (
            s.spread_pct() <= CONFIG.max_spread_pct
            and s.depth_3_levels >= CONFIG.min_book_depth_contracts
            and s.estimated_slippage_pct <= 0.04
        )
        rationale = f"Spread {s.spread_pct():.1%}; top sizes {s.bid_size}/{s.ask_size}; 3-level depth {s.depth_3_levels}; est. slippage {s.estimated_slippage_pct:.1%}."
        return AgentResult(self.name, clamp(score), passed, rationale)


class SupervisorAgent:
    name = "supervisor"

    def evaluate(self, s: OptionSnapshot, results: list[AgentResult], open_positions: int, modeled_daily_pnl: float) -> SupervisorDecision:
        score_map = {r.name: r.score for r in results}
        composite = (
            score_map["volume_lead"] * CONFIG.weight_volume
            + score_map["entry"] * CONFIG.weight_entry
            + score_map["noise_filter"] * CONFIG.weight_noise
            + score_map["liquidity_depth"] * CONFIG.weight_liquidity
        )

        hard_pass = all(r.passed for r in results)
        daily_loss_limit = -CONFIG.account_equity * CONFIG.max_daily_loss_pct
        risk_ok = open_positions < CONFIG.max_concurrent_positions and modeled_daily_pnl > daily_loss_limit
        approved = hard_pass and risk_ok and composite >= CONFIG.supervisor_min_score

        risk_dollars = CONFIG.account_equity * CONFIG.max_risk_per_trade_pct
        # Options multiplier = 100. Conservative assumption: premium can go to zero.
        per_contract_risk = max(s.ask * 100, 1)
        max_contracts = int(risk_dollars // per_contract_risk) if approved else 0
        max_contracts = max(1, max_contracts) if approved else 0

        entry_low = round(max(s.bid, s.option_mid * 0.98), 2)
        entry_high = round(min(s.ask, s.option_mid * 1.02), 2)
        rationale = f"Composite {composite:.1f}; hard filters {'PASS' if hard_pass else 'FAIL'}; portfolio risk {'PASS' if risk_ok else 'FAIL'}."
        return SupervisorDecision(approved, composite, max_contracts, entry_low, entry_high, rationale)
