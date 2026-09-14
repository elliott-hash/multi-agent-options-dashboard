from abc import ABC, abstractmethod
from datetime import date, timedelta
import random
from models import OptionSnapshot


class MarketDataSource(ABC):
    @abstractmethod
    def get_option_snapshots(self) -> list[OptionSnapshot]:
        raise NotImplementedError


class SimulatedOptionsData(MarketDataSource):
    """Produces deterministic-ish sample data for paper testing.

    Replace this class with a broker/data adapter when live market data is connected.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def get_option_snapshots(self) -> list[OptionSnapshot]:
        names = [("NVDA", 190.0), ("AAPL", 240.0), ("TSLA", 320.0), ("AMD", 175.0), ("META", 610.0), ("SPY", 650.0)]
        expiry = str(date.today() + timedelta(days=32))
        out = []
        for idx, (sym, px) in enumerate(names):
            hot = idx in (0, 3, 5)
            strike = round(px * (1.02 if idx % 2 == 0 else 0.98) / 5) * 5
            mid = round(max(0.75, px * self.rng.uniform(0.012, 0.03)), 2)
            spread = mid * (self.rng.uniform(0.015, 0.04) if hot else self.rng.uniform(0.04, 0.12))
            bid = round(mid - spread / 2, 2)
            ask = round(mid + spread / 2, 2)
            exp_vol = self.rng.randint(300, 1000)
            rel = self.rng.uniform(3.5, 7.0) if hot else self.rng.uniform(0.5, 2.5)
            vol = int(exp_vol * rel)
            prior5 = self.rng.randint(30, 120)
            v5 = int(prior5 * (self.rng.uniform(1.5, 3.5) if hot else self.rng.uniform(0.6, 1.4)))

            out.append(OptionSnapshot(
                symbol=sym,
                contract=f"{sym} {expiry} {strike:.0f}{'C' if idx % 2 == 0 else 'P'}",
                option_type="CALL" if idx % 2 == 0 else "PUT",
                strike=float(strike),
                expiry=expiry,
                underlying_price=round(px * self.rng.uniform(0.99, 1.01), 2),
                option_mid=mid,
                bid=bid,
                ask=ask,
                volume=vol,
                expected_volume=float(exp_vol),
                open_interest=self.rng.randint(500, 5000) if hot else self.rng.randint(50, 1000),
                volume_5m=v5,
                prior_volume_5m=prior5,
                underlying_return_5m=self.rng.uniform(-0.004, 0.004) if hot else self.rng.uniform(-0.015, 0.015),
                option_return_5m=self.rng.uniform(-0.04, 0.08) if hot else self.rng.uniform(-0.15, 0.25),
                trades_at_ask_ratio=self.rng.uniform(0.62, 0.86) if hot else self.rng.uniform(0.35, 0.65),
                trades_at_bid_ratio=self.rng.uniform(0.62, 0.86) if (hot and idx % 2 == 1) else self.rng.uniform(0.35, 0.65),
                vwap_distance_pct=self.rng.uniform(-0.006, 0.009) if hot else self.rng.uniform(-0.03, 0.03),
                momentum_score=self.rng.uniform(0.72, 0.95) if hot else self.rng.uniform(0.25, 0.75),
                support_distance_pct=self.rng.uniform(0.002, 0.02),
                resistance_distance_pct=self.rng.uniform(0.002, 0.02),
                iv_percentile=self.rng.uniform(35, 78) if hot else self.rng.uniform(20, 98),
                earnings_flag=False if hot else self.rng.choice([False, False, True]),
                single_print_share=self.rng.uniform(0.08, 0.45) if hot else self.rng.uniform(0.2, 0.85),
                bid_size=self.rng.randint(20, 80) if hot else self.rng.randint(1, 30),
                ask_size=self.rng.randint(20, 80) if hot else self.rng.randint(1, 30),
                depth_3_levels=self.rng.randint(100, 400) if hot else self.rng.randint(10, 120),
                estimated_slippage_pct=self.rng.uniform(0.005, 0.025) if hot else self.rng.uniform(0.02, 0.08),
            ))
        return out
