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

WARNINGS=()

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    PYTHON_BIN="${PYTHON_BIN:-python}"
fi
if ! command -v "$PYTHON_BIN" &>/dev/null; then
    fail "python interpreter not found"
fi
PIP_CMD=("$PYTHON_BIN" -m pip)

record_warning() {
    WARNINGS+=("$1")
    warn "$1"
}

try_run() {
    local description="$1"
    shift
    if "$@"; then
        ok "$description"
    else
        record_warning "$description failed"
    fi
    return 0
}

# ---- 1. System packages (ffmpeg, ffprobe) ----------------------------------
log "Installing system packages..."
if command -v apt-get &>/dev/null; then
    if command -v sudo &>/dev/null; then
        try_run "apt-get update" sudo apt-get update -qq
        try_run "apt-get install ffmpeg libsndfile1" sudo apt-get install -y -qq ffmpeg libsndfile1
    else
        try_run "apt-get update" apt-get update -qq
        try_run "apt-get install ffmpeg libsndfile1" apt-get install -y -qq ffmpeg libsndfile1
    fi
elif command -v yum &>/dev/null; then
    try_run "yum install ffmpeg libsndfile" yum install -y -q ffmpeg libsndfile
else
    record_warning "No apt-get or yum found. Ensure ffmpeg is installed manually."
fi

# Verify ffmpeg/ffprobe
FFMPEG_VERSION=$(ffmpeg -version 2>/dev/null | head -1 || true)
FFPROBE_VERSION=$(ffprobe -version 2>/dev/null | head -1 || true)

if [ -z "$FFMPEG_VERSION" ]; then
    record_warning "ffmpeg not found after setup. Real video rendering will be unavailable until installed."
else
    ok "ffmpeg: $FFMPEG_VERSION"
fi

if [ -z "$FFPROBE_VERSION" ]; then
    record_warning "ffprobe not found (some features may be limited)"
else
    ok "ffprobe: $FFPROBE_VERSION"
fi

# ---- 2. Python dependencies ------------------------------------------------
log "Installing Python dependencies..."

try_run "pip upgrade" "${PIP_CMD[@]}" install --quiet --upgrade pip

# Core
try_run "Python core dependencies" "${PIP_CMD[@]}" install --quiet \
    "pydantic>=2,<3" \
    "PyYAML>=6,<7"

# ASR - faster-whisper
try_run "ASR dependencies" "${PIP_CMD[@]}" install --quiet \
    "faster-whisper>=1.0.0" \
    "ctranslate2>=4.0.0"

# TTS - Edge TTS
try_run "Edge-TTS dependency" "${PIP_CMD[@]}" install --quiet "edge-tts>=6.1.0"

# Video processing - OpenCV
try_run "OpenCV dependency" "${PIP_CMD[@]}" install --quiet "opencv-python-headless>=4.8.0"

# Translation - Alibaba Qwen/DashScope
try_run "DashScope dependency" "${PIP_CMD[@]}" install --quiet "dashscope>=1.20.0"

# UI - Streamlit
try_run "Streamlit UI dependency" "${PIP_CMD[@]}" install --quiet \
    "streamlit>=1.30.0"

# Colab utilities
try_run "ipywidgets dependency" "${PIP_CMD[@]}" install --quiet "ipywidgets>=8.0.0"

if [ "${#WARNINGS[@]}" -eq 0 ]; then
    ok "Python packages installed"
fi

# ---- 3. Install videotransdub package in dev mode --------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    log "Installing videotransdub package..."
    if ! "${PIP_CMD[@]}" install --quiet -e "$SCRIPT_DIR"; then
        if "${PIP_CMD[@]}" install --quiet --no-build-isolation --no-deps -e "$SCRIPT_DIR"; then
            ok "videotransdub installed (offline fallback)"
        else
            fail "videotransdub package install failed"
        fi
    else
        ok "videotransdub installed"
    fi
    if "$PYTHON_BIN" -c "import videotransdub, sys; print(videotransdub.__file__)"; then
        ok "videotransdub import verified in active Python environment"
    else
        fail "videotransdub import verification failed after install"
    fi
else
    fail "pyproject.toml not found at $SCRIPT_DIR. Cannot install videotransdub."
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
        if command -v sudo &>/dev/null; then
            wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -O /tmp/cloudflared.deb || true
            sudo dpkg -i /tmp/cloudflared.deb > /dev/null 2>&1 || sudo apt-get install -f -y -qq > /dev/null 2>&1 || true
        else
            wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -O /tmp/cloudflared.deb || true
            dpkg -i /tmp/cloudflared.deb > /dev/null 2>&1 || apt-get install -f -y -qq > /dev/null 2>&1 || true
        fi
        rm -f /tmp/cloudflared.deb
    fi
fi

if command -v cloudflared &>/dev/null; then
    ok "cloudflared: $(cloudflared --version 2>&1 | head -1)"
else
    record_warning "cloudflared not installed. Streamlit will only be accessible via Colab proxy."
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
if [ "${#WARNINGS[@]}" -gt 0 ]; then
    echo "  Warnings:"
    for item in "${WARNINGS[@]}"; do
        echo "    - $item"
    done
    echo ""
fi
echo "  Next steps:"
echo "    1. Preflight: videotransdub preflight --config apps/videotransdub/configs/default.yaml --config apps/videotransdub/configs/presets/fast_free.yaml --video-path /path/to/video.mp4 --check-ui"
echo "    2. Smoke test: videotransdub smoke --config apps/videotransdub/configs/default.yaml --config apps/videotransdub/configs/presets/fast_free.yaml --video-path /path/to/video.mp4 --target-language vi --clip-seconds 15"
echo "    3. Run Streamlit UI: videotransdub-ui"
echo "    4. Or use CLI: videotransdub run --config ..."
echo ""
