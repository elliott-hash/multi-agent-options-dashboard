from __future__ import annotations

import os
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import databento as db

from models import OptionSnapshot

OCC_RE = re.compile(r"^([A-Z0-9.]+)\s+(\d{6})([CP])(\d{8})$")


def _f(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        if value != value or abs(value) > 1e100:
            return default
        return value
    except Exception:
        return default


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def parse_occ(raw: str) -> tuple[str, str, str, float] | None:
    m = OCC_RE.match(raw.strip())
    if not m:
        return None
    root, yymmdd, cp, strike8 = m.groups()
    expiry = datetime.strptime(yymmdd, "%y%m%d").date().isoformat()
    return root, expiry, "CALL" if cp == "C" else "PUT", int(strike8) / 1000.0


@dataclass
class _Trade:
    ts_ns: int
    price: float
    size: int
    bid: float
    ask: float
    bid_size: int
    ask_size: int


class DatabentoOptionsData:
    """Short live OPRA sampling adapter for the paper scanner.

    Uses Databento OPRA.PILLAR TCBBO: each option trade plus the consolidated
    NBBO immediately before that trade. OPRA does not provide universal L2
    depth, so this adapter reports top-of-book size only and deliberately does
    not claim true three-level depth.
    """

    def __init__(self, symbols: list[str] | None = None, sample_seconds: int = 12):
        self.key = os.getenv("DATABENTO_API_KEY")
        if not self.key:
            raise RuntimeError("DATABENTO_API_KEY is not configured")
        raw = os.getenv("SCAN_SYMBOLS", "AMD")
        self.symbols = symbols or [s.strip().upper() for s in raw.split(",") if s.strip()]
        self.sample_seconds = max(5, min(int(os.getenv("LIVE_SAMPLE_SECONDS", sample_seconds)), 30))
        self._maps: dict[int, str] = {}
        self._trades: dict[int, deque[_Trade]] = defaultdict(lambda: deque(maxlen=5000))
        self._lock = threading.Lock()

    def _on_record(self, msg: Any) -> None:
        # Symbol mappings arrive automatically for parent subscriptions.
        if isinstance(msg, db.SymbolMappingMsg):
            raw = getattr(msg, "stype_out_symbol", None)
            if raw:
                with self._lock:
                    self._maps[_i(msg.instrument_id)] = str(raw)
            return

        # TCBBO records expose trade price/size and consolidated BBO in levels[0].
        if not hasattr(msg, "price") or not hasattr(msg, "instrument_id"):
            return
        levels = getattr(msg, "levels", None)
        if not levels:
            return
        level = levels[0]
        trade = _Trade(
            ts_ns=_i(getattr(msg, "ts_event", 0)),
            price=_f(getattr(msg, "price", 0)),
            size=_i(getattr(msg, "size", 0)),
            bid=_f(getattr(level, "bid_px", 0)),
            ask=_f(getattr(level, "ask_px", 0)),
            bid_size=_i(getattr(level, "bid_sz", 0)),
            ask_size=_i(getattr(level, "ask_sz", 0)),
        )
        if trade.price <= 0 or trade.size <= 0:
            return
        with self._lock:
            self._trades[_i(msg.instrument_id)].append(trade)

    def _collect(self) -> None:
        client = db.Live(key=self.key, compression=db.Compression.ZSTD)
        for sym in self.symbols:
            client.subscribe(
                dataset="OPRA.PILLAR",
                schema="tcbbo",
                symbols=f"{sym}.OPT",
                stype_in="parent",
            )
        client.add_callback(self._on_record)
        client.start()
        client.block_for_close(timeout=self.sample_seconds)

    @staticmethod
    def _window_volume(rows: list[_Trade], start_ns: int, end_ns: int) -> int:
        return sum(t.size for t in rows if start_ns <= t.ts_ns < end_ns)

    def get_option_snapshots(self) -> list[OptionSnapshot]:
        self._collect()
        now_ns = time.time_ns()
        five = 5 * 60 * 1_000_000_000
        snapshots: list[OptionSnapshot] = []

        with self._lock:
            items = [(iid, list(rows)) for iid, rows in self._trades.items()]
            maps = dict(self._maps)

        for iid, rows in items:
            raw = maps.get(iid)
            parsed = parse_occ(raw or "")
            if not parsed or len(rows) < 2:
                continue
            root, expiry, option_type, strike = parsed
            if root not in self.symbols:
                continue

            rows.sort(key=lambda x: x.ts_ns)
            last = rows[-1]
            bid, ask = last.bid, last.ask
            if bid <= 0 or ask <= 0 or ask < bid:
                continue
            mid = (bid + ask) / 2

            v5 = self._window_volume(rows, now_ns - five, now_ns)
            prior5 = self._window_volume(rows, now_ns - 2 * five, now_ns - five)
            total = sum(t.size for t in rows)
            largest = max(t.size for t in rows)
            ask_vol = sum(t.size for t in rows if t.ask > 0 and t.price >= t.ask - 1e-9)
            bid_vol = sum(t.size for t in rows if t.bid > 0 and t.price <= t.bid + 1e-9)

            first_price = rows[0].price
            option_ret = (last.price / first_price - 1.0) if first_price > 0 else 0.0
            spread_pct = (ask - bid) / mid if mid > 0 else 1.0

            # During the first live integration we intentionally use only fields
            # OPRA/TCBBO can substantiate. Missing OI, IV percentile, earnings,
            # underlying return, and L2 depth are represented conservatively so
            # the supervisor cannot auto-approve a trade from incomplete data.
            snapshots.append(OptionSnapshot(
                symbol=root,
                contract=f"{root} {expiry} {strike:g}{'C' if option_type == 'CALL' else 'P'}",
                option_type=option_type,
                strike=strike,
                expiry=expiry,
                underlying_price=0.0,
                option_mid=mid,
                bid=bid,
                ask=ask,
                volume=total,
                expected_volume=max(float(prior5 * 2), 1.0),
                open_interest=0,
                volume_5m=v5,
                prior_volume_5m=prior5,
                underlying_return_5m=0.0,
                option_return_5m=option_ret,
                trades_at_ask_ratio=ask_vol / max(total, 1),
                trades_at_bid_ratio=bid_vol / max(total, 1),
                vwap_distance_pct=0.0,
                momentum_score=min(1.0, abs(option_ret) / 0.10),
                support_distance_pct=0.0,
                resistance_distance_pct=0.0,
                iv_percentile=100.0,
                earnings_flag=False,
                single_print_share=largest / max(total, 1),
                bid_size=last.bid_size,
                ask_size=last.ask_size,
                depth_3_levels=0,
                estimated_slippage_pct=min(1.0, spread_pct / 2),
            ))

        snapshots.sort(key=lambda s: (s.volume_5m, s.volume), reverse=True)
        return snapshots[:100]
