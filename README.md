# quant

> A-share quantitative research pipeline: data ingestion -> panel construction -> backtesting

本项目当前是一套以 **A 股日频研究** 为主的量化工程仓库，核心目标不是做完整生产系统，而是把研究常用的数据准备、面板构建、策略回测和结果导出做成一条可复现、可测试、可扩展的闭环。

当前主链路已经明确：

1. 从 TuShare 拉取原始数据
2. 构建 HS300 研究面板
3. 运行示例策略与因子分组测试
4. 输出标准化结果和质量检查报表

---

## 项目定位

这个仓库当前主要服务两个场景：

* **A 股研究原型验证**：快速验证因子、价格列、调仓频率、简单交易成本假设
* **工程化研究底座**：避免 notebook-only 工作流，把数据和回测流程固化成脚本与可测试模块

当前不是完整的生产交易系统，尤其在以下方面仍是研究级实现：

* 股票池已支持 **动态 HS300 成分历史过滤**，但默认研究口径仍偏单指数日频研究
* `stock_st` 下载链路已接入；若 TuShare 账号无权限，会保留空占位文件并降级运行
* 回测引擎偏向最小可用闭环，尚未覆盖更复杂的订单撮合与风控约束

---

## 当前仓库结构

```text
quant/
├── config/
│   ├── config_tushare.py
│   ├── paths.py
│   └── __init__.py
│
├── scripts/
│   ├── a_stock/
│   │   ├── download_hs300.py
│   │   ├── download_research_basics.py
│   │   ├── build_panel.py
│   │   ├── data_quality_check.py
│   │   ├── backtest_ma.py
│   │   ├── factor_test.py
│   │   ├── inspect_parquet.py
│   │   └── excel_to_csv.py
│   ├── crypto/
│   │   ├── get_data_okx.py
│   │   ├── okx_kline_rest.py
│   │   └── get_data_yf.py
│   └── env_check.py
│
├── src/
│   └── quantbt/
│       ├── engine.py
│       ├── metrics.py
│       ├── cost.py
│       ├── io.py
│       └── __init__.py
│
├── tests/
│   └── test_a_stock_scripts.py
│
├── data/
│   ├── tushare/
│   │   ├── raw/
│   │   └── processed/
│   ├── ifind/
│   └── okx/
│
├── results/
├── requirements.txt
├── Dockerfile
└── README.md
```

说明：

* `scripts/a_stock/` 是当前主工作流
* `src/quantbt/` 是回测核心模块
* `tests/test_a_stock_scripts.py` 已覆盖主 A 股脚本的 CLI 路径
* `scripts/crypto/` 和 `data/okx/` 目前更像探索性样例，不是主链路
* `data/ifind/` 是已有的人工导出 Excel 数据，不参与当前主回测流程

---

## 当前已完成能力

### 1. 数据拉取

已完成的 TuShare 数据抓取包括：

* 全市场日线行情 `daily`
* 全市场日度基本面 `daily_basic`
* HS300 最新成分快照 `hs300_constituents_latest`
* HS300 复权因子 `adj_factor`
* HS300 涨跌停价格 `stk_limit`
* HS300 动态成分与权重 `index_weight`
* HS300 停复牌信息 `suspend_d`
* A 股上市/退市/暂停上市基础信息 `stock_basic`
* HS300 指数基准行情 `index_daily`

当前未成功落地的唯一一项是：

* `stock_st`
  * 脚本已实现
  * 当前 TuShare 账号无接口权限
  * 因此仓库里只有一个空的占位 parquet

### 2. 面板构建

已完成两类研究面板：

* 基础面板：行情 + `daily_basic`
* 完整面板：在基础面板上补齐
  * `adj_factor`
  * 完整 `qfq_*` / `hfq_*` 价格列
  * `is_suspended`
  * `list_status` / `list_date` / `delist_date`
  * `is_listed_from_stock_basic`
  * `is_paused_listing`
  * `is_st`
  * `limit_up` / `limit_down`
  * `is_limit_up` / `is_limit_down`
  * `is_one_word_limit_up` / `is_one_word_limit_down`
  * `listed_days`
  * `is_new_listing_60d`
  * `ret_1d` / `ret_5d` / `ret_20d`
  * `volatility_20d`
  * `amount_ma20_ratio`
  * `turnover_rate_ma20_ratio`
  * `is_tradeable_buy` / `is_tradeable_sell`

### 3. 回测与研究

当前仓库已经有完整的脚本闭环：

* `backtest_ma.py`
  * 支持 `--price-col`
  * 默认使用 `qfq_close`
  * 可以直接用 `close` 或 `qfq_close`
  * 周 / 月调仓现在会在调仓日之间保持仓位
  * 会读取 `is_tradeable_buy` / `is_tradeable_sell`
  * 输出净值、收益、持仓、指标和图表
* `factor_test.py`
  * 支持横截面因子分组
  * 支持 `daily / weekly / monthly` 调仓
  * 默认使用 `qfq_close`
  * 分组时会过滤不可买入样本
  * 输出分组净值、Long-short 指标、IC 序列和图
* `data_quality_check.py`
  * 输出覆盖度、历史长度、缺失率和最新成分缺口检查

### 4. 测试

当前自动化测试已经覆盖以下 CLI 主路径：

* `build_panel.py`
* `backtest_ma.py`
* `factor_test.py`
* `data_quality_check.py`

测试文件：

* `tests/test_a_stock_scripts.py`

---

## 当前数据现状

### 主研究数据目录

主链路数据集中在 `data/tushare/`。

#### `data/tushare/raw/`

当前已实际落盘的核心 parquet：

* `daily_20150101_20241231.parquet`
  * 全市场 A 股日线行情
  * 约 `948` 万行
* `daily_basic_20150101_20241231.parquet`
  * 全市场日度估值、股本、流动性指标
  * 约 `936` 万行
* `adj_factor_hs300_20150101_20241231.parquet`
  * HS300 复权因子
  * 约 `64` 万行
* `hs300_constituents_latest.parquet`
  * HS300 最新成分快照
  * `300` 行
* `stk_limit_hs300_20150101_20241231.parquet`
  * HS300 涨跌停价格
  * `639,983` 行
* `000300_sh_index_weight_20150101_20241231.parquet`
  * HS300 动态成分与权重历史
  * `51,000` 行
* `suspend_d_hs300_20150101_20241231.parquet`
  * HS300 停复牌信息
  * `11,858` 行
* `stock_basic_all_status.parquet`
  * 上市 / 退市 / 暂停上市状态
  * `5,818` 行
* `index_daily_000300_SH_20150101_20241231.parquet`
  * 沪深300指数基准行情
  * `2,431` 行
* `stock_st_20160101_20241231.parquet`
  * ST 状态占位文件
  * 当前为空

#### `data/tushare/processed/`

* `hs300_panel_20150101_20241231.parquet`
  * 基础研究面板
  * `628,796 x 23`
* `hs300_panel_20150101_20241231_qfq.parquet`
  * 基础面板 + `adj_factor` + `qfq_close`
  * `628,796 x 25`
* `hs300_panel_20241225_20241231.parquet`
  * 小区间验证面板
  * `1,495 x 23`

#### `results/a_stock/panels/`

* `hs300_panel_20150101_20241231_full.parquet`
  * 当前最完整的研究面板
  * 含完整前复权 / 后复权价格、动态成分过滤、停牌 / ST / 上市状态和交易可达性字段

### 当前研究口径

* 频率：日频
* 时间范围：2015-01-01 到 2024-12-31
* 主键：`(ts_code, trade_date)`
* 默认股票池口径：**动态 HS300 成分历史**
* 默认研究价格列：`qfq_close`

---

## 环境准备

### 方式一：本地 venv

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

可选环境检查：

```bash
python scripts/env_check.py
```

### 方式二：Docker

```bash
docker build -t quant-dev .
docker run -it --rm --env-file .env -v $(pwd):/workspace -w /workspace quant-dev
```

### TuShare Token

需要在项目根目录提供 `.env`：

```bash
TUSHARE_TOKEN=YOUR_TUSHARE_TOKEN
```

或者在 `config/config_tushare.py` 中读取该环境变量。

当前 `download_hs300.py` 与 `download_research_basics.py` 都支持优先读取环境变量 `TUSHARE_TOKEN`，`config/config_tushare.py` 仅作为回退。

---

## 推荐使用顺序

### 1. 拉取基础原始数据

```bash
python scripts/a_stock/download_hs300.py
```

输出：

* `data/tushare/raw/daily_20150101_20241231.parquet`
* `data/tushare/raw/daily_basic_20150101_20241231.parquet`
* `data/tushare/raw/hs300_constituents_latest.parquet`
* `data/tushare/raw/adj_factor_hs300_20150101_20241231.parquet`

### 2. 补齐研究所需基础数据

```bash
python scripts/a_stock/download_research_basics.py
```

输出：

* `data/tushare/raw/stk_limit_hs300_20150101_20241231.parquet`
* `data/tushare/raw/000300_sh_index_weight_20150101_20241231.parquet`
* `data/tushare/raw/suspend_d_hs300_20150101_20241231.parquet`
* `data/tushare/raw/stock_basic_all_status.parquet`
* `data/tushare/raw/index_daily_000300_SH_20150101_20241231.parquet`
* `results/a_stock/panels/hs300_panel_20150101_20241231_full.parquet`

说明：

* 当前脚本内部会尝试抓取 `stock_st`
* 如果账号无权限，会保留空的占位文件而不中断主流程

### 3. 构建基础研究面板

```bash
python scripts/a_stock/build_panel.py
```

常用参数：

```bash
python scripts/a_stock/build_panel.py \
  --daily-path data/tushare/raw/daily_20150101_20241231.parquet \
  --basic-path data/tushare/raw/daily_basic_20150101_20241231.parquet \
  --universe-path data/tushare/raw/hs300_constituents_latest.parquet \
  --adj-factor-path data/tushare/raw/adj_factor_hs300_20150101_20241231.parquet \
  --stk-limit-path data/tushare/raw/stk_limit_hs300_20150101_20241231.parquet \
  --suspend-d-path data/tushare/raw/suspend_d_hs300_20150101_20241231.parquet \
  --stock-basic-path data/tushare/raw/stock_basic_all_status.parquet \
  --stock-st-path data/tushare/raw/stock_st_20160101_20241231.parquet \
  --output-path data/tushare/processed/hs300_panel_20150101_20241231.parquet
```

说明：

* 如果 `data/tushare/processed/` 不可写，会自动回退到 `results/a_stock/panels/`
* `build_panel.py` 当前已经支持输出完整 `qfq_*` / `hfq_*` 列，并会把 `suspend_d`、`stock_basic_all_status`、`stock_st` 折叠进 `is_tradeable_buy` / `is_tradeable_sell`
* 当前口径下：停牌与暂停上市会同时禁止买卖，ST 仅禁止买入，涨跌停分别禁止对应方向成交

### 4. 运行均线策略回测

默认使用 `full` 面板和 `qfq_close`：

```bash
python scripts/a_stock/backtest_ma.py
```

如果想显式指定：

```bash
python scripts/a_stock/backtest_ma.py --panel-path results/a_stock/panels/hs300_panel_20150101_20241231_full.parquet --price-col qfq_close
```

输出目录默认在 `results/a_stock/ma/`，包括：

* `nav.csv`
* `returns.csv`
* `positions.csv`
* `metrics.csv`
* 图表和 Excel 汇总

### 5. 运行因子分组回测

```bash
python scripts/a_stock/factor_test.py --factor pe_ttm
```

示例：

```bash
python scripts/a_stock/factor_test.py \
  --panel-path results/a_stock/panels/hs300_panel_20150101_20241231_full.parquet \
  --factor pe_ttm \
  --groups 5 \
  --rebalance monthly
```

输出目录默认在 `results/a_stock/factor/`。

### 6. 运行数据质量检查

```bash
python scripts/a_stock/data_quality_check.py --save-csv
```

输出目录默认在 `results/a_stock/data_quality/`。

---

## `quantbt` 模块说明

`src/quantbt/` 是当前仓库的回测核心。

### `engine.py`

提供：

* `BacktestEngine`
* `SignalGenerator`
* `PositionBuilder`
* `ReturnCalculator`
* `MASignalGenerator`
* `MomentumSignalGenerator`
* `MeanReversionSignalGenerator`

当前回测引擎的关键设计是：

* 信号生成后显式 `shift(1)` 执行，避免未来函数
* `weekly / monthly` 调仓频率会在调仓日之间保持上次仓位
* 会读取 `is_tradeable_buy` / `is_tradeable_sell` 约束真实可执行仓位
* 支持简单成本模型
* 可接入 benchmark 计算 Alpha / Beta / Information Ratio

### `metrics.py`

提供基础绩效指标：

* 总收益
* 年化收益
* 波动率
* 最大回撤
* Sharpe
* Sortino
* Calmar
* 胜率
* 盈亏比
* Alpha / Beta
* Information Ratio

### `cost.py`

提供手续费、印花税、滑点和换手估算。

### `io.py`

提供结果导出和图表绘制。

---

## 当前已知限制

* `stock_st` 真实数据仍受 TuShare 权限约束；无权限时只会得到空占位文件
* 交易过滤已接入停牌 / 上市状态 / ST，但仍是研究级约束，不包含更细的撮合与成交量冲击
* crypto 相关脚本没有纳入统一测试，也没有接入主 A 股工作流

---

## 下一步更合理的演进方向

* 给因子测试增加行业中性化、可交易过滤和基准对比
* 将 `data_quality_check.py` 扩展为专门输出停牌 / ST / 暂停上市覆盖率
* 让回测引擎的 `cost_model` 真正参与扣费，而不是只保留接口层
* 将 crypto 脚本从样例整理为独立子模块，或明确标注为实验目录

---

## 开发与测试

运行主测试：

```bash
python -m unittest discover -s tests -v
```

当前这组测试主要验证：

* 面板构建是否成功
* MA 回测 CLI 是否产出结果
* 因子分组回测 CLI 是否产出指标和图
* 数据质量检查 CLI 是否成功输出 CSV

---

## 备注

* 所有真实数据默认都在 `data/` 和 `results/` 下，本地生成，不入 Git
* README 里的数据规模和文件名反映的是当前仓库实际状态，不是预期状态
