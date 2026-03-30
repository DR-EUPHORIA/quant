
# quant

> A-share quantitative research pipeline: data ingestion → panel construction → backtesting (MVP)

本项目是一个 **A 股量化研究与回测工程项目**，目标是构建一个**可复现、可扩展、工程化**的量化研究基础设施，用于支持因子研究与策略原型验证。

项目当前聚焦于 **数据工程 + 回测最小闭环（MVP）**，强调研究过程的**口径可解释性**与**工程可复现性**。

---

## ✨ 项目目标

* 构建 **A 股研究级数据面板**（行情 + 基本面，parquet 存储）
* 实现 **研究级最小回测系统（Backtest MVP）**

  * 显式防未来函数
  * 支持费用模型
  * 可输出标准化结果（图表 / 指标）
* 支持 **研究员快速迭代因子 / 策略原型**
* 保持 **工程可复现性**

  * 数据与代码分离
  * 脚本化执行
  * Docker 统一运行环境

---

## 📁 项目结构

```text
quant/
├── config/                 # 本地配置与路径定义
│   ├── __init__.py
│   └── paths.py
│
├── scripts/
│   └── a_stock/
│       ├── download_hs300.py     # A股 / HS300 数据拉取
│       ├── build_panel.py        # 构建研究面板（parquet）
│       ├── backtest_ma.py        # 示例：MA 策略回测（MVP）
│       ├── factor_test.py        # 因子分组回测
│       └── inspect_parquet.py    # parquet schema 检查工具
│
├── src/
│   └── quantbt/            # 回测核心库（engine / metrics / cost / io）
│
├── data/                   # 本地数据（全部 ignore）
│   └── tushare/
│       ├── raw/            # 原始数据
│       └── processed/      # 研究面板 / 中间结果
│
├── results/                # 回测结果（图表 / 指标，可入库）
│
├── Dockerfile               # Docker 运行环境定义
├── .dockerignore
├── requirements.txt
├── .gitignore
└── README.md
```

> ⚠️ 所有真实数据均存放在 `data/` 下并通过 `.gitignore` 忽略，
> 仓库仅包含 **代码、工程逻辑与实验方法**。

---

## 🧱 当前已完成内容

### 1️⃣ 数据工程（已完成）

* 使用 **TuShare** 拉取：

  * A 股日线行情（open / high / low / close / vol / amount）
  * 日度基本面指标（turnover_rate、pe_ttm、total_mv 等）
* 构建 **日频研究面板（parquet）**
* 数据处理流程包括：

  * 字段标准化
  * 日期对齐（trade_date）
  * 复合主键检查（`ts_code`, `trade_date`）
  * 缺失值与数据规模统计

> 数据以 **研究面板（long format）** 形式组织，便于后续因子与回测模块复用。
>
> 当前脚本约定的默认文件为：
> - 原始行情：`data/tushare/raw/daily_20150101_20241231.parquet`
> - 原始基本面：`data/tushare/raw/daily_basic_20150101_20241231.parquet`
> - 成分股：`data/tushare/raw/hs300_constituents_latest.parquet`
> - 面板输出：`data/tushare/processed/hs300_panel_20150101_20241231.parquet`
>
> 若运行环境中 `data/tushare/processed/` 不可写，`build_panel.py` 会自动回退到
> `results/a_stock/panels/hs300_panel_20150101_20241231.parquet`。

---

### 2️⃣ 回测系统（Backtest MVP，已搭建）

当前回测模块定位为 **研究级最小系统（Research-grade MVP）**，而非交易系统，重点在于：

* **回测流程拆分清晰**：

  1. 信号生成（Signal）
  2. 持仓构建（Position，显式 `shift(1)` 防未来函数）
  3. 收益计算（Return）
  4. 费用与换手建模（Cost）
  5. 净值与绩效指标（NAV & Metrics）

* **已支持能力**：

  * 显式防未来函数（信号 → 下一交易日执行）
  * 简化手续费 / 滑点模型（bps）
  * 基础绩效指标：

    * 年化收益
    * 最大回撤
    * Sharpe Ratio
  * 净值曲线可视化（matplotlib）
  * 结果导出（`csv` / `xlsx` / 图片）


---

### 3️⃣ 示例策略与研究演示

* **时间序列策略**

  * MA5 / MA20 均线交叉（示例，用于验证回测闭环）
* **横截面研究**

  * 基础因子分组回测（已提供最小版本）
  * 当前已支持：

    * 日 / 周 / 月调仓
    * 分组净值
    * 多空组合净值
    * IC（Spearman）

---

## 🐳 Docker 运行环境（推荐）

为保证 **环境一致性与可复现性**，项目提供 Docker 运行环境，推荐使用 Docker 而非本地 venv。

### Docker 的设计目标

* 统一 Python 版本与依赖
* 避免本地环境 / venv 差异
* 行为贴近真实 Linux 量化研究服务器
* 支持直接在 Docker 内运行数据处理与回测脚本

### 构建镜像

```bash
docker build -t quant-dev .
```

### 启动容器（挂载本地项目）

```bash
docker run -it --rm \
  --env-file .env \
  -v $(pwd):/workspace \
  -w /workspace \
  quant-dev
```

### 环境变量（TuShare Token）

在项目根目录创建 `.env`（不入 Git）：

```bash
TUSHARE_TOKEN=YOUR_TUSHARE_TOKEN
```

如果你使用 `download_hs300.py` 拉取 TuShare 数据，需要在本地提供
`config/config_tushare.py`，例如：

```python
import os

TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
```

脚本会从这个模块中读取 `TUSHARE_TOKEN`。

---

## 🚀 快速开始

### 方式一：Docker（推荐）

```bash
docker build -t quant-dev .
docker run -it --rm --env-file .env -v $(pwd):/workspace -w /workspace quant-dev
```

容器内执行：

```bash
python scripts/a_stock/download_hs300.py
python scripts/a_stock/build_panel.py
python scripts/a_stock/backtest_ma.py
python scripts/a_stock/factor_test.py --factor pe_ttm
```

---

### 方式二：本地 venv（可选）

```bash
python -m venv quant-env
source quant-env/bin/activate  # Windows: quant-env\Scripts\activate
pip install -r requirements.txt
```

安装后可先做一次依赖检查：

```bash
python scripts/env_check.py
```

然后运行最小自动验证：

```bash
python -m unittest discover -s tests -v
```

---

## ▶️ 脚本说明

### 1. 下载原始数据

```bash
python scripts/a_stock/download_hs300.py
```

输出：

* `data/tushare/raw/daily_20150101_20241231.parquet`
* `data/tushare/raw/daily_basic_20150101_20241231.parquet`
* `data/tushare/raw/hs300_constituents_latest.parquet`

### 2. 构建研究面板

```bash
python scripts/a_stock/build_panel.py
```

常用参数：

```bash
python scripts/a_stock/build_panel.py \
  --daily-path data/tushare/raw/daily_20150101_20241231.parquet \
  --basic-path data/tushare/raw/daily_basic_20150101_20241231.parquet \
  --universe-path data/tushare/raw/hs300_constituents_latest.parquet \
  --output-path data/tushare/processed/hs300_panel_20150101_20241231.parquet
```

### 3. 运行均线策略回测

```bash
python scripts/a_stock/backtest_ma.py
```

常用参数：

```bash
python scripts/a_stock/backtest_ma.py \
  --start-date 2020-01-01 \
  --end-date 2024-12-31 \
  --fast 5 \
  --slow 20 \
  --cost-bps 20
```

输出目录默认在 `results/a_stock/ma/`，包括：

* 净值、收益、持仓 `csv`
* 绩效指标 `csv`
* 净值 / 回撤 / 收益分布 / 滚动夏普图
* Excel 汇总结果

### 4. 运行因子分组回测

```bash
python scripts/a_stock/factor_test.py --factor pe_ttm
```

常用参数：

```bash
python scripts/a_stock/factor_test.py \
  --factor pe_ttm \
  --groups 5 \
  --rebalance monthly \
  --start-date 2020-01-01 \
  --end-date 2024-12-31
```

如果因子值越大越好，可以加：

```bash
python scripts/a_stock/factor_test.py --factor total_mv --higher-is-better
```

输出目录默认在 `results/a_stock/factor/`，包括：

* 分组收益与分组净值
* 分组成员矩阵
* Long-short 指标表
* IC 序列与 IC 汇总
* 分组净值图与 IC 图

---

### 5. 运行数据质量检查

`ash
python scripts/a_stock/data_quality_check.py
`

如果要把检查结果保存成 CSV：

`ash
python scripts/a_stock/data_quality_check.py --save-csv
`

输出目录默认在 esults/a_stock/data_quality/，包括：

* 最新交易日成分股缺口
* 每日样本覆盖度
* 每只股票历史长度
* 每只股票的字段缺失率

---

## 📊 数据说明

* 股票池：沪深300 **固定成分池回填历史**
* 时间区间：2015–2024（日频）
* 面板主键：`(ts_code, trade_date)`
* 数据存储格式：`parquet`

> 注意：如果原始数据实际只覆盖少量日期，回测脚本仍然可以运行，
> 但绩效指标会退化为 `0` 或 `NaN`。脚本会在运行时打印样本区间和交易日数。

> 当前版本用于 **研究与工程验证**，存在成分股幸存者偏差，
> 后续将升级为 **动态指数成分处理**。

---

## 🛠️ Roadmap

* [ ] HS300 动态成分与调仓
* [ ] 前复权 / 后复权价格接入
* [ ] 停牌 / ST / 退市处理
* [ ] 更通用的因子回测接口
* [ ] IC / 分组 / 多空组合评估
* [ ] 统一参数管理与日志系统

---

## 📌 设计原则

* **可复现优先**：所有结果均由脚本生成
* **工程化优先**：避免 notebook-only 研究
* **研究友好**：结构清晰、接口明确
* **避免未来函数**：回测阶段强制处理

---

## 📬 联系方式

* Email: [duanrui553@gmail.com](mailto:duanrui553@gmail.com)
* GitHub: [https://github.com/DR-EUPHORIA](https://github.com/DR-EUPHORIA)

