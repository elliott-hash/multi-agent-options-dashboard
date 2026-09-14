from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class OptionSnapshot:
    symbol: str
    contract: str
    option_type: str
    strike: float
    expiry: str
    underlying_price: float
    option_mid: float
    bid: float
    ask: float
    volume: int
    expected_volume: float
    open_interest: int
    volume_5m: int
    prior_volume_5m: int
    underlying_return_5m: float
    option_return_5m: float
    trades_at_ask_ratio: float
    trades_at_bid_ratio: float
    vwap_distance_pct: float
    momentum_score: float
    support_distance_pct: float
    resistance_distance_pct: float
    iv_percentile: float
    earnings_flag: bool
    single_print_share: float
    bid_size: int
    ask_size: int
    depth_3_levels: int
    estimated_slippage_pct: float

    def spread_pct(self) -> float:
        if self.option_mid <= 0:
            return 1.0
        return max(self.ask - self.bid, 0) / self.option_mid

    def relative_volume(self) -> float:
        if self.expected_volume <= 0:
            return 0.0
        return self.volume / self.expected_volume

    def as_dict(self) -> Dict:
        d = asdict(self)
        d["spread_pct"] = self.spread_pct()
        d["relative_volume"] = self.relative_volume()
        return d


@dataclass
class AgentResult:
    name: str
    score: float
    passed: bool
    rationale: str


@dataclass
class SupervisorDecision:
    approved: bool
    composite_score: float
    max_contracts: int
    entry_low: float
    entry_high: float
    rationale: str
