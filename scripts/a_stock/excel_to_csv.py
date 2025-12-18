import pandas as pd
from pathlib import Path

# ========= 配置区域 =========
# 你的 HS300 Excel 文件路径（请改成你自己的文件名）
INPUT_EXCEL = Path("data/tushare/raw/hs300_constituents.xlsx")

# 输出 CSV 路径
OUTPUT_CSV = Path("data/tushare/universe/hs300_constituents.csv")
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
# ===========================


def normalize_code(code):
    """把 600000 → 600000.SH，000001 → 000001.SZ"""
    code = str(code).strip()

    if len(code) == 6:
        # 沪市以 6 开头
        if code.startswith("6"):
            return code + ".SH"
        else:
            return code + ".SZ"

    # 如果本来就是 600000.SH 格式，则直接返回
    if "." in code:
        return code

    raise ValueError(f"无法识别的股票代码格式: {code}")


def main():
    print(f"读取 Excel 文件: {INPUT_EXCEL}")
    df = pd.read_excel(INPUT_EXCEL)

    print("Excel 前几行：")
    print(df.head())

    # 自动识别列名
    possible_cols = ["ts_code", "证券代码", "代码", "stock_code"]

    col_code = None
    for col in possible_cols:
        if col in df.columns:
            col_code = col
            break

    if col_code is None:
        raise RuntimeError(
            f"Excel 文件中未找到股票代码列，请检查列名是否为：{possible_cols}"
        )

    # 生成 ts_code
    df["ts_code"] = df[col_code].apply(normalize_code)

    # 输出 CSV
    df[["ts_code"]].to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"\n转换完成！CSV 已保存到：\n{OUTPUT_CSV}")
    print("前几行：")
    print(df[["ts_code"]].head())


if __name__ == "__main__":
    main()
