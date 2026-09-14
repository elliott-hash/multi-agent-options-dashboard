# Multi-Agent Options Dashboard — V2

A browser-based, paper-trading-only interface for the five-agent options scanner.

## What it does
- Detects contracts where volume accelerates before price.
- Scores entry quality.
- Filters noisy / low-quality flow.
- Tests spread, book depth, and estimated slippage.
- Uses a supervisor to approve/reject setups and write a paper ledger.

## Fastest local start

### Windows
1. Unzip the folder.
2. Double-click `start_windows.bat`.
3. Your browser should open to `http://127.0.0.1:8000`.

### Mac
1. Unzip the folder.
2. Double-click `start_mac.command`.
3. If macOS blocks it, right-click > Open once.
4. Your browser should open to `http://127.0.0.1:8000`.

The first launch installs the required Python packages.

## Current safety mode
The dashboard uses simulated options data and paper trades only. It does not send any brokerage orders.

## Cloud deployment
The included `Dockerfile` and `render.yaml` make the app ready for a Docker-capable host. The server command is:

`uvicorn app:app --host 0.0.0.0 --port $PORT`

## Next integration point
Replace `SimulatedOptionsData` with a live market-data adapter (for example IBKR or another options feed). Keep execution paper-only until the scanner has been validated on a meaningful out-of-sample sample.
