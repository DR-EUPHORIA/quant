import pyarrow.parquet as pq

paths = [
    "data/tushare/raw/daily_20150101_20241231.parquet",
    "data/tushare/raw/daily_basic_20150101_20241231.parquet",
    "data/tushare/raw/hs300_constituents_latest.parquet",
]

for p in paths:
    pf = pq.ParquetFile(p)
    schema = pf.schema_arrow
    print("\n===", p, "===")
    print("num_row_groups:", pf.num_row_groups)
    print("num_cols:", len(schema.names))
    print("columns:", schema.names)
