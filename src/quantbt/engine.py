import numpy as np
import pandas as pd
from typing import Union, Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from .metrics import calculate_all_metrics, format_metrics_table
from .cost import CostModel, create_simple_cost_model, calculate_turnover, calculate_annualized_turnover
from .io import generate_report, plot_nav, plot_drawdown


class SignalGenerator(ABC):
    """
    信号生成器基类
    """
    
    @abstractmethod
    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成交易信号
        
        Parameters
        ----------
        data : pd.DataFrame
            面板数据，包含 trade_date, ts_code, close 等字段
        
        Returns
        -------
        pd.DataFrame
            包含 trade_date, ts_code, signal 字段的 DataFrame
            signal: 1=买入, -1=卖出, 0=持有
        """
        pass


class PositionBuilder:
    """
    持仓构建器
    """
    
    def __init__(
        self,
        rebalance_freq: str = 'daily',
        position_type: str = 'equal_weight',
        max_position: float = 1.0,
        min_position: float = 0.0,
        long_only: bool = True
    ):
        """
        Parameters
        ----------
        rebalance_freq : str
            调仓频率，'daily', 'weekly', 'monthly'
        position_type : str
            持仓类型，'equal_weight', 'signal_weight', 'custom'
        max_position : float
            单只股票最大持仓权重
        min_position : float
            单只股票最小持仓权重
        long_only : bool
            是否只做多
        """
        self.rebalance_freq = rebalance_freq
        self.position_type = position_type
        self.max_position = max_position
        self.min_position = min_position
        self.long_only = long_only
    
    def build(
        self,
        signals: pd.DataFrame,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        根据信号构建持仓权重
        
        Parameters
        ----------
        signals : pd.DataFrame
            交易信号，包含 trade_date, ts_code, signal
        data : pd.DataFrame
            面板数据
        
        Returns
        -------
        pd.DataFrame
            持仓权重，index 为 trade_date，columns 为 ts_code
        """
        signals = signals.copy()
        
        signals['rebalance'] = self._get_rebalance_mask(signals['trade_date']).values
        
        pivot_signals = signals.pivot(index='trade_date', columns='ts_code', values='signal')
        pivot_signals = pivot_signals.fillna(0)
        
        if self.long_only:
            pivot_signals = pivot_signals.clip(lower=0)
        
        if self.position_type == 'equal_weight':
            positions = self._equal_weight(pivot_signals)
        elif self.position_type == 'signal_weight':
            positions = self._signal_weight(pivot_signals)
        else:
            positions = pivot_signals
        
        positions = positions.clip(lower=self.min_position, upper=self.max_position)
        
        row_sums = positions.sum(axis=1)
        row_sums = row_sums.replace(0, 1)
        positions = positions.div(row_sums, axis=0)
        
        rebalance_dates = pd.Index(signals.loc[signals['rebalance'], 'trade_date'].drop_duplicates())
        if self.rebalance_freq != 'daily':
            positions.loc[~positions.index.isin(rebalance_dates), :] = np.nan
            positions = positions.ffill()

        positions = positions.shift(1).fillna(0.0)
        positions = self._apply_tradeability_constraints(positions, data)
        
        return positions

    def _get_rebalance_mask(self, trade_dates: pd.Series) -> pd.Series:
        dates = pd.to_datetime(trade_dates)
        if self.rebalance_freq == 'weekly':
            keys = dates.dt.strftime('%Y-%W')
            return keys.ne(keys.shift(1)).fillna(True)
        if self.rebalance_freq == 'monthly':
            keys = dates.dt.to_period('M').astype(str)
            return keys.ne(keys.shift(1)).fillna(True)
        return pd.Series(True, index=trade_dates.index)

    def _apply_tradeability_constraints(
        self,
        target_positions: pd.DataFrame,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        buyable = self._build_boolean_panel(data, 'is_tradeable_buy', target_positions.index, target_positions.columns)
        sellable = self._build_boolean_panel(data, 'is_tradeable_sell', target_positions.index, target_positions.columns)

        constrained_rows = []
        prev = pd.Series(0.0, index=target_positions.columns)

        for trade_date, target in target_positions.iterrows():
            target = target.fillna(0.0)
            if self.long_only:
                target = target.clip(lower=0.0)

            can_buy = buyable.loc[trade_date]
            can_sell = sellable.loc[trade_date]

            reduced = prev.where((target >= prev) | (~can_sell), target)
            desired_add = (target - reduced).clip(lower=0.0)
            desired_add = desired_add.where(can_buy, 0.0)

            available_cash = max(0.0, 1.0 - float(reduced.sum()))
            total_add = float(desired_add.sum())
            if total_add > 0 and available_cash > 0:
                scale = min(1.0, available_cash / total_add)
                current = reduced + desired_add * scale
            else:
                current = reduced

            current = current.fillna(0.0)
            constrained_rows.append(current)
            prev = current

        constrained = pd.DataFrame(constrained_rows, index=target_positions.index)
        constrained.columns = target_positions.columns
        return constrained

    @staticmethod
    def _build_boolean_panel(
        data: pd.DataFrame,
        column: str,
        index: pd.Index,
        columns: pd.Index
    ) -> pd.DataFrame:
        if column not in data.columns:
            return pd.DataFrame(True, index=index, columns=columns)

        values = (
            data[['trade_date', 'ts_code', column]]
            .drop_duplicates(subset=['trade_date', 'ts_code'], keep='last')
            .pivot(index='trade_date', columns='ts_code', values=column)
            .reindex(index=index, columns=columns)
            .fillna(False)
            .astype(bool)
        )
        return values
    
    def _equal_weight(self, signals: pd.DataFrame) -> pd.DataFrame:
        """等权重持仓"""
        positions = signals.copy()
        mask = positions > 0
        count = mask.sum(axis=1)
        count = count.replace(0, 1)
        positions = mask.div(count, axis=0)
        return positions
    
    def _signal_weight(self, signals: pd.DataFrame) -> pd.DataFrame:
        """按信号强度加权"""
        positions = signals.copy()
        positions[positions < 0] = 0
        row_sums = positions.sum(axis=1)
        row_sums = row_sums.replace(0, 1)
        positions = positions.div(row_sums, axis=0)
        return positions


class ReturnCalculator:
    """
    收益计算器
    """
    
    def __init__(
        self,
        price_col: str = 'close',
        return_method: str = 'simple'
    ):
        """
        Parameters
        ----------
        price_col : str
            价格列名
        return_method : str
            收益率计算方法，'simple' 或 'log'
        """
        self.price_col = price_col
        self.return_method = return_method
    
    def calculate(
        self,
        positions: pd.DataFrame,
        data: pd.DataFrame
    ) -> pd.Series:
        """
        计算策略收益率
        
        Parameters
        ----------
        positions : pd.DataFrame
            持仓权重，index 为 trade_date，columns 为 ts_code
        data : pd.DataFrame
            面板数据
        
        Returns
        -------
        pd.Series
            策略日收益率，index 为 trade_date
        """
        returns = self._calculate_stock_returns(data)
        
        returns = returns.reindex(index=positions.index, columns=positions.columns)
        
        strategy_returns = (positions * returns).sum(axis=1)
        
        return strategy_returns
    
    def _calculate_stock_returns(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算个股收益率"""
        price_pivot = data.pivot(index='trade_date', columns='ts_code', values=self.price_col)
        
        if self.return_method == 'log':
            returns = np.log(price_pivot / price_pivot.shift(1))
        else:
            returns = price_pivot.pct_change()
        
        return returns


@dataclass
class BacktestResult:
    """
    回测结果
    """
    nav: pd.Series
    returns: pd.Series
    positions: pd.DataFrame
    metrics: Dict[str, Any]
    turnover: pd.Series
    annualized_turnover: float
    trade_count: int
    
    def summary(self) -> pd.DataFrame:
        """返回绩效摘要表"""
        return format_metrics_table(self.metrics)
    
    def plot(self, output_dir: Optional[str] = None, show: bool = True) -> None:
        """绘制回测结果图表"""
        if output_dir:
            generate_report(
                self.nav, 
                self.returns, 
                self.metrics, 
                output_dir,
                name='backtest'
            )
        else:
            plot_nav(self.nav, show=show)
            plot_drawdown(self.nav, show=show)


class BacktestEngine:
    """
    回测引擎
    
    研究级最小回测系统，重点在于：
    - 显式防未来函数（信号 → 下一交易日执行）
    - 简化手续费/滑点模型
    - 基础绩效指标计算
    """
    
    def __init__(
        self,
        data: pd.DataFrame,
        signal_generator: Optional[SignalGenerator] = None,
        position_builder: Optional[PositionBuilder] = None,
        return_calculator: Optional[ReturnCalculator] = None,
        cost_model: Optional[CostModel] = None,
        initial_capital: float = 1.0,
        risk_free_rate: float = 0.0,
        benchmark_data: Optional[pd.DataFrame] = None
    ):
        """
        Parameters
        ----------
        data : pd.DataFrame
            面板数据，必须包含 trade_date, ts_code, close 列
        signal_generator : SignalGenerator
            信号生成器
        position_builder : PositionBuilder
            持仓构建器
        return_calculator : ReturnCalculator
            收益计算器
        cost_model : CostModel
            费用模型
        initial_capital : float
            初始资金
        risk_free_rate : float
            无风险利率
        benchmark_data : pd.DataFrame
            基准数据，用于计算 Alpha/Beta
        """
        self.data = data.copy()
        self.signal_generator = signal_generator
        self.position_builder = position_builder or PositionBuilder()
        self.return_calculator = return_calculator or ReturnCalculator()
        self.cost_model = cost_model or create_simple_cost_model()
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate
        self.benchmark_data = benchmark_data
        
        self._validate_data()
        self._prepare_data()
    
    def _validate_data(self):
        """验证数据格式"""
        required_cols = ['trade_date', 'ts_code', 'close']
        missing = [col for col in required_cols if col not in self.data.columns]
        if missing:
            raise ValueError(f"数据缺少必要列: {missing}")
    
    def _prepare_data(self):
        """准备数据"""
        if self.data['trade_date'].dtype == 'object':
            self.data['trade_date'] = pd.to_datetime(self.data['trade_date'], format='%Y%m%d')
        elif not pd.api.types.is_datetime64_any_dtype(self.data['trade_date']):
            self.data['trade_date'] = pd.to_datetime(self.data['trade_date'])
        
        self.data = self.data.sort_values(['trade_date', 'ts_code'])
        self.dates = sorted(self.data['trade_date'].unique())
        self.codes = sorted(self.data['ts_code'].unique())
    
    def run(
        self,
        signals: Optional[pd.DataFrame] = None,
        apply_cost: bool = True
    ) -> BacktestResult:
        """
        运行回测
        
        Parameters
        ----------
        signals : pd.DataFrame, optional
            外部提供的信号，如果为 None 则使用 signal_generator 生成
        apply_cost : bool
            是否应用交易成本
        
        Returns
        -------
        BacktestResult
            回测结果
        """
        if signals is None:
            if self.signal_generator is None:
                raise ValueError("必须提供 signals 或 signal_generator")
            signals = self.signal_generator.generate(self.data)
        
        positions = self.position_builder.build(signals, self.data)
        
        returns = self.return_calculator.calculate(positions, self.data)
        
        if apply_cost:
            returns = self._apply_transaction_cost(returns, positions)
        
        nav = (1 + returns).cumprod() * self.initial_capital
        nav.iloc[0] = self.initial_capital
        
        benchmark_returns = None
        if self.benchmark_data is not None:
            benchmark_returns = self._calculate_benchmark_returns()
        
        metrics = calculate_all_metrics(
            returns,
            benchmark_returns=benchmark_returns,
            risk_free_rate=self.risk_free_rate
        )
        
        turnover = pd.Series(calculate_turnover(positions), index=positions.index[1:])
        annualized_turnover = calculate_annualized_turnover(positions)
        
        trade_count = int(np.sum(np.abs(np.diff(positions.values, axis=0)) > 1e-6))
        
        return BacktestResult(
            nav=nav,
            returns=returns,
            positions=positions,
            metrics=metrics,
            turnover=turnover,
            annualized_turnover=annualized_turnover,
            trade_count=trade_count
        )
    
    def _apply_transaction_cost(
        self,
        returns: pd.Series,
        positions: pd.DataFrame
    ) -> pd.Series:
        """应用交易成本"""
        position_changes = positions.diff().abs().sum(axis=1)
        
        avg_cost_bps = 20
        cost = position_changes * avg_cost_bps / 10000
        
        returns = returns - cost
        
        return returns
    
    def _calculate_benchmark_returns(self) -> pd.Series:
        """计算基准收益率"""
        if 'close' not in self.benchmark_data.columns:
            raise ValueError("基准数据必须包含 close 列")
        
        if 'trade_date' in self.benchmark_data.columns:
            if self.benchmark_data['trade_date'].dtype == 'object':
                self.benchmark_data['trade_date'] = pd.to_datetime(
                    self.benchmark_data['trade_date'], format='%Y%m%d'
                )
            benchmark = self.benchmark_data.set_index('trade_date')['close']
        else:
            benchmark = self.benchmark_data['close']
        
        return benchmark.pct_change()


class MASignalGenerator(SignalGenerator):
    """
    均线交叉信号生成器
    """
    
    def __init__(
        self,
        fast_period: int = 5,
        slow_period: int = 20,
        price_col: str = 'close'
    ):
        """
        Parameters
        ----------
        fast_period : int
            快线周期
        slow_period : int
            慢线周期
        price_col : str
            价格列名
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.price_col = price_col
    
    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成均线交叉信号"""
        data = data.copy()
        
        data['ma_fast'] = data.groupby('ts_code')[self.price_col].transform(
            lambda x: x.rolling(self.fast_period, min_periods=1).mean()
        )
        data['ma_slow'] = data.groupby('ts_code')[self.price_col].transform(
            lambda x: x.rolling(self.slow_period, min_periods=1).mean()
        )
        
        data['signal'] = 0
        data.loc[data['ma_fast'] > data['ma_slow'], 'signal'] = 1
        data.loc[data['ma_fast'] < data['ma_slow'], 'signal'] = 0
        
        return data[['trade_date', 'ts_code', 'signal']]


class MomentumSignalGenerator(SignalGenerator):
    """
    动量信号生成器
    """
    
    def __init__(
        self,
        lookback_period: int = 20,
        top_n: int = 10,
        price_col: str = 'close'
    ):
        """
        Parameters
        ----------
        lookback_period : int
            回看周期
        top_n : int
            选取前 N 只股票
        price_col : str
            价格列名
        """
        self.lookback_period = lookback_period
        self.top_n = top_n
        self.price_col = price_col
    
    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成动量信号"""
        data = data.copy()
        
        data['return'] = data.groupby('ts_code')[self.price_col].transform(
            lambda x: x.pct_change(self.lookback_period)
        )
        
        signals_list = []
        for date, group in data.groupby('trade_date'):
            group = group.dropna(subset=['return'])
            group = group.sort_values('return', ascending=False)
            
            group['signal'] = 0
            group.iloc[:self.top_n, group.columns.get_loc('signal')] = 1
            
            signals_list.append(group[['trade_date', 'ts_code', 'signal']])
        
        return pd.concat(signals_list, ignore_index=True)


class MeanReversionSignalGenerator(SignalGenerator):
    """
    均值回归信号生成器
    """
    
    def __init__(
        self,
        lookback_period: int = 20,
        zscore_threshold: float = 2.0,
        price_col: str = 'close'
    ):
        """
        Parameters
        ----------
        lookback_period : int
            回看周期
        zscore_threshold : float
            Z-score 阈值
        price_col : str
            价格列名
        """
        self.lookback_period = lookback_period
        self.zscore_threshold = zscore_threshold
        self.price_col = price_col
    
    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成均值回归信号"""
        data = data.copy()
        
        def calc_zscore(x):
            mean = x.rolling(self.lookback_period, min_periods=1).mean()
            std = x.rolling(self.lookback_period, min_periods=1).std()
            std = std.replace(0, np.nan)
            return (x - mean) / std
        
        data['zscore'] = data.groupby('ts_code')[self.price_col].transform(calc_zscore)
        
        data['signal'] = 0
        data.loc[data['zscore'] < -self.zscore_threshold, 'signal'] = 1
        data.loc[data['zscore'] > self.zscore_threshold, 'signal'] = 0
        
        return data[['trade_date', 'ts_code', 'signal']]


def run_backtest(
    data: pd.DataFrame,
    signal_generator: SignalGenerator,
    cost_bps: float = 20,
    risk_free_rate: float = 0.0,
    benchmark_data: Optional[pd.DataFrame] = None,
    output_dir: Optional[str] = None
) -> BacktestResult:
    """
    快速运行回测的便捷函数
    
    Parameters
    ----------
    data : pd.DataFrame
        面板数据
    signal_generator : SignalGenerator
        信号生成器
    cost_bps : float
        交易成本（基点）
    risk_free_rate : float
        无风险利率
    benchmark_data : pd.DataFrame, optional
        基准数据
    output_dir : str, optional
        输出目录
    
    Returns
    -------
    BacktestResult
        回测结果
    """
    cost_model = create_simple_cost_model(
        commission_bps=cost_bps / 4,
        stamp_duty_bps=cost_bps / 4,
        slippage_bps=cost_bps / 2
    )
    
    engine = BacktestEngine(
        data=data,
        signal_generator=signal_generator,
        cost_model=cost_model,
        risk_free_rate=risk_free_rate,
        benchmark_data=benchmark_data
    )
    
    result = engine.run()
    
    if output_dir:
        result.plot(output_dir=output_dir, show=False)
    
    return result
