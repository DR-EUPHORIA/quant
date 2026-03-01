import os
import json
from pathlib import Path
from typing import Union, Optional, Dict, Any, List
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def load_panel(
    filepath: Union[str, Path],
    columns: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    codes: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    加载研究面板数据
    
    Parameters
    ----------
    filepath : str or Path
        parquet 文件路径
    columns : list of str, optional
        需要加载的列，默认加载全部
    start_date : str, optional
        起始日期，格式 'YYYY-MM-DD' 或 'YYYYMMDD'
    end_date : str, optional
        结束日期，格式 'YYYY-MM-DD' 或 'YYYYMMDD'
    codes : list of str, optional
        股票代码列表，用于筛选
    
    Returns
    -------
    pd.DataFrame
        面板数据
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")
    
    df = pd.read_parquet(filepath, columns=columns)
    
    if 'trade_date' in df.columns:
        if df['trade_date'].dtype == 'object':
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        elif not pd.api.types.is_datetime64_any_dtype(df['trade_date']):
            df['trade_date'] = pd.to_datetime(df['trade_date'])
    
    if start_date is not None:
        start_date = pd.to_datetime(start_date)
        df = df[df['trade_date'] >= start_date]
    
    if end_date is not None:
        end_date = pd.to_datetime(end_date)
        df = df[df['trade_date'] <= end_date]
    
    if codes is not None and 'ts_code' in df.columns:
        df = df[df['ts_code'].isin(codes)]
    
    return df


def save_results(
    results: Dict[str, Any],
    output_dir: Union[str, Path],
    name: str,
    format: str = 'parquet'
) -> Path:
    """
    保存回测结果
    
    Parameters
    ----------
    results : dict
        回测结果字典，包含 'nav', 'returns', 'positions' 等
    output_dir : str or Path
        输出目录
    name : str
        文件名前缀
    format : str
        保存格式，支持 'parquet', 'csv', 'excel'
    
    Returns
    -------
    Path
        保存的文件路径
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    saved_files = []
    
    for key, value in results.items():
        if isinstance(value, pd.DataFrame):
            if format == 'parquet':
                filepath = output_dir / f"{name}_{key}.parquet"
                value.to_parquet(filepath, index=True)
            elif format == 'csv':
                filepath = output_dir / f"{name}_{key}.csv"
                value.to_csv(filepath, index=True)
            elif format == 'excel':
                filepath = output_dir / f"{name}_{key}.xlsx"
                value.to_excel(filepath, index=True)
            else:
                raise ValueError(f"不支持的格式: {format}")
            saved_files.append(filepath)
        
        elif isinstance(value, (dict, list)):
            filepath = output_dir / f"{name}_{key}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False, indent=2, default=str)
            saved_files.append(filepath)
    
    return output_dir


def plot_nav(
    nav: Union[pd.Series, pd.DataFrame],
    benchmark: Optional[Union[pd.Series, pd.DataFrame]] = None,
    title: str = "策略净值曲线",
    figsize: tuple = (12, 6),
    output_path: Optional[Union[str, Path]] = None,
    show: bool = True
) -> plt.Figure:
    """
    绘制净值曲线
    
    Parameters
    ----------
    nav : pd.Series or pd.DataFrame
        策略净值序列
    benchmark : pd.Series or pd.DataFrame, optional
        基准净值序列
    title : str
        图表标题
    figsize : tuple
        图表大小
    output_path : str or Path, optional
        图片保存路径
    show : bool
        是否显示图表
    
    Returns
    -------
    plt.Figure
        matplotlib Figure 对象
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    if isinstance(nav, pd.DataFrame):
        for col in nav.columns:
            ax.plot(nav.index, nav[col], label=col, linewidth=1.5)
    else:
        ax.plot(nav.index, nav, label='策略', linewidth=1.5, color='#2E86AB')
    
    if benchmark is not None:
        if isinstance(benchmark, pd.DataFrame):
            for col in benchmark.columns:
                ax.plot(benchmark.index, benchmark[col], label=f'基准({col})', 
                       linewidth=1, linestyle='--', alpha=0.7)
        else:
            ax.plot(benchmark.index, benchmark, label='基准', 
                   linewidth=1, linestyle='--', alpha=0.7, color='#A23B72')
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('日期', fontsize=12)
    ax.set_ylabel('净值', fontsize=12)
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
    
    if show:
        plt.show()
    
    return fig


def plot_drawdown(
    nav: Union[pd.Series, pd.DataFrame],
    title: str = "策略回撤曲线",
    figsize: tuple = (12, 4),
    output_path: Optional[Union[str, Path]] = None,
    show: bool = True
) -> plt.Figure:
    """
    绘制回撤曲线
    
    Parameters
    ----------
    nav : pd.Series or pd.DataFrame
        策略净值序列
    title : str
        图表标题
    figsize : tuple
        图表大小
    output_path : str or Path, optional
        图片保存路径
    show : bool
        是否显示图表
    
    Returns
    -------
    plt.Figure
        matplotlib Figure 对象
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    if isinstance(nav, pd.DataFrame):
        for col in nav.columns:
            running_max = nav[col].cummax()
            drawdown = (nav[col] - running_max) / running_max
            ax.fill_between(nav.index, drawdown, 0, alpha=0.3, label=col)
            ax.plot(nav.index, drawdown, linewidth=1)
    else:
        running_max = nav.cummax()
        drawdown = (nav - running_max) / running_max
        ax.fill_between(nav.index, drawdown, 0, alpha=0.3, color='#E74C3C')
        ax.plot(nav.index, drawdown, linewidth=1, color='#E74C3C')
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('日期', fontsize=12)
    ax.set_ylabel('回撤', fontsize=12)
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: '{:.1%}'.format(y)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
    
    if show:
        plt.show()
    
    return fig


def plot_returns_distribution(
    returns: Union[pd.Series, np.ndarray],
    title: str = "收益率分布",
    figsize: tuple = (10, 6),
    bins: int = 50,
    output_path: Optional[Union[str, Path]] = None,
    show: bool = True
) -> plt.Figure:
    """
    绘制收益率分布直方图
    
    Parameters
    ----------
    returns : pd.Series or np.ndarray
        收益率序列
    title : str
        图表标题
    figsize : tuple
        图表大小
    bins : int
        直方图柱数
    output_path : str or Path, optional
        图片保存路径
    show : bool
        是否显示图表
    
    Returns
    -------
    plt.Figure
        matplotlib Figure 对象
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    if isinstance(returns, pd.Series):
        returns = returns.dropna().values
    
    ax.hist(returns, bins=bins, density=True, alpha=0.7, color='#3498DB', edgecolor='white')
    
    mean_ret = np.mean(returns)
    std_ret = np.std(returns)
    
    ax.axvline(mean_ret, color='#E74C3C', linestyle='--', linewidth=2, label=f'均值: {mean_ret:.2%}')
    ax.axvline(mean_ret - 2*std_ret, color='#F39C12', linestyle=':', linewidth=1.5, label=f'±2σ')
    ax.axvline(mean_ret + 2*std_ret, color='#F39C12', linestyle=':', linewidth=1.5)
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('日收益率', fontsize=12)
    ax.set_ylabel('频率', fontsize=12)
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: '{:.1%}'.format(x)))
    
    plt.tight_layout()
    
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
    
    if show:
        plt.show()
    
    return fig


def plot_rolling_sharpe(
    returns: pd.Series,
    window: int = 252,
    risk_free_rate: float = 0.0,
    title: str = "滚动夏普比率",
    figsize: tuple = (12, 4),
    output_path: Optional[Union[str, Path]] = None,
    show: bool = True
) -> plt.Figure:
    """
    绘制滚动夏普比率
    
    Parameters
    ----------
    returns : pd.Series
        收益率序列
    window : int
        滚动窗口大小
    risk_free_rate : float
        无风险利率
    title : str
        图表标题
    figsize : tuple
        图表大小
    output_path : str or Path, optional
        图片保存路径
    show : bool
        是否显示图表
    
    Returns
    -------
    plt.Figure
        matplotlib Figure 对象
    """
    fig, ax = plt.subplots(figsize=figsize)
    
    daily_rf = risk_free_rate / 252
    excess_returns = returns - daily_rf
    
    rolling_mean = excess_returns.rolling(window=window).mean() * 252
    rolling_std = returns.rolling(window=window).std() * np.sqrt(252)
    rolling_sharpe = rolling_mean / rolling_std
    
    ax.plot(returns.index, rolling_sharpe, linewidth=1.5, color='#2E86AB')
    ax.axhline(0, color='gray', linestyle='--', linewidth=1)
    ax.axhline(1, color='green', linestyle=':', linewidth=1, alpha=0.7, label='Sharpe=1')
    ax.axhline(2, color='green', linestyle=':', linewidth=1, alpha=0.7, label='Sharpe=2')
    
    ax.fill_between(returns.index, rolling_sharpe, 0, 
                    where=rolling_sharpe >= 0, alpha=0.3, color='green')
    ax.fill_between(returns.index, rolling_sharpe, 0, 
                    where=rolling_sharpe < 0, alpha=0.3, color='red')
    
    ax.set_title(f'{title} (窗口={window}天)', fontsize=14, fontweight='bold')
    ax.set_xlabel('日期', fontsize=12)
    ax.set_ylabel('夏普比率', fontsize=12)
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
    
    if show:
        plt.show()
    
    return fig


def export_to_excel(
    results: Dict[str, Any],
    output_path: Union[str, Path],
    sheet_name_prefix: str = ''
) -> Path:
    """
    导出回测结果到 Excel
    
    Parameters
    ----------
    results : dict
        回测结果字典
    output_path : str or Path
        输出文件路径
    sheet_name_prefix : str
        工作表名称前缀
    
    Returns
    -------
    Path
        保存的文件路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for key, value in results.items():
            sheet_name = f"{sheet_name_prefix}{key}" if sheet_name_prefix else key
            sheet_name = sheet_name[:31]
            
            if isinstance(value, pd.DataFrame):
                value.to_excel(writer, sheet_name=sheet_name)
            elif isinstance(value, pd.Series):
                value.to_frame().to_excel(writer, sheet_name=sheet_name)
            elif isinstance(value, dict):
                pd.DataFrame(list(value.items()), columns=['指标', '数值']).to_excel(
                    writer, sheet_name=sheet_name, index=False)
    
    return output_path


def generate_report(
    nav: pd.Series,
    returns: pd.Series,
    metrics: Dict[str, Any],
    output_dir: Union[str, Path],
    name: str = 'backtest',
    benchmark: Optional[pd.Series] = None,
    positions: Optional[pd.DataFrame] = None
) -> Dict[str, Path]:
    """
    生成完整的回测报告
    
    Parameters
    ----------
    nav : pd.Series
        净值序列
    returns : pd.Series
        收益率序列
    metrics : dict
        绩效指标字典
    output_dir : str or Path
        输出目录
    name : str
        文件名前缀
    benchmark : pd.Series, optional
        基准净值序列
    positions : pd.DataFrame, optional
        持仓数据
    
    Returns
    -------
    dict
        生成的文件路径字典
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_files = {}
    
    nav_plot_path = output_dir / f"{name}_nav.png"
    plot_nav(nav, benchmark=benchmark, output_path=nav_plot_path, show=False)
    generated_files['nav_plot'] = nav_plot_path
    
    drawdown_plot_path = output_dir / f"{name}_drawdown.png"
    plot_drawdown(nav, output_path=drawdown_plot_path, show=False)
    generated_files['drawdown_plot'] = drawdown_plot_path
    
    returns_plot_path = output_dir / f"{name}_returns_dist.png"
    plot_returns_distribution(returns, output_path=returns_plot_path, show=False)
    generated_files['returns_dist_plot'] = returns_plot_path
    
    rolling_sharpe_path = output_dir / f"{name}_rolling_sharpe.png"
    plot_rolling_sharpe(returns, output_path=rolling_sharpe_path, show=False)
    generated_files['rolling_sharpe_plot'] = rolling_sharpe_path
    
    results = {
        'nav': nav,
        'returns': returns,
        'metrics': metrics
    }
    
    if positions is not None:
        results['positions'] = positions
    
    excel_path = output_dir / f"{name}_results.xlsx"
    export_to_excel(results, excel_path)
    generated_files['excel'] = excel_path
    
    metrics_df = pd.DataFrame(list(metrics.items()), columns=['指标', '数值'])
    metrics_path = output_dir / f"{name}_metrics.csv"
    metrics_df.to_csv(metrics_path, index=False, encoding='utf-8-sig')
    generated_files['metrics_csv'] = metrics_path
    
    return generated_files


def inspect_parquet(
    filepath: Union[str, Path],
    n_rows: int = 5
) -> Dict[str, Any]:
    """
    检查 parquet 文件结构和内容
    
    Parameters
    ----------
    filepath : str or Path
        parquet 文件路径
    n_rows : int
        显示的行数
    
    Returns
    -------
    dict
        文件信息字典
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")
    
    df = pd.read_parquet(filepath)
    
    info = {
        'filepath': str(filepath),
        'file_size_mb': filepath.stat().st_size / (1024 * 1024),
        'n_rows': len(df),
        'n_columns': len(df.columns),
        'columns': list(df.columns),
        'dtypes': df.dtypes.to_dict(),
        'memory_usage_mb': df.memory_usage(deep=True).sum() / (1024 * 1024),
        'head': df.head(n_rows),
        'tail': df.tail(n_rows),
        'describe': df.describe(),
        'null_counts': df.isnull().sum().to_dict(),
    }
    
    if 'trade_date' in df.columns:
        if df['trade_date'].dtype == 'object':
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
        info['date_range'] = {
            'start': df['trade_date'].min(),
            'end': df['trade_date'].max()
        }
    
    if 'ts_code' in df.columns:
        info['n_codes'] = df['ts_code'].nunique()
    
    return info


def print_parquet_info(filepath: Union[str, Path]) -> None:
    """
    打印 parquet 文件信息
    
    Parameters
    ----------
    filepath : str or Path
        parquet 文件路径
    """
    info = inspect_parquet(filepath)
    
    print("=" * 60)
    print(f"文件: {info['filepath']}")
    print("=" * 60)
    print(f"文件大小: {info['file_size_mb']:.2f} MB")
    print(f"行数: {info['n_rows']:,}")
    print(f"列数: {info['n_columns']}")
    print(f"内存占用: {info['memory_usage_mb']:.2f} MB")
    print()
    
    print("列信息:")
    for col, dtype in info['dtypes'].items():
        null_count = info['null_counts'].get(col, 0)
        print(f"  {col}: {dtype} (null: {null_count})")
    print()
    
    if 'date_range' in info:
        print(f"日期范围: {info['date_range']['start']} ~ {info['date_range']['end']}")
    
    if 'n_codes' in info:
        print(f"股票数量: {info['n_codes']}")
    
    print()
    print("前5行数据:")
    print(info['head'])
    print()
    print("统计摘要:")
    print(info['describe'])
