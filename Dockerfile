# 1. 以你本地已有的 Python 镜像为基础
FROM python:3.11-slim

# 2. 安装系统级依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    wget \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 3. 设置时区为上海
ENV TZ=Asia/Shanghai

# 4. 安装常用科学计算 / 量化库
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    pyarrow \
    scipy \
    numba \
    statsmodels \
    matplotlib \
    seaborn \
    jupyterlab \
    backtrader \
    akshare \
    tushare


# 5. 工作目录（后面我们把代码挂载到这里）
WORKDIR /workspace

# 6. 默认进入 bash，方便开发调试
CMD ["bash"]
