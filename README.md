
# quant

> A-share quantitative research pipeline: data ingestion → panel construction → backtesting (work in progress)

本项目是一个 **A 股量化研究与回测工程项目**，目标是构建一个**可复现、可扩展、工程化**的量化研究基础设施，用于支持因子研究与策略回测。

当前重点放在 **数据工程 + 回测最小闭环（MVP）**，后续逐步扩展至动态成分、复权处理与更完整的研究平台能力。

---

## ✨ 项目目标

- 构建 **A 股研究级数据面板**（行情 + 基本面）
- 实现 **最小可用回测引擎**（避免未来函数、支持费用模型）
- 支持 **研究员快速迭代策略/因子原型**
- 保持 **工程可复现性**（脚本化、数据与代码分离）

---

## 📁 项目结构

```text
quant/
├── config/                 # 本地配置（token 等，不入 Git）
│   └── config_tushare.py   # TuShare Token（ignored）
│
├── scripts/
│   └── a_stock/
│       ├── download_hs300.py     # A股/HS300 数据拉取
│       ├── build_panel.py        # 构建研究面板（parquet）
│       ├── backtest_ma.py        # 示例：MA 策略回测（MVP）
│       └── utils.py              # 公共工具函数
│
├── data/                   # 本地数据（全部 ignore）
│   └── tushare/
│       ├── raw/            # 原始数据
│       └── processed/      # 面板/回测中间结果
│
├── requirements.txt
├── .gitignore
└── README.md
````

> ⚠️ 所有真实数据均存放在 `data/` 下并通过 `.gitignore` 忽略，仓库仅包含 **代码与工程逻辑**。

---

## 🧱 当前已完成内容

### 1. 数据工程（已完成）

* 使用 **TuShare** 拉取：

  * A 股日线行情（open/high/low/close/vol/amount）
  * 日度基本面指标（turnover_rate、pe_ttm、total_mv 等）
* 构建 **日频研究面板（parquet）**
* 数据处理包含：

  * 字段标准化
  * 日期对齐
  * 重复键检查（ts_code, trade_date）
  * 缺失值统计

### 2. 回测框架（MVP，已搭建）

* 回测流程拆分为：

  * 信号生成
  * 持仓序列（shift 防未来函数）
  * 策略收益与净值
  * 基础绩效指标（年化、最大回撤、Sharpe）
* 支持：

  * 手续费 / 简化滑点模型
  * 净值曲线可视化（matplotlib）

### 3. 示例策略

* 时间序列：MA5 / MA20 均线交叉（示例）
* 横截面：基础因子分组回测（进行中）

---

## 🚀 快速开始

### 1️⃣ 创建虚拟环境并安装依赖

```bash
python -m venv quant-env
source quant-env/bin/activate  # Windows: quant-env\Scripts\activate
pip install -r requirements.txt
```

### 2️⃣ 配置 TuShare Token（本地）

在 `config/config_tushare.py` 中：

```python
TUSHARE_TOKEN = "YOUR_TUSHARE_TOKEN"
```

> 该文件不会被提交到 Git。

### 3️⃣ 拉取数据并构建面板

```bash
python scripts/a_stock/download_hs300.py
python scripts/a_stock/build_panel.py
```

### 4️⃣ 运行示例回测

```bash
python scripts/a_stock/backtest_ma.py
```

---

## 📊 数据说明

* 股票池：沪深300 **固定成分池回填历史**（当前版本）
* 时间区间：2015–2024（日频）
* 数据格式：

  * 行情 / 基本面：`parquet`
  * 面板键：`(ts_code, trade_date)`

> 当前版本用于 **研究与工程验证**，存在成分股幸存者偏差，后续将升级为动态成分。

---

## 🛠️ 开发计划（Roadmap）

* [ ] 动态指数成分处理（HS300 调仓）
* [ ] 前复权价格接入
* [ ] 停牌 / 退市 / ST 处理
* [ ] 更通用的因子回测接口
* [ ] 结果持久化与实验对比
* [ ] 简单参数管理与日志系统

---

## 📌 设计原则

* **可复现优先**：所有结果由脚本生成
* **工程化优先**：避免 notebook-only 研究
* **研究友好**：结构清晰，易于扩展因子与策略
* **避免未来函数**：在回测阶段显式处理


---

## 📬 联系方式

* Email: [duanrui553@gmail.com](mailto:duanrui553@gmail.com)
* GitHub: [https://github.com/DR-EUPHORIA](https://github.com/DR-EUPHORIA)
