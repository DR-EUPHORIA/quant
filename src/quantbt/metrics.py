import numpy as np
import pandas as pd
from typing import Union, Optional, Dict, Any


def annual_return(
    returns: Union[pd.Series, np.ndarray],
    periods_per_year: int = 252
) -> float:
    """
    计算年化收益率
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        日度收益率序列
    periods_per_year : int
        每年交易日数，默认252
    
    Returns
    -------
    float
        年化收益率
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    returns = returns[~np.isnan(returns)]
    if len(returns) == 0:
        return 0.0
    
    cumulative = (1 + returns).prod()
    n_periods = len(returns)
    
    return cumulative ** (periods_per_year / n_periods) - 1


def cumulative_return(
    returns: Union[pd.Series, np.ndarray]
) -> float:
    """
    计算累计收益率
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        收益率序列
    
    Returns
    -------
    float
        累计收益率
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    returns = returns[~np.isnan(returns)]
    if len(returns) == 0:
        return 0.0
    
    return (1 + returns).prod() - 1


def volatility(
    returns: Union[pd.Series, np.ndarray],
    periods_per_year: int = 252
) -> float:
    """
    计算年化波动率
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        日度收益率序列
    periods_per_year : int
        每年交易日数，默认252
    
    Returns
    -------
    float
        年化波动率
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    returns = returns[~np.isnan(returns)]
    if len(returns) == 0:
        return 0.0
    
    return np.std(returns, ddof=1) * np.sqrt(periods_per_year)


def max_drawdown(
    returns: Union[pd.Series, np.ndarray]
) -> float:
    """
    计算最大回撤
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        收益率序列
    
    Returns
    -------
    float
        最大回撤（负数）
    """
    if isinstance(returns, np.ndarray):
        returns = pd.Series(returns)
    
    returns = returns.dropna()
    if len(returns) == 0:
        return 0.0
    
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    
    return drawdown.min()


def max_drawdown_duration(
    returns: Union[pd.Series, np.ndarray]
) -> int:
    """
    计算最大回撤持续期（天数）
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        收益率序列
    
    Returns
    -------
    int
        最大回撤持续天数
    """
    if isinstance(returns, np.ndarray):
        returns = pd.Series(returns)
    
    returns = returns.dropna()
    if len(returns) == 0:
        return 0
    
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    
    in_drawdown = drawdown < 0
    
    if not in_drawdown.any():
        return 0
    
    max_duration = 0
    current_duration = 0
    
    for is_dd in in_drawdown:
        if is_dd:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0
    
    return max_duration


def sharpe_ratio(
    returns: Union[pd.Series, np.ndarray],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    计算夏普比率
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        日度收益率序列
    risk_free_rate : float
        年化无风险利率，默认0
    periods_per_year : int
        每年交易日数，默认252
    
    Returns
    -------
    float
        夏普比率
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    returns = returns[~np.isnan(returns)]
    if len(returns) == 0:
        return 0.0
    
    daily_rf = risk_free_rate / periods_per_year
    excess_returns = returns - daily_rf
    
    if np.std(excess_returns, ddof=1) == 0:
        return 0.0
    
    ann_ret = annual_return(returns, periods_per_year)
    ann_vol = volatility(returns, periods_per_year)
    
    if ann_vol == 0:
        return 0.0
    
    return (ann_ret - risk_free_rate) / ann_vol


def sortino_ratio(
    returns: Union[pd.Series, np.ndarray],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    计算索提诺比率（只考虑下行风险）
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        日度收益率序列
    risk_free_rate : float
        年化无风险利率，默认0
    periods_per_year : int
        每年交易日数，默认252
    
    Returns
    -------
    float
        索提诺比率
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    returns = returns[~np.isnan(returns)]
    if len(returns) == 0:
        return 0.0
    
    daily_rf = risk_free_rate / periods_per_year
    excess_returns = returns - daily_rf
    
    downside_returns = excess_returns[excess_returns < 0]
    
    if len(downside_returns) == 0:
        return float('inf') if annual_return(returns, periods_per_year) > risk_free_rate else 0.0
    
    downside_std = np.sqrt(np.mean(downside_returns ** 2)) * np.sqrt(periods_per_year)
    
    if downside_std == 0:
        return 0.0
    
    ann_ret = annual_return(returns, periods_per_year)
    
    return (ann_ret - risk_free_rate) / downside_std


def calmar_ratio(
    returns: Union[pd.Series, np.ndarray],
    periods_per_year: int = 252
) -> float:
    """
    计算卡玛比率（年化收益/最大回撤绝对值）
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        日度收益率序列
    periods_per_year : int
        每年交易日数，默认252
    
    Returns
    -------
    float
        卡玛比率
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    returns = returns[~np.isnan(returns)]
    if len(returns) == 0:
        return 0.0
    
    ann_ret = annual_return(returns, periods_per_year)
    mdd = abs(max_drawdown(returns))
    
    if mdd == 0:
        return float('inf') if ann_ret > 0 else 0.0
    
    return ann_ret / mdd


def win_rate(
    returns: Union[pd.Series, np.ndarray]
) -> float:
    """
    计算胜率
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        收益率序列
    
    Returns
    -------
    float
        胜率（0-1之间）
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    returns = returns[~np.isnan(returns)]
    if len(returns) == 0:
        return 0.0
    
    winning = np.sum(returns > 0)
    total = len(returns)
    
    return winning / total


def profit_loss_ratio(
    returns: Union[pd.Series, np.ndarray]
) -> float:
    """
    计算盈亏比（平均盈利/平均亏损绝对值）
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        收益率序列
    
    Returns
    -------
    float
        盈亏比
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    
    returns = returns[~np.isnan(returns)]
    if len(returns) == 0:
        return 0.0
    
    profits = returns[returns > 0]
    losses = returns[returns < 0]
    
    if len(profits) == 0:
        return 0.0
    if len(losses) == 0:
        return float('inf')
    
    avg_profit = np.mean(profits)
    avg_loss = abs(np.mean(losses))
    
    if avg_loss == 0:
        return float('inf')
    
    return avg_profit / avg_loss


def alpha_beta(
    returns: Union[pd.Series, np.ndarray],
    benchmark_returns: Union[pd.Series, np.ndarray],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> Dict[str, float]:
    """
    计算 Alpha 和 Beta
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        策略收益率序列
    benchmark_returns : pd.Series or np.ndarray
        基准收益率序列
    risk_free_rate : float
        年化无风险利率，默认0
    periods_per_year : int
        每年交易日数，默认252
    
    Returns
    -------
    dict
        {'alpha': float, 'beta': float}
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    if isinstance(benchmark_returns, pd.Series):
        benchmark_returns = benchmark_returns.values
    
    min_len = min(len(returns), len(benchmark_returns))
    returns = returns[:min_len]
    benchmark_returns = benchmark_returns[:min_len]
    
    mask = ~(np.isnan(returns) | np.isnan(benchmark_returns))
    returns = returns[mask]
    benchmark_returns = benchmark_returns[mask]
    
    if len(returns) == 0:
        return {'alpha': 0.0, 'beta': 0.0}
    
    covariance = np.cov(returns, benchmark_returns, ddof=1)[0, 1]
    benchmark_variance = np.var(benchmark_returns, ddof=1)
    
    if benchmark_variance == 0:
        beta = 0.0
    else:
        beta = covariance / benchmark_variance
    
    daily_rf = risk_free_rate / periods_per_year
    alpha = np.mean(returns) - daily_rf - beta * (np.mean(benchmark_returns) - daily_rf)
    alpha = alpha * periods_per_year
    
    return {'alpha': alpha, 'beta': beta}


def information_ratio(
    returns: Union[pd.Series, np.ndarray],
    benchmark_returns: Union[pd.Series, np.ndarray],
    periods_per_year: int = 252
) -> float:
    """
    计算信息比率
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        策略收益率序列
    benchmark_returns : pd.Series or np.ndarray
        基准收益率序列
    periods_per_year : int
        每年交易日数，默认252
    
    Returns
    -------
    float
        信息比率
    """
    if isinstance(returns, pd.Series):
        returns = returns.values
    if isinstance(benchmark_returns, pd.Series):
        benchmark_returns = benchmark_returns.values
    
    min_len = min(len(returns), len(benchmark_returns))
    returns = returns[:min_len]
    benchmark_returns = benchmark_returns[:min_len]
    
    mask = ~(np.isnan(returns) | np.isnan(benchmark_returns))
    returns = returns[mask]
    benchmark_returns = benchmark_returns[mask]
    
    if len(returns) == 0:
        return 0.0
    
    excess_returns = returns - benchmark_returns
    
    tracking_error = np.std(excess_returns, ddof=1) * np.sqrt(periods_per_year)
    
    if tracking_error == 0:
        return 0.0
    
    ann_excess_return = annual_return(excess_returns, periods_per_year)
    
    return ann_excess_return / tracking_error


def calculate_all_metrics(
    returns: Union[pd.Series, np.ndarray],
    benchmark_returns: Optional[Union[pd.Series, np.ndarray]] = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> Dict[str, Any]:
    """
    计算所有绩效指标
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        策略收益率序列
    benchmark_returns : pd.Series or np.ndarray, optional
        基准收益率序列
    risk_free_rate : float
        年化无风险利率，默认0
    periods_per_year : int
        每年交易日数，默认252
    
    Returns
    -------
    dict
        包含所有绩效指标的字典
    """
    metrics = {
        'total_return': cumulative_return(returns),
        'annual_return': annual_return(returns, periods_per_year),
        'volatility': volatility(returns, periods_per_year),
        'max_drawdown': max_drawdown(returns),
        'max_drawdown_duration': max_drawdown_duration(returns),
        'sharpe_ratio': sharpe_ratio(returns, risk_free_rate, periods_per_year),
        'sortino_ratio': sortino_ratio(returns, risk_free_rate, periods_per_year),
        'calmar_ratio': calmar_ratio(returns, periods_per_year),
        'win_rate': win_rate(returns),
        'profit_loss_ratio': profit_loss_ratio(returns),
    }
    
    if benchmark_returns is not None:
        ab = alpha_beta(returns, benchmark_returns, risk_free_rate, periods_per_year)
        metrics['alpha'] = ab['alpha']
        metrics['beta'] = ab['beta']
        metrics['information_ratio'] = information_ratio(returns, benchmark_returns, periods_per_year)
        metrics['benchmark_return'] = annual_return(benchmark_returns, periods_per_year)
    
    return metrics


def format_metrics_table(
    metrics: Dict[str, Any],
    precision: int = 4
) -> pd.DataFrame:
    """
    将绩效指标格式化为表格
    
    Parameters
    ----------
    metrics : dict
        绩效指标字典
    precision : int
        小数位数，默认4
    
    Returns
    -------
    pd.DataFrame
        格式化的绩效指标表格
    """
    metric_names = {
        'total_return': '总收益率',
        'annual_return': '年化收益率',
        'volatility': '年化波动率',
        'max_drawdown': '最大回撤',
        'max_drawdown_duration': '最大回撤持续期(天)',
        'sharpe_ratio': '夏普比率',
        'sortino_ratio': '索提诺比率',
        'calmar_ratio': '卡玛比率',
        'win_rate': '胜率',
        'profit_loss_ratio': '盈亏比',
        'alpha': 'Alpha',
        'beta': 'Beta',
        'information_ratio': '信息比率',
        'benchmark_return': '基准年化收益',
    }
    
    formatted = {}
    for key, value in metrics.items():
        name = metric_names.get(key, key)
        if isinstance(value, float):
            if key in ['win_rate']:
                formatted[name] = f'{value:.2%}'
            elif key in ['max_drawdown', 'total_return', 'annual_return', 'volatility', 'benchmark_return']:
                formatted[name] = f'{value:.2%}'
            else:
                formatted[name] = f'{value:.{precision}f}'
        else:
            formatted[name] = str(value)
    
    return pd.DataFrame(list(formatted.items()), columns=['指标', '数值'])
