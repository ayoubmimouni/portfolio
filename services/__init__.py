"""Service layer: data access and session state.

`catalog`   static ETF universe metadata (mirrors api.ETF_METADATA)
`api_client` typed client for the FastAPI optimizer backend
`market`    cached market data and derived technical indicators
`store`     session-scoped application state (paper account, watchlist, alerts)

The optimizer and forecaster business logic lives in `backend/` and is reached
only through the HTTP API — this layer never duplicates it.
"""
