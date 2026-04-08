import pandas as pd
import yfinance as yf


def fetch_yahoo_ohlcv(
    ticker: str = "BTC-USD",
    start: str = "2022-01-01",
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Fetch OHLCV data from Yahoo Finance and normalize columns.
    """
    data = yf.download(tickers=ticker, start=start, interval=interval, auto_adjust=False)
    data = data.reset_index()
    rename_map = {
        "Date": "timestamp",
        "Datetime": "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }
    data = data.rename(columns=rename_map)
    if "timestamp" in data.columns:
        data["timestamp"] = pd.to_datetime(data["timestamp"])
    data["source"] = "yahoo"
    data["symbol"] = ticker
    data["interval"] = interval
    return data
