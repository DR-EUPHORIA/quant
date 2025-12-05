import ccxt
import pandas as pd
import matplotlib.pyplot as plt

# 1. 初始化 OKX 交易所（只用公共接口，不需要 API key）
exchange = ccxt.okx({
    'enableRateLimit': True,   # 防止请求过快被限流
    'timeout': 20000,          # 20 秒超时，避免网络略慢就挂
    'options': {
        'defaultType': 'spot', # 使用现货市场
    }
})

# 2. 加载市场信息（测试网络 + 确认交易对存在）
try:
    markets = exchange.load_markets()
    print("OKX markets loaded, total symbols:", len(markets))
except Exception as e:
    print("加载 OKX 市场信息失败：", type(e).__name__, e)
    exit(1)

# 3. 拉取 BTC/USDT 日线 K 线
symbol = 'BTC/USDT'   # ccxt 统一使用这种格式
timeframe = '1d'
limit = 500           # 最近 500 根 K 线（约 500 天）

try:
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
except Exception as e:
    print("获取 K 线失败：", type(e).__name__, e)
    exit(1)

# 4. 转为 DataFrame
df = pd.DataFrame(
    bars,
    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
)
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

print(df.head())

# 5. 画图
plt.plot(df['timestamp'], df['close'])
plt.title('OKX BTC/USDT Close Price (1d)')
plt.xlabel('Date')
plt.ylabel('Close')
plt.tight_layout()
plt.show()
