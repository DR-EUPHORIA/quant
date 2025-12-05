import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

# 1. 下载 BTC-USD 的日线数据
data = yf.download(
    tickers="BTC-USD",
    start="2022-01-01",
    interval="1d"
)

# 2. 重置索引，统一列名
data = data.reset_index()
data = data.rename(columns={
    "Date": "timestamp",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
})

print(data.head())

# 3. 画收盘价
plt.plot(data["timestamp"], data["close"])
plt.title("BTC-USD Close Price (Yahoo Finance)")
plt.xlabel("Date")
plt.ylabel("Close")
plt.tight_layout()
plt.show()
