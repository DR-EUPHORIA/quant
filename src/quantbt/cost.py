import numpy as np
import pandas as pd
from typing import Union, Optional, Callable
from dataclasses import dataclass


@dataclass
class CommissionModel:
    """
    手续费模型
    
    Parameters
    ----------
    rate : float
        手续费率（按成交金额比例），默认 0.0003 (万三)
    min_commission : float
        最低手续费，默认 5 元
    stamp_duty_rate : float
        印花税率（仅卖出），默认 0.001 (千一)
    transfer_fee_rate : float
        过户费率，默认 0.00001 (十万分之一)
    """
    rate: float = 0.0003
    min_commission: float = 5.0
    stamp_duty_rate: float = 0.001
    transfer_fee_rate: float = 0.00001
    
    def calculate(
        self,
        trade_value: Union[float, np.ndarray, pd.Series],
        is_sell: Union[bool, np.ndarray, pd.Series] = False
    ) -> Union[float, np.ndarray]:
        """
        计算手续费
        
        Parameters
        ----------
        trade_value : float or array-like
            成交金额
        is_sell : bool or array-like
            是否为卖出交易
        
        Returns
        -------
        float or np.ndarray
            手续费总额
        """
        trade_value = np.asarray(trade_value)
        is_sell = np.asarray(is_sell)
        
        commission = trade_value * self.rate
        commission = np.maximum(commission, self.min_commission)
        
        stamp_duty = np.where(is_sell, trade_value * self.stamp_duty_rate, 0)
        
        transfer_fee = trade_value * self.transfer_fee_rate
        
        total = commission + stamp_duty + transfer_fee
        
        return total.item() if np.isscalar(trade_value) or trade_value.ndim == 0 else total


@dataclass
class SlippageModel:
    """
    滑点模型
    
    Parameters
    ----------
    fixed_bps : float
        固定滑点（基点），默认 10 bps
    volume_impact : float
        成交量冲击系数，默认 0
    max_slippage_bps : float
        最大滑点限制（基点），默认 None（无限制）
    """
    fixed_bps: float = 10.0
    volume_impact: float = 0.0
    max_slippage_bps: Optional[float] = None
    
    def calculate(
        self,
        price: Union[float, np.ndarray, pd.Series],
        volume: Optional[Union[float, np.ndarray, pd.Series]] = None,
        adv: Optional[Union[float, np.ndarray, pd.Series]] = None,
        is_buy: Union[bool, np.ndarray, pd.Series] = True
    ) -> Union[float, np.ndarray]:
        """
        计算滑点后的执行价格
        
        Parameters
        ----------
        price : float or array-like
            理论价格
        volume : float or array-like, optional
            交易量
        adv : float or array-like, optional
            平均日成交量（用于计算冲击成本）
        is_buy : bool or array-like
            是否为买入交易
        
        Returns
        -------
        float or np.ndarray
            考虑滑点后的执行价格
        """
        price = np.asarray(price)
        is_buy = np.asarray(is_buy)
        
        slippage_bps = self.fixed_bps
        
        if self.volume_impact > 0 and volume is not None and adv is not None:
            volume = np.asarray(volume)
            adv = np.asarray(adv)
            participation_rate = volume / np.maximum(adv, 1)
            impact_bps = self.volume_impact * participation_rate * 10000
            slippage_bps = slippage_bps + impact_bps
        
        if self.max_slippage_bps is not None:
            slippage_bps = np.minimum(slippage_bps, self.max_slippage_bps)
        
        slippage = price * slippage_bps / 10000
        
        execution_price = np.where(
            is_buy,
            price + slippage,
            price - slippage
        )
        
        return execution_price.item() if np.isscalar(price) or price.ndim == 0 else execution_price
    
    def calculate_slippage_cost(
        self,
        price: Union[float, np.ndarray, pd.Series],
        volume: Optional[Union[float, np.ndarray, pd.Series]] = None,
        adv: Optional[Union[float, np.ndarray, pd.Series]] = None,
        is_buy: Union[bool, np.ndarray, pd.Series] = True
    ) -> Union[float, np.ndarray]:
        """
        计算滑点成本（金额）
        
        Parameters
        ----------
        price : float or array-like
            理论价格
        volume : float or array-like, optional
            交易量
        adv : float or array-like, optional
            平均日成交量
        is_buy : bool or array-like
            是否为买入交易
        
        Returns
        -------
        float or np.ndarray
            滑点成本
        """
        price = np.asarray(price)
        execution_price = self.calculate(price, volume, adv, is_buy)
        
        slippage_per_share = np.abs(execution_price - price)
        
        if volume is not None:
            volume = np.asarray(volume)
            return slippage_per_share * volume
        
        return slippage_per_share


class CostModel:
    """
    综合费用模型（手续费 + 滑点）
    
    Parameters
    ----------
    commission : CommissionModel
        手续费模型
    slippage : SlippageModel
        滑点模型
    """
    
    def __init__(
        self,
        commission: Optional[CommissionModel] = None,
        slippage: Optional[SlippageModel] = None
    ):
        self.commission = commission or CommissionModel()
        self.slippage = slippage or SlippageModel()
    
    def calculate_total_cost(
        self,
        price: Union[float, np.ndarray, pd.Series],
        volume: Union[float, np.ndarray, pd.Series],
        is_buy: Union[bool, np.ndarray, pd.Series] = True,
        adv: Optional[Union[float, np.ndarray, pd.Series]] = None
    ) -> Union[float, np.ndarray]:
        """
        计算总交易成本
        
        Parameters
        ----------
        price : float or array-like
            理论价格
        volume : float or array-like
            交易量
        is_buy : bool or array-like
            是否为买入交易
        adv : float or array-like, optional
            平均日成交量
        
        Returns
        -------
        float or np.ndarray
            总交易成本
        """
        price = np.asarray(price)
        volume = np.asarray(volume)
        is_buy = np.asarray(is_buy)
        
        trade_value = price * volume
        
        commission_cost = self.commission.calculate(trade_value, ~is_buy)
        
        slippage_cost = self.slippage.calculate_slippage_cost(price, volume, adv, is_buy)
        
        return commission_cost + slippage_cost
    
    def calculate_cost_bps(
        self,
        price: Union[float, np.ndarray, pd.Series],
        volume: Union[float, np.ndarray, pd.Series],
        is_buy: Union[bool, np.ndarray, pd.Series] = True,
        adv: Optional[Union[float, np.ndarray, pd.Series]] = None
    ) -> Union[float, np.ndarray]:
        """
        计算交易成本（基点）
        
        Parameters
        ----------
        price : float or array-like
            理论价格
        volume : float or array-like
            交易量
        is_buy : bool or array-like
            是否为买入交易
        adv : float or array-like, optional
            平均日成交量
        
        Returns
        -------
        float or np.ndarray
            交易成本（基点）
        """
        price = np.asarray(price)
        volume = np.asarray(volume)
        
        total_cost = self.calculate_total_cost(price, volume, is_buy, adv)
        trade_value = price * volume
        
        return total_cost / trade_value * 10000


def calculate_turnover(
    positions: Union[pd.DataFrame, np.ndarray],
    price: Optional[Union[pd.DataFrame, np.ndarray]] = None
) -> Union[pd.Series, np.ndarray]:
    """
    计算换手率
    
    Parameters
    ----------
    positions : pd.DataFrame or np.ndarray
        持仓权重或持仓金额，shape: (n_periods, n_assets)
    price : pd.DataFrame or np.ndarray, optional
        价格数据，如果 positions 是权重则需要价格来计算金额
    
    Returns
    -------
    pd.Series or np.ndarray
        每期换手率
    """
    if isinstance(positions, pd.DataFrame):
        positions = positions.values
    
    if positions.ndim != 2:
        raise ValueError("positions 必须是二维数组")
    
    position_changes = np.abs(np.diff(positions, axis=0))
    
    turnover = np.sum(position_changes, axis=1)
    
    return turnover


def calculate_annualized_turnover(
    positions: Union[pd.DataFrame, np.ndarray],
    periods_per_year: int = 252
) -> float:
    """
    计算年化换手率
    
    Parameters
    ----------
    positions : pd.DataFrame or np.ndarray
        持仓权重或持仓金额
    periods_per_year : int
        每年交易日数
    
    Returns
    -------
    float
        年化换手率
    """
    turnover = calculate_turnover(positions)
    
    avg_turnover = np.mean(turnover)
    
    return float(avg_turnover * periods_per_year)


def calculate_trade_count(
    positions: Union[pd.DataFrame, np.ndarray],
    threshold: float = 1e-6
) -> int:
    """
    计算交易次数
    
    Parameters
    ----------
    positions : pd.DataFrame or np.ndarray
        持仓权重或持仓金额
    threshold : float
        判断是否有交易的最小变化阈值
    
    Returns
    -------
    int
        总交易次数
    """
    if isinstance(positions, pd.DataFrame):
        positions = positions.values
    
    position_changes = np.abs(np.diff(positions, axis=0))
    
    trades = position_changes > threshold
    
    return int(np.sum(trades))


def estimate_transaction_cost(
    turnover: float,
    commission_rate: float = 0.0003,
    stamp_duty_rate: float = 0.001,
    slippage_bps: float = 10.0
) -> float:
    """
    估算交易成本（年化）
    
    Parameters
    ----------
    turnover : float
        年化换手率
    commission_rate : float
        手续费率
    stamp_duty_rate : float
        印花税率（仅卖出，所以除以2）
    slippage_bps : float
        滑点（基点）
    
    Returns
    -------
    float
        年化交易成本率
    """
    total_cost_bps = (
        commission_rate * 10000 +
        stamp_duty_rate * 10000 / 2 +
        slippage_bps
    )
    
    annual_cost = turnover * total_cost_bps / 10000
    
    return annual_cost


def create_simple_cost_model(
    commission_bps: float = 3.0,
    stamp_duty_bps: float = 10.0,
    slippage_bps: float = 10.0,
    min_commission: float = 5.0
) -> CostModel:
    """
    创建简单的费用模型
    
    Parameters
    ----------
    commission_bps : float
        手续费（基点）
    stamp_duty_bps : float
        印花税（基点，仅卖出）
    slippage_bps : float
        滑点（基点）
    min_commission : float
        最低手续费
    
    Returns
    -------
    CostModel
        综合费用模型
    """
    commission = CommissionModel(
        rate=commission_bps / 10000,
        min_commission=min_commission,
        stamp_duty_rate=stamp_duty_bps / 10000
    )
    
    slippage = SlippageModel(fixed_bps=slippage_bps)
    
    return CostModel(commission=commission, slippage=slippage)
