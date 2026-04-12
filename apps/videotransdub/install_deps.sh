#!/usr/bin/env bash
# ============================================================================
# VideoTransDub - No-fail Colab Environment Setup
# Run once at the start of a Colab session.
# Usage: bash apps/videotransdub/install_deps.sh
# ============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[SETUP]${NC} $*"; }
ok()   { echo -e "${GREEN}[  OK ]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# ---- 1. System packages (ffmpeg, ffprobe) ----------------------------------
log "Installing system packages..."
if command -v apt-get &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq ffmpeg libsndfile1 > /dev/null 2>&1
    ok "apt-get packages installed"
elif command -v yum &>/dev/null; then
    yum install -y -q ffmpeg libsndfile > /dev/null 2>&1
    ok "yum packages installed"
else
    warn "No apt-get or yum found. Ensure ffmpeg is installed manually."
fi

# Verify ffmpeg/ffprobe
FFMPEG_VERSION=$(ffmpeg -version 2>/dev/null | head -1 || true)
FFPROBE_VERSION=$(ffprobe -version 2>/dev/null | head -1 || true)

if [ -z "$FFMPEG_VERSION" ]; then
    fail "ffmpeg not found after install! Please install manually."
fi
ok "ffmpeg: $FFMPEG_VERSION"

if [ -z "$FFPROBE_VERSION" ]; then
    warn "ffprobe not found (some features may be limited)"
else
    ok "ffprobe: $FFPROBE_VERSION"
fi

# ---- 2. Python dependencies ------------------------------------------------
log "Installing Python dependencies..."

pip install --quiet --upgrade pip

# Core
pip install --quiet \
    "pydantic>=2,<3" \
    "PyYAML>=6,<7"

# ASR - faster-whisper
pip install --quiet \
    "faster-whisper>=1.0.0" \
    "ctranslate2>=4.0.0"

# TTS - Edge TTS
pip install --quiet "edge-tts>=6.1.0"

# Video processing - OpenCV
pip install --quiet "opencv-python-headless>=4.8.0"

# Translation - Alibaba Qwen/DashScope
pip install --quiet "dashscope>=1.20.0"

# UI - Streamlit
pip install --quiet \
    "streamlit>=1.30.0"

# Colab utilities
pip install --quiet "ipywidgets>=8.0.0"

ok "Python packages installed"

# ---- 3. Install videotransdub package in dev mode --------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    log "Installing videotransdub package..."
    pip install --quiet -e "$SCRIPT_DIR"
    ok "videotransdub installed"
else
    warn "pyproject.toml not found at $SCRIPT_DIR. Skipping package install."
fi

# ---- 4. Create runtime directories ----------------------------------------
log "Creating runtime directories..."
RUNTIME_DIR="${SCRIPT_DIR}/runtime"
mkdir -p "$RUNTIME_DIR/workspace"
mkdir -p "$RUNTIME_DIR/output"
mkdir -p "$RUNTIME_DIR/uploads"
ok "Runtime dirs ready: $RUNTIME_DIR"

# ---- 5. Cloudflare tunnel (for Streamlit remote access) --------------------
log "Installing Cloudflare tunnel (cloudflared)..."
if ! command -v cloudflared &>/dev/null; then
    if command -v apt-get &>/dev/null; then
        wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -O /tmp/cloudflared.deb
        dpkg -i /tmp/cloudflared.deb > /dev/null 2>&1 || apt-get install -f -y -qq > /dev/null 2>&1
        rm -f /tmp/cloudflared.deb
    fi
fi

if command -v cloudflared &>/dev/null; then
    ok "cloudflared: $(cloudflared --version 2>&1 | head -1)"
else
    warn "cloudflared not installed. Streamlit will only be accessible via Colab proxy."
fi

# ---- 6. GPU check ----------------------------------------------------------
log "Checking GPU availability..."
if command -v nvidia-smi &>/dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "unknown")
    ok "GPU detected: $GPU_INFO"
else
    warn "No GPU detected. ASR will run on CPU (slower)."
fi

# ---- 7. Summary ------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  VideoTransDub Setup Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Next steps:"
echo "    1. Upload a video to runtime/uploads/"
echo "    2. Run Streamlit UI: streamlit run apps/videotransdub/src/videotransdub/app.py"
echo "    3. Or use CLI: python -m videotransdub.cli run --config ..."
echo ""
