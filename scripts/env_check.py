import importlib
import sys

REQUIRED = [
    # 基础
    "numpy",
    "pandas",

    # parquet 读写（关键）
    "pyarrow",
    "pyarrow.dataset",
    "pyarrow.parquet",

    # 可视化
    "matplotlib",

    # 回测/统计（你 Dockerfile 已装，但验证一下）
    "scipy",
    "statsmodels",

    # 数据源
    "tushare",
    "akshare",

    # 测试（后续工程化需要）
    "pytest",
]

missing = []
ok = []

for m in REQUIRED:
    try:
        importlib.import_module(m)
        ok.append(m)
    except Exception as e:
        missing.append((m, repr(e)))

print("Python:", sys.version)
print("\nOK modules:")
for m in ok:
    print("  -", m)

print("\nMissing/failed modules:")
for m, e in missing:
    print("  -", m, "=>", e)

# 额外：打印关键版本，便于后续复现
try:
    import numpy, pandas, pyarrow, matplotlib, tushare, akshare
    print("\nVersions:")
    print("  numpy      =", numpy.__version__)
    print("  pandas     =", pandas.__version__)
    print("  pyarrow    =", pyarrow.__version__)
    print("  matplotlib =", matplotlib.__version__)
    print("  tushare    =", tushare.__version__)
    print("  akshare    =", akshare.__version__)
except Exception as e:
    print("\nVersion print failed:", repr(e))
