from dataclasses import dataclass


@dataclass(frozen=True)
class TradingConfig:
    account_equity: float = 100_000.0
    max_risk_per_trade_pct: float = 0.005
    max_daily_loss_pct: float = 0.02
    max_concurrent_positions: int = 5

    min_relative_volume: float = 3.0
    max_spread_pct: float = 0.05
    min_open_interest: int = 250
    min_book_depth_contracts: int = 50
    supervisor_min_score: float = 80.0

    # Weighting of the four specialist agents
    weight_volume: float = 0.30
    weight_entry: float = 0.25
    weight_noise: float = 0.20
    weight_liquidity: float = 0.25


CONFIG = TradingConfig()
