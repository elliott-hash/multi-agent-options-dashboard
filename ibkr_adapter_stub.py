"""IBKR integration placeholder.

Do not enable live order placement in V1. Implement market-data ingestion here later.
The adapter should normalize broker data into models.OptionSnapshot objects.

Typical fields needed:
- underlying last / VWAP / intraday returns
- option bid, ask, volume, open interest, implied volatility
- recent trade direction / prints
- Level II or depth-of-book snapshots where available

Once connected, replace SimulatedOptionsData in main.py with an IBKRMarketData class
that implements data_source.MarketDataSource.
"""
