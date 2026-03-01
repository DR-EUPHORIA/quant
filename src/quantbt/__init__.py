"""
quantbt - 量化回测工具包

研究级最小回测系统，重点在于：
- 显式防未来函数（信号 → 下一交易日执行）
- 简化手续费/滑点模型
- 基础绩效指标计算
- 净值曲线可视化

主要模块：
- engine: 回测引擎核心
- metrics: 绩效指标计算
- cost: 费用与换手建模
- io: 数据输入输出

快速开始：
>>> from quantbt import BacktestEngine, MASignalGenerator, run_backtest
>>> 
>>> # 加载数据
>>> data = pd.read_parquet('panel.parquet')
>>> 
>>> # 创建信号生成器
>>> signal_gen = MASignalGenerator(fast_period=5, slow_period=20)
>>> 
>>> # 运行回测
>>> result = run_backtest(data, signal_gen)
>>> 
>>> # 查看绩效
>>> print(result.summary())
"""

__version__ = '0.1.0'
__author__ = 'DR-EUPHORIA'

from .metrics import (
    annual_return,
    cumulative_return,
    volatility,
    max_drawdown,
    max_drawdown_duration,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    win_rate,
    profit_loss_ratio,
    alpha_beta,
    information_ratio,
    calculate_all_metrics,
    format_metrics_table,
)

from .cost import (
    CommissionModel,
    SlippageModel,
    CostModel,
    calculate_turnover,
    calculate_annualized_turnover,
    calculate_trade_count,
    estimate_transaction_cost,
    create_simple_cost_model,
)

from .io import (
    load_panel,
    save_results,
    plot_nav,
    plot_drawdown,
    plot_returns_distribution,
    plot_rolling_sharpe,
    export_to_excel,
    generate_report,
    inspect_parquet,
    print_parquet_info,
)

from .engine import (
    SignalGenerator,
    PositionBuilder,
    ReturnCalculator,
    BacktestResult,
    BacktestEngine,
    MASignalGenerator,
    MomentumSignalGenerator,
    MeanReversionSignalGenerator,
    run_backtest,
)

__all__ = [
    # 版本信息
    '__version__',
    '__author__',
    
    # 绩效指标
    'annual_return',
    'cumulative_return',
    'volatility',
    'max_drawdown',
    'max_drawdown_duration',
    'sharpe_ratio',
    'sortino_ratio',
    'calmar_ratio',
    'win_rate',
    'profit_loss_ratio',
    'alpha_beta',
    'information_ratio',
    'calculate_all_metrics',
    'format_metrics_table',
    
    # 费用模型
    'CommissionModel',
    'SlippageModel',
    'CostModel',
    'calculate_turnover',
    'calculate_annualized_turnover',
    'calculate_trade_count',
    'estimate_transaction_cost',
    'create_simple_cost_model',
    
    # 输入输出
    'load_panel',
    'save_results',
    'plot_nav',
    'plot_drawdown',
    'plot_returns_distribution',
    'plot_rolling_sharpe',
    'export_to_excel',
    'generate_report',
    'inspect_parquet',
    'print_parquet_info',
    
    # 回测引擎
    'SignalGenerator',
    'PositionBuilder',
    'ReturnCalculator',
    'BacktestResult',
    'BacktestEngine',
    'MASignalGenerator',
    'MomentumSignalGenerator',
    'MeanReversionSignalGenerator',
    'run_backtest',
]
