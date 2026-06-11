#!/bin/bash
# ============================================================
# setup_wsl.sh — ezto-agent WSL conda 环境一键配置
#
# 用法: bash /mnt/d/code/ezto_video/ezto-agent/setup_wsl.sh
#
# 注意: WSL 下 conda create 的并行 I/O 可能 [Errno 11]，
#       脚本会优先复用已有的 py312/ezto 环境。
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== ezto-agent WSL conda 环境配置 ==="
echo ""

# ── 确保 Miniconda 已安装 ──
MINICONDA_DIR="$HOME/miniconda3"

if [ ! -d "$MINICONDA_DIR" ]; then
    echo "[1/4] 未检测到 Miniconda，正在安装..."
    wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p "$MINICONDA_DIR"
    rm /tmp/miniconda.sh
else
    echo "[1/4] Miniconda 已存在: $MINICONDA_DIR"
fi

# ── 初始化 conda ──
source "$MINICONDA_DIR/etc/profile.d/conda.sh"

# ── 挑一个可用的 Python 3.12 环境 ──
# 优先顺序: ezto > py312 > 新建 ezto
ENV_NAME=""
for candidate in ezto py312; do
    if conda info --envs | grep -qP "^\s*${candidate}\s"; then
        ENV_NAME="$candidate"
        echo "[2/4] 使用已有 conda 环境: $ENV_NAME"
        break
    fi
done

if [ -z "$ENV_NAME" ]; then
    ENV_NAME="ezto"
    echo "[2/4] 创建 conda 环境 '$ENV_NAME' (Python 3.12)..."
    # 单线程提取避免 WSL [Errno 11]
    CONDA_EXTRACT_THREADS=1 conda create -y -n "$ENV_NAME" python=3.12 pip -c defaults
fi

# ── 安装项目依赖 ──
echo "[3/4] 安装项目依赖..."
conda activate "$ENV_NAME"
pip install --upgrade pip
pip install -e "$SCRIPT_DIR"

echo "[4/4] 配置完成！"
echo ""
echo "============================================"
echo "  使用方式:"
echo "    cd /mnt/d/code/ezto_video/ezto-agent"
echo "    conda activate $ENV_NAME"
echo "    uvicorn app.api.server:app --reload --port 8001"
echo "============================================"
