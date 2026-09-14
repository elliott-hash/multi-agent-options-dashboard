from __future__ import annotations

import csv
import os
import random
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from agents import VolumeLeadAgent, EntryAgent, NoiseFilterAgent, LiquidityDepthAgent, SupervisorAgent
from data_source import SimulatedOptionsData
from ledger import PaperLedger

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Multi-Agent Options Dashboard", version="2.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

security = HTTPBasic()
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")


def require_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    if not DASHBOARD_USERNAME or not DASHBOARD_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard authentication is not configured",
        )

    username_ok = secrets.compare_digest(credentials.username, DASHBOARD_USERNAME)
    password_ok = secrets.compare_digest(credentials.password, DASHBOARD_PASSWORD)

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


specialists = [VolumeLeadAgent(), EntryAgent(), NoiseFilterAgent(), LiquidityDepthAgent()]
supervisor = SupervisorAgent()


def run_scan(seed: int | None = None) -> dict[str, Any]:
    if seed is None:
        seed = random.randint(1, 1_000_000)

    source = SimulatedOptionsData(seed=seed)
    ledger = PaperLedger(output_dir=str(OUTPUT_DIR))
    signal_rows: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    for snap in source.get_option_snapshots():
        results = [agent.evaluate(snap) for agent in specialists]
        decision = supervisor.evaluate(
            snap,
            results,
            ledger.open_positions,
            ledger.modeled_daily_pnl,
        )

        score_map = {r.name: r.score for r in results}
        pass_map = {r.name: r.passed for r in results}
        rationale_map = {r.name: r.rationale for r in results}

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
            "volume_pass": pass_map["volume_lead"],
            "entry_pass": pass_map["entry"],
            "noise_pass": pass_map["noise_filter"],
            "liquidity_pass": pass_map["liquidity_depth"],
            "supervisor_rationale": decision.rationale,
            "volume_rationale": rationale_map["volume_lead"],
            "entry_rationale": rationale_map["entry"],
            "noise_rationale": rationale_map["noise_filter"],
            "liquidity_rationale": rationale_map["liquidity_depth"],
        })

        signal_rows.append(row)
        decisions.append(row)

        if decision.approved:
            ledger.add_trade(snap, decision)

    signal_rows.sort(key=lambda x: x["composite_score"], reverse=True)
    approved = [r for r in signal_rows if r["approved"]]

    path = OUTPUT_DIR / "latest_scan.csv"
    if signal_rows:
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=signal_rows[0].keys())
            writer.writeheader()
            writer.writerows(signal_rows)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "PAPER / SIMULATED DATA",
        "seed": seed,
        "summary": {
            "reviewed": len(signal_rows),
            "approved": len(approved),
            "rejected": len(signal_rows) - len(approved),
            "best_score": max((r["composite_score"] for r in signal_rows), default=0),
        },
        "signals": signal_rows,
        "paper_positions": ledger.positions,
    }


@app.get("/", response_class=HTMLResponse)
def home(_: str = Depends(require_auth)) -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text())


@app.get("/api/scan")
def api_scan(
    seed: int | None = None,
    _: str = Depends(require_auth),
) -> JSONResponse:
    return JSONResponse(run_scan(seed))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "paper"}
