import requests
import pandas as pd
import matplotlib.pyplot as plt

# === 对照 OKX 官方文档 ===
# REST URL: https://www.okx.com/api/v5/market/candles
# Method: GET
# Params:
#   instId: 交易对，如 BTC-USDT
#   bar:    K 线周期，如 1m, 5m, 1H, 1D
#   limit:  返回条数（可选）
#   after / before: 翻页时间戳（可选）
# 返回 data:
#   [
#     [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm],
#     ...
#   ]

BASE_URL = "https://www.okx.com"

def fetch_okx_candles(
    instId="BTC-USDT",
    bar="1D",
    limit=200
):
    """
    读取 OKX K 线（对照官方文档编写）
    """
    url = BASE_URL + "/api/v5/market/candles"
    params = {
        "instId": instId,
        "bar": bar,
        "limit": str(limit)
    }

    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print("请求失败：", type(e).__name__, e)
        return None

    raw = resp.json()

    # 结构必须包含 data 字段
    if "data" not in raw:
        print("返回数据无 data 字段：", raw)
        return None

    data = raw["data"]

    # 按文档字段顺序建立 DataFrame
    df = pd.DataFrame(
        data,
        columns=[
            "ts", "open", "high", "low", "close",
            "volume", "volCcy", "volCcyQuote", "confirm"
        ]
    )

    # 文档说明 ts 是毫秒时间戳
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms")

    # 按时间正序排列
    df = df.sort_values("ts")

    # 转 float（OKX 返回的是字符串）
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df


# === 主流程 ===
df = fetch_okx_candles("BTC-USDT", "1D", 200)

if df is not None:
    print(df.head())

    # 画图
    plt.plot(df["ts"], df["close"])
    plt.title("OKX BTC-USDT 1D Candlestick (REST API)")
    plt.xlabel("Time")
    plt.ylabel("Close Price")
    plt.tight_layout()
    plt.show()

    # 保存数据
    df.to_csv("okx_btc_usdt_1d.csv", index=False)
    print("数据已保存到 okx_btc_usdt_1d.csv")
else:
    print("未能成功获取 K 线")
