# 模块化开发计划

本文档基于当前仓库的实际状态整理，目标是把项目稳定拆分为 `A 股`、`crypto`、`futures` 三个市场模块，并保留 `quantcore` 与 `quantbt` 作为公共层。

## 当前状态概览

- `quantcore` 已承担基础公共能力：路径、schema 校验。
- `quantbt` 已独立为通用回测层。
- `markets.a_share` 已基本完成实质迁移，已具备 `data`、`cli`、`research`、`providers` 四层的最小结构。
- `markets.crypto` 已拆出独立命名空间，并已完成最小可用的 `data`、`research` 第一版闭环。
- `markets.futures` 当前主要还是结构骨架。
- `quanta_stock` 与 `quantcrypto` 仍作为兼容层保留，但已开始收缩为薄兼容壳。

## 最新进展

截至当前，已完成以下模块化结果：

1. 已完成 `quanta_stock` 与 `quantcrypto` 的兼容层收缩。
   - `src/quanta_stock/` 旧实现文件已删除，只保留 `__init__.py` 作为兼容入口。
   - `src/quantcrypto/paths.py` 已删除，`src/quantcrypto/__init__.py` 保留为兼容入口。
2. 已完成 A 股 CLI 最小闭环迁移。
   - 已新增：`src/markets/a_share/cli/build_panel.py`
   - 已新增：`src/markets/a_share/cli/backtest_ma.py`
   - 已新增：`src/markets/a_share/cli/factor_test.py`
   - 已新增：`src/markets/a_share/cli/data_quality_check.py`
3. 已完成 A 股 research 分层。
   - 已新增：`src/markets/a_share/research/factor.py`
   - 已新增：`src/markets/a_share/research/quality.py`
   - CLI 中的因子研究和质量检查逻辑已迁移到 `research` 层。
4. 已完成 A 股 providers 第一版边界。
   - 已新增：`src/markets/a_share/providers/tushare.py`
   - 当前已沉淀最小 TuShare provider 能力：client 初始化、交易日获取、HS300 最新成分获取、指数权重获取。
5. 已补充 A 股路径与导出接口。
   - `src/markets/a_share/paths.py` 已新增 `BACKTESTS_DIR`、`FACTOR_DIR`。
   - `src/markets/a_share/__init__.py`、`src/markets/a_share/cli/__init__.py`、`src/markets/a_share/research/__init__.py`、`src/markets/a_share/providers/__init__.py` 已同步更新导出接口。
6. 已补充 A 股模块测试覆盖。
   - `tests/market_tests/a_share/test_pipeline.py` 当前已覆盖：
     - 面板构建
     - 回测引擎
     - `build_panel` CLI
     - `backtest_ma` CLI
     - `factor_test` CLI
     - `data_quality_check` CLI
7. 已完成 README 与当前模块化结构对齐。
   - `README.md` 已更新为当前实际结构，不再以旧的 `scripts/*` 路径作为主入口说明。
   - A 股当前推荐入口已经切换为 `markets.a_share.cli.*`。
8. 已完成 crypto 最小闭环第一版。
   - 已实现：`src/markets/crypto/data/loader.py`
   - 已实现：`src/markets/crypto/data/panel.py`
   - 已实现：`src/markets/crypto/research/signals.py`
   - 已更新：`src/markets/crypto/__init__.py` 与相关 `__init__` 导出
   - 已新增：`tests/market_tests/crypto/test_pipeline.py`
9. 已启动 futures 第一版，并完成 ETF 研究内核迁移的最小闭环。
   - 已实现：`src/markets/futures/data/io.py`
   - 已实现：`src/markets/futures/data/continuous.py`
   - 已实现：`src/markets/futures/research/metrics.py`
   - 已实现：`src/markets/futures/research/portfolio.py`
   - 已实现：`src/markets/futures/research/reporting.py`
   - 已实现：`src/markets/futures/cli/build_continuous.py`
   - 已新增：`tests/market_tests/futures/test_pipeline.py`

当前验证结果：

- 已执行：`python -m unittest tests.market_tests.a_share.test_pipeline`
- 当前结果：8 个测试通过
- 已执行：`python -m unittest tests.market_tests.crypto.test_pipeline`
- 当前结果：4 个测试通过
- 已执行：`python -m unittest tests.market_tests.futures.test_pipeline`
- 当前结果：3 个测试通过

阶段性判断：

- 阶段 1：已完成
- 阶段 2：已完成最小可用版本，后续还可继续补充更多 provider 与 research 细化实现
- 阶段 3：已完成最小可用版本
- 阶段 4：已完成最小闭环第一版，后续仍需补 `schema / instruments / panel / roll`
- 阶段 5：已部分开始
- 阶段 6：进行中

## 阶段 1：收缩兼容层

目标：避免旧包与新模块双份维护。

### 任务

1. 清点旧包中仍存在的真实实现文件。
   - 目录：`src/quanta_stock/`
   - 目录：`src/quantcrypto/`
2. 将兼容层收缩为纯重导出入口。
   - 保留：`src/quanta_stock/__init__.py`
   - 保留：`src/quantcrypto/__init__.py`
3. 在兼容入口中注明仅用于兼容导入，不再承载新实现。
4. 删除旧实现文件，或至少冻结这些文件，禁止后续继续演进。

### 完成标准

- `quanta_stock` 与 `quantcrypto` 不再包含业务演进逻辑。
- 新增功能只允许进入 `markets/*`、`quantcore`、`quantbt`。

### 当前进度

- 已完成。
- `src/quanta_stock/` 旧实现已清理，仅保留兼容入口。
- `src/quantcrypto/` 已进一步收缩为兼容入口。

## 阶段 2：补齐 A 股模块分层

目标：让 `markets.a_share` 从可用模块升级为结构完整模块。

### 任务

1. 明确 `providers` 层职责。
   - 目录：`src/markets/a_share/providers/`
   - 负责数据源接入，不负责研究逻辑。
2. 明确 `research` 层职责。
   - 目录：`src/markets/a_share/research/`
   - 负责信号、因子、研究分析逻辑。
3. 保持 `data` 层只做数据拼接和面板构建。
   - 文件：`src/markets/a_share/data/panel.py`
   - 文件：`src/markets/a_share/data/enrich.py`
   - 文件：`src/markets/a_share/data/features.py`
4. 补齐 CLI 入口。
   - 目录：`src/markets/a_share/cli/`
   - 建议脚本：`build_panel.py`
   - 建议脚本：`factor_test.py`
   - 建议脚本：`backtest_ma.py`
   - 建议脚本：`data_quality_check.py`
5. 收敛稳定导出接口。
   - 文件：`src/markets/a_share/__init__.py`

### 完成标准

- A 股模块形成 `providers`、`data`、`research`、`cli` 四层清晰边界。
- 使用方默认从 `markets.a_share` 导入，不再依赖旧包名。

### 当前进度

- 已完成最小可用版本。
- `data` 层已稳定承载面板构建。
- `cli` 层四个核心入口已补齐。
- `research` 层已承接因子研究与质量检查逻辑。
- `providers` 层已建立 TuShare 第一版边界，但旧下载脚本中的剩余数据源逻辑还可以继续迁移进来。

## 阶段 3：补完 crypto 最小闭环

目标：让 `markets.crypto` 从独立命名空间变成最小可运行模块。

### 任务

1. 固定 crypto 标准字段集合。
   - 文件：`src/markets/crypto/paths.py`
   - 如有需要新增 schema 文件，统一 `symbol`、`ts`、`open`、`high`、`low`、`close`、`volume`、`source`、`bar` 等字段。
2. 实现数据加载层。
   - 文件：`src/markets/crypto/data/loader.py`
   - 负责读取 provider 输出并统一字段与时间列。
3. 实现面板构建层。
   - 文件：`src/markets/crypto/data/panel.py`
   - 负责去重、排序、生成基础收益字段。
4. 统一 provider 接口风格。
   - 文件：`src/markets/crypto/providers/okx.py`
   - 文件：`src/markets/crypto/providers/yahoo.py`
5. 实现最小研究信号。
   - 文件：`src/markets/crypto/research/signals.py`
   - 先提供 MA 或 momentum 示例，确保能接 `quantbt`。
6. 补齐 CLI。
   - 目录：`src/markets/crypto/cli/`
   - 建议脚本：`fetch_okx.py`
   - 建议脚本：`build_panel.py`
   - 建议脚本：`backtest_ma.py`

### 完成标准

- crypto 具备 `拉行情 -> 标准化 -> panel -> 基础策略回测` 的最小通路。

### 当前进度

- 已完成最小可用版本。
- `data.loader` 已支持将 provider 输出统一为 `ts_code + trade_date + OHLCV + source + bar`。
- `data.panel` 已支持基础 crypto panel 构建，并生成 `ret_1d`、`ret_5d`、`ret_20d`、`volatility_20d`。
- `research.signals` 已提供可接 `quantbt` 的均线信号生成。
- 已补充 `tests/market_tests/crypto/test_pipeline.py` 作为最小测试覆盖。

## 阶段 4：启动 futures 第一版

目标：先建立期货模块的核心抽象，不追求一步到位。

### 任务

1. 实现合约元数据层。
   - 文件：`src/markets/futures/instruments.py`
   - 明确定义 `symbol`、`exchange`、`contract`、`multiplier`、`tick_size`、`list_date`、`delist_date` 等字段。
2. 设计 futures schema。
   - 文件：`src/markets/futures/schema.py`
   - 区分原始合约行情、连续合约、研究面板三类 schema。
3. 实现连续合约骨架。
   - 文件：`src/markets/futures/data/continuous.py`
   - 文件：`src/markets/futures/data/roll.py`
   - 至少支持一种简单换月规则。
4. 实现研究面板层。
   - 文件：`src/markets/futures/data/panel.py`
   - 负责基于连续合约生成基础收益面板。
5. 补齐 CLI。
   - 文件：`src/markets/futures/cli/build_continuous.py`

### 完成标准

- futures 具备 `原始合约 -> 连续合约 -> 研究面板` 的第一版流程。

### 当前进度

- 已完成最小闭环第一版，但还不是完整期货研究框架。
- 已补 `data.io`，支持读取 `hots` 表和合约 K 线。
- 已补 `data.continuous`，支持按主力切换表构建连续合约价格序列。
- 已补 `research.metrics / portfolio / reporting`，支持 ETF 跟踪净值构建与结果输出。
- 已补 `cli.build_continuous`，可直接从 `hots + kline` 生成 `.csv + .jpg` 报告。
- 已补 `tests/market_tests/futures/test_pipeline.py` 作为最小测试入口。
- 仍未完成的部分包括：`schema.py`、`instruments.py`、`data/panel.py`、`data/roll.py` 的正式实现。

## 阶段 5：统一测试体系

目标：让模块化结果可验证，而不只是目录拆分。

### 任务

1. 按市场补测试目录。
   - 已有：`tests/market_tests/a_share/`
   - 新增：`tests/market_tests/crypto/`
   - 新增：`tests/market_tests/futures/`
2. 每个市场至少覆盖三类测试。
   - `data` 层测试
   - `research` 层测试
   - CLI smoke test
3. 补充公共层测试。
   - 建议目录：`tests/quantcore/`
   - 建议目录：`tests/quantbt/`

### 完成标准

- A 股、crypto、futures、quantcore、quantbt 都有最小独立测试入口。

### 当前进度

- A 股：已具备独立测试入口。
- crypto：已具备独立测试入口。
- futures：已补最小独立测试入口。
- `quantcore` 与 `quantbt` 仍缺少单独测试目录。

## 阶段 6：统一文档与导出边界

目标：让文档、代码结构、导入方式保持一致。

### 任务

1. 更新仓库说明文档。
   - 文件：`README.md`
   - 按 `已完成`、`进行中`、`规划中` 描述模块成熟度。
2. 统一各市场模块公开导出接口。
   - 文件：`src/markets/a_share/__init__.py`
   - 文件：`src/markets/crypto/__init__.py`
   - 文件：`src/markets/futures/__init__.py`
3. 明确公共层职责。
   - 文件：`src/quantcore/__init__.py`
   - 文件：`src/quantbt/__init__.py`

### 完成标准

- 新开发者只看 `README` 和各模块 `__init__` 即可理解项目结构与推荐调用方式。

## 推荐执行顺序

1. 收缩兼容层。
2. 完成 A 股模块分层收尾。
3. 完成 crypto 最小闭环。
4. 给 crypto 补测试。
5. 启动 futures 第一版。
6. 最后统一 README 与导出边界。

## 近期优先级建议

优先推进以下事项：

1. 继续把 A 股旧下载脚本中的剩余 TuShare 拉取逻辑迁移到 `src/markets/a_share/providers/tushare.py`。
2. 为 crypto 补 CLI 入口，例如 `fetch_okx.py`、`build_panel.py`、`backtest_ma.py`。
3. 给 crypto 增加面向 `quantbt` 的最小回测闭环测试。
4. 启动 futures 第一版，先补 `instruments.py` 与 schema。
5. 继续压缩兼容层，确认旧包不再承载任何新实现。
