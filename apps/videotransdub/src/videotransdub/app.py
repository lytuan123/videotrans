"""
VideoTransDub - Streamlit Production UI
Dark Mode Dashboard with full pipeline control.

Run: videotransdub-ui
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import sys
import threading
import time
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="VideoTransDub",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Light UI CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp {
        background:
            radial-gradient(circle at top right, rgba(29, 78, 216, 0.10), transparent 26%),
            linear-gradient(180deg, #f7f9fc 0%, #eef3f8 100%);
        color: #1f2328;
    }
    .stSidebar > div:first-child {
        background: rgba(255, 255, 255, 0.92);
        border-right: 1px solid #d8dee4;
    }

    .metric-card {
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid #d8dee4;
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.5rem 0;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
    }
    .metric-card h3 { color: #1f6feb; margin: 0 0 0.5rem 0; font-size: 0.9rem; }
    .metric-card .value { color: #0f172a; font-size: 1.6rem; font-weight: 700; }

    .stage-item {
        display: flex;
        align-items: center;
        padding: 0.6rem 1rem;
        margin: 0.3rem 0;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid #d8dee4;
        border-left: 4px solid #94a3b8;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
    }
    .stage-item.completed { border-left-color: #3fb950; }
    .stage-item.running { border-left-color: #d97706; background: #fff7ed; }
    .stage-item.failed { border-left-color: #f85149; background: #fef2f2; }
    .stage-item.pending { border-left-color: #94a3b8; background: #f8fafc; }
    .stage-label { flex: 1; color: #0f172a; font-weight: 600; }
    .stage-status { font-size: 0.85rem; padding: 0.2rem 0.6rem; border-radius: 12px; }
    .stage-status.completed { background: #dcfce7; color: #166534; }
    .stage-status.running { background: #ffedd5; color: #9a3412; }
    .stage-status.failed { background: #fee2e2; color: #b91c1c; }
    .stage-status.pending { background: #e2e8f0; color: #475569; }

    .srt-editor textarea {
        font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
        font-size: 13px !important;
        background: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }

    .app-header {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(239, 246, 255, 0.96) 100%);
        border: 1px solid #d8dee4;
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
    }
    .app-header h1 {
        color: #0f172a;
        font-size: 1.8rem;
        margin: 0;
        background: linear-gradient(90deg, #1d4ed8, #0f766e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .app-header p { color: #475569; margin: 0.3rem 0 0 0; }

    .stButton > button {
        background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.5rem !important;
        font-weight: 600 !important;
        box-shadow: 0 10px 20px rgba(37, 99, 235, 0.18) !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    }

    [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: rgba(226, 232, 240, 0.92);
        padding: 0.4rem;
        border-radius: 999px;
        border: 1px solid #d8dee4;
        margin-bottom: 1rem;
    }
    button[data-baseweb="tab"] {
        background: #ffffff !important;
        color: #334155 !important;
        border-radius: 999px !important;
        border: 1px solid #d0d7de !important;
        padding: 0.45rem 0.9rem !important;
        font-weight: 600 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: #1d4ed8 !important;
        color: #ffffff !important;
        border-color: #1d4ed8 !important;
    }

    .stCodeBlock, pre {
        background: #0f172a !important;
        border-radius: 12px !important;
    }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants & Paths
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent.parent.parent  # apps/videotransdub/
SRC_DIR = APP_DIR / "src"
CONFIGS_DIR = APP_DIR / "configs"
PRESETS_DIR = CONFIGS_DIR / "presets"
RUNTIME_DIR = APP_DIR / "runtime"
UPLOADS_DIR = RUNTIME_DIR / "uploads"
WORKSPACE_DIR = RUNTIME_DIR / "workspace"
OUTPUT_DIR = RUNTIME_DIR / "output"

for d in [UPLOADS_DIR, WORKSPACE_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

PRESETS = {
    "real_free": "Real Free (Whisper small + Edge-TTS)",
    "fast_free": "Fast Free (Whisper tiny + Edge-TTS)",
    "qwen_free": "Qwen Free (Whisper + Qwen-MT + Edge-TTS)",
    "balanced": "Balanced (Whisper large + Gemini)",
    "quality_api": "Quality API (GPT-4o + Premium TTS)",
    "mock": "Mock (Smoke Test)",
}

STAGE_NAMES = [
    ("stage0_preprocess", "Preprocessing"),
    ("stage1_asr", "Speech-to-Text (STT)"),
    ("stage2_translate", "Translation"),
    ("stage3_tts", "Text-to-Speech (TTS)"),
    ("stage3_5_sync", "Audio Synchronization"),
    ("stage4_mix", "Audio Mixing"),
    ("stage5_video", "Video Rendering"),
    ("stage6_finalize", "Final Muxing"),
]

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
if "pipeline_running" not in st.session_state:
    st.session_state.pipeline_running = False
if "pipeline_error" not in st.session_state:
    st.session_state.pipeline_error = None
if "pipeline_done" not in st.session_state:
    st.session_state.pipeline_done = False
if "current_workspace" not in st.session_state:
    st.session_state.current_workspace = None
if "waiting_for_srt_confirm" not in st.session_state:
    st.session_state.waiting_for_srt_confirm = False
if "pipeline_thread" not in st.session_state:
    st.session_state.pipeline_thread = None
if "pipeline_events" not in st.session_state:
    st.session_state.pipeline_events = queue.Queue()
if "pipeline_started_at" not in st.session_state:
    st.session_state.pipeline_started_at = None
if "pipeline_last_event" not in st.session_state:
    st.session_state.pipeline_last_event = "Idle"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ensure_package_import_path() -> None:
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def poll_pipeline_events() -> None:
    event_queue = st.session_state.pipeline_events
    while True:
        try:
            event = event_queue.get_nowait()
        except queue.Empty:
            break

        event_type = event.get("type")
        if event_type == "workspace":
            st.session_state.current_workspace = event.get("workspace")
            st.session_state.pipeline_last_event = "Workspace prepared"
        elif event_type == "status":
            st.session_state.pipeline_last_event = event.get("message", "Running")
        elif event_type == "paused":
            st.session_state.pipeline_running = False
            st.session_state.waiting_for_srt_confirm = True
            st.session_state.pipeline_last_event = event.get("message", "Paused for subtitle review")
        elif event_type == "done":
            st.session_state.pipeline_done = True
            st.session_state.pipeline_last_event = event.get("message", "Pipeline completed")
        elif event_type == "error":
            st.session_state.pipeline_error = event.get("message", "Unknown pipeline error")
            st.session_state.pipeline_last_event = st.session_state.pipeline_error
        elif event_type == "finished":
            st.session_state.pipeline_running = False
            st.session_state.pipeline_thread = None


def sync_pipeline_thread_state() -> None:
    thread = st.session_state.pipeline_thread
    if (
        st.session_state.pipeline_running
        and thread is not None
        and not thread.is_alive()
        and not st.session_state.pipeline_done
        and not st.session_state.pipeline_error
        and not st.session_state.waiting_for_srt_confirm
    ):
        st.session_state.pipeline_running = False
        st.session_state.pipeline_thread = None
        st.session_state.pipeline_error = (
            "Pipeline stopped before publishing status. Open the log panel below to inspect startup errors."
        )


poll_pipeline_events()
sync_pipeline_thread_state()


def get_gdrive_path() -> Path | None:
    """Return Google Drive mount path if available."""
    gdrive = Path("/content/drive/MyDrive/VideoTransDub")
    if gdrive.parent.parent.exists():
        gdrive.mkdir(parents=True, exist_ok=True)
        return gdrive
    return None


def sync_to_gdrive(source: Path, gdrive: Path) -> None:
    """Copy output files to Google Drive."""
    dest = gdrive / source.name
    if source.is_file():
        shutil.copy2(source, dest)
    elif source.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)


def read_status(workspace: Path) -> dict:
    """Read async status from status.json."""
    status_file = workspace / "manifests" / "status.json"
    if status_file.exists():
        try:
            return json.loads(status_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"current_stage": "unknown", "message": "Waiting...", "progress": 0.0}


def read_checkpoint(workspace: Path) -> dict:
    """Read checkpoint.json for stage statuses."""
    cp_file = workspace / "manifests" / "checkpoint.json"
    if cp_file.exists():
        try:
            return json.loads(cp_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"stages": {}}


def get_system_info() -> dict:
    """Collect system resource info."""
    info = {}
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["ram_used_gb"] = round(mem.used / (1024**3), 1)
        info["ram_total_gb"] = round(mem.total / (1024**3), 1)
        info["ram_pct"] = mem.percent
        disk = psutil.disk_usage("/")
        info["disk_used_gb"] = round(disk.used / (1024**3), 1)
        info["disk_total_gb"] = round(disk.total / (1024**3), 1)
        info["disk_pct"] = disk.percent
    except ImportError:
        info["ram_used_gb"] = "N/A"
        info["ram_total_gb"] = "N/A"
        info["ram_pct"] = 0
        info["disk_used_gb"] = "N/A"
        info["disk_total_gb"] = "N/A"
        info["disk_pct"] = 0

    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            info["gpu_util"] = int(parts[0].strip())
            info["gpu_mem_used"] = int(parts[1].strip())
            info["gpu_mem_total"] = int(parts[2].strip())
        else:
            info["gpu_util"] = None
    except Exception:
        info["gpu_util"] = None

    return info


def run_pipeline_thread(
    video_path: str,
    preset_key: str,
    target_lang: str,
    source_lang: str,
    pause_for_srt: bool,
    event_queue: queue.Queue,
) -> None:
    """Run the pipeline in a background thread."""
    try:
        ensure_package_import_path()
        from videotransdub.orchestrator import VideoTransDubOrchestrator
        from videotransdub.settings import load_settings

        config_paths = [str(CONFIGS_DIR / "default.yaml")]
        preset_file = PRESETS_DIR / f"{preset_key}.yaml"
        if preset_file.exists():
            config_paths.append(str(preset_file))

        overrides = {
            "pipeline": {
                "video_path": video_path,
                "target_language": target_lang,
                "source_language": source_lang,
                "workspace_dir": str(WORKSPACE_DIR),
                "output_dir": str(OUTPUT_DIR),
            }
        }

        settings = load_settings(*config_paths, overrides=overrides)
        orch = VideoTransDubOrchestrator(
            settings,
            pause_after_translate=pause_for_srt,
        )
        event_queue.put({"type": "workspace", "workspace": str(orch.workspace.root)})
        event_queue.put({"type": "status", "message": f"Pipeline started in {orch.workspace.root.name}"})

        if pause_for_srt:
            orch.run_until_translate()
            event_queue.put({"type": "paused", "message": "Translation finished. Waiting for SRT review."})
        else:
            orch.run()
            event_queue.put({"type": "done", "message": "Pipeline completed successfully."})

    except Exception as exc:
        event_queue.put({"type": "error", "message": str(exc)})
    finally:
        event_queue.put({"type": "finished"})


def run_post_translate_thread(workspace_root: str, event_queue: queue.Queue) -> None:
    """Resume pipeline from TTS after SRT edit."""
    try:
        ensure_package_import_path()
        from videotransdub.orchestrator import VideoTransDubOrchestrator
        from videotransdub.settings import load_settings

        workspace = Path(workspace_root)
        manifest_file = workspace / "manifests" / "job.json"
        if not manifest_file.exists():
            raise FileNotFoundError("No job manifest found to resume")

        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        config_paths = [str(CONFIGS_DIR / "default.yaml")]
        # Reload with same settings
        settings = load_settings(*config_paths, overrides={
            "pipeline": {
                "video_path": manifest_data.get("source_video", ""),
                "workspace_dir": str(WORKSPACE_DIR),
                "output_dir": str(OUTPUT_DIR),
                "resume": True,
            }
        })

        orch = VideoTransDubOrchestrator(settings)
        orch.run_from_tts()
        event_queue.put({"type": "workspace", "workspace": str(workspace)})
        event_queue.put({"type": "done", "message": "Pipeline completed successfully."})
    except Exception as exc:
        event_queue.put({"type": "error", "message": str(exc)})
    finally:
        event_queue.put({"type": "finished"})


def render_live_log(workspace: Path, title: str = "Live Pipeline Log", expanded: bool = False) -> None:
    log_file = workspace / "logs" / "pipeline.log"
    with st.expander(title, expanded=expanded):
        if log_file.exists():
            log_text = log_file.read_text(encoding="utf-8")
            st.code(log_text[-5000:] if len(log_text) > 5000 else log_text, language="text")
        else:
            st.caption("Log file will appear after the worker writes its first entry.")


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
st.markdown("""
<div class="app-header">
    <h1>VideoTransDub</h1>
    <p>Production-grade Video Translation & Dubbing Pipeline</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SIDEBAR - Configuration & Upload
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Configuration")

    # File upload
    uploaded_file = st.file_uploader(
        "Upload Video",
        type=["mp4", "mkv", "avi", "mov", "webm", "flv"],
        help="Upload a video file to translate and dub",
    )

    video_path = ""
    if uploaded_file is not None:
        save_path = UPLOADS_DIR / uploaded_file.name
        save_path.write_bytes(uploaded_file.getvalue())
        video_path = str(save_path)
        st.success(f"Uploaded: {uploaded_file.name}")

    # Or specify path directly
    manual_path = st.text_input(
        "Or enter video path",
        placeholder="/content/input/video.mp4",
        help="Direct path to video file (useful on Colab)",
    )
    if manual_path:
        video_path = manual_path

    st.markdown("---")

    # Preset selector
    preset_key = st.selectbox(
        "Pipeline Preset",
        options=list(PRESETS.keys()),
        format_func=lambda k: PRESETS[k],
        index=0,
        help="Choose engine configuration preset",
    )

    # Language settings
    col1, col2 = st.columns(2)
    with col1:
        source_lang = st.selectbox(
            "Source Language",
            options=["auto", "en", "ja", "ko", "zh", "fr", "de", "es", "ru", "vi"],
            index=0,
        )
    with col2:
        target_lang = st.selectbox(
            "Target Language",
            options=["vi", "en", "ja", "ko", "zh", "fr", "de", "es", "ru", "th"],
            index=0,
        )

    st.markdown("---")

    # SRT review option
    pause_for_srt = st.checkbox(
        "Pause for SRT review",
        value=True,
        help="Pause after translation to review/edit subtitles before TTS",
    )

    st.markdown("---")

    # Google Drive sync
    gdrive = get_gdrive_path()
    if gdrive:
        st.markdown(f"**Google Drive**: `{gdrive}`")
        auto_sync = st.checkbox("Auto-sync output to Drive", value=True)
    else:
        auto_sync = False
        st.markdown("*Google Drive not mounted*")

    st.markdown("---")

    # System info
    st.markdown("### System Resources")
    sys_info = get_system_info()

    if sys_info.get("ram_pct"):
        st.markdown(f"""
        <div class="metric-card">
            <h3>RAM</h3>
            <div class="value">{sys_info['ram_used_gb']} / {sys_info['ram_total_gb']} GB</div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(sys_info["ram_pct"] / 100)

    if sys_info.get("disk_pct"):
        st.markdown(f"""
        <div class="metric-card">
            <h3>Disk</h3>
            <div class="value">{sys_info['disk_used_gb']} / {sys_info['disk_total_gb']} GB</div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(sys_info["disk_pct"] / 100)

    if sys_info.get("gpu_util") is not None:
        st.markdown(f"""
        <div class="metric-card">
            <h3>GPU</h3>
            <div class="value">{sys_info['gpu_util']}% | {sys_info['gpu_mem_used']}/{sys_info['gpu_mem_total']} MB</div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(sys_info["gpu_util"] / 100)
    else:
        st.markdown("""
        <div class="metric-card">
            <h3>GPU</h3>
            <div class="value">Not detected</div>
        </div>
        """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# MAIN AREA - Pipeline Control & Status
# ---------------------------------------------------------------------------
tab_pipeline, tab_srt_editor, tab_output = st.tabs(["Pipeline", "SRT Editor", "Output & Preview"])

# ---- Tab 1: Pipeline -------------------------------------------------------
with tab_pipeline:
    col_ctrl, col_status = st.columns([1, 2])

    with col_ctrl:
        st.markdown("### Pipeline Control")

        if not st.session_state.pipeline_running and not st.session_state.waiting_for_srt_confirm:
            if st.button("Start Pipeline", type="primary", use_container_width=True):
                if not video_path:
                    st.error("Please upload a video or enter a video path first.")
                else:
                    st.session_state.pipeline_running = True
                    st.session_state.pipeline_done = False
                    st.session_state.pipeline_error = None
                    st.session_state.waiting_for_srt_confirm = False
                    st.session_state.current_workspace = None
                    st.session_state.pipeline_started_at = time.time()
                    st.session_state.pipeline_last_event = "Starting pipeline worker..."
                    st.session_state.pipeline_events = queue.Queue()

                    thread = threading.Thread(
                        target=run_pipeline_thread,
                        args=(
                            video_path,
                            preset_key,
                            target_lang,
                            source_lang,
                            pause_for_srt,
                            st.session_state.pipeline_events,
                        ),
                        daemon=True,
                    )
                    thread.start()
                    st.session_state.pipeline_thread = thread
                    st.rerun()

        if st.session_state.pipeline_running:
            thread = st.session_state.pipeline_thread
            alive = thread.is_alive() if thread else False
            st.info(
                f"Pipeline is running. Worker thread: {'alive' if alive else 'stopped'}. "
                f"Last event: {st.session_state.pipeline_last_event}"
            )
            if st.session_state.pipeline_started_at:
                elapsed = int(time.time() - st.session_state.pipeline_started_at)
                st.caption(f"Elapsed: {elapsed}s")
            st.button("Refresh Status", on_click=lambda: None, use_container_width=True)

        if st.session_state.waiting_for_srt_confirm:
            st.warning("Pipeline paused. Review subtitles in the SRT Editor tab, then click Continue.")
            if st.button("Continue Pipeline (after SRT review)", type="primary", use_container_width=True):
                st.session_state.pipeline_running = True
                st.session_state.waiting_for_srt_confirm = False
                st.session_state.pipeline_last_event = "Resuming from TTS..."
                st.session_state.pipeline_events = queue.Queue()
                thread = threading.Thread(
                    target=run_post_translate_thread,
                    args=(str(st.session_state.current_workspace), st.session_state.pipeline_events),
                    daemon=True,
                )
                thread.start()
                st.session_state.pipeline_thread = thread
                st.rerun()

        if st.session_state.pipeline_error:
            st.error(f"Pipeline error: {st.session_state.pipeline_error}")

        if st.session_state.pipeline_done and not st.session_state.pipeline_running:
            st.success("Pipeline completed successfully!")

    with col_status:
        st.markdown("### Stage Progress")

        workspace = st.session_state.current_workspace
        if workspace and Path(workspace).exists():
            checkpoint = read_checkpoint(Path(workspace))
            status = read_status(Path(workspace))
            stages_data = checkpoint.get("stages", {})

            # Overall progress bar
            completed_count = sum(1 for s in stages_data.values() if s.get("status") == "completed")
            total_stages = len(STAGE_NAMES)
            file_progress = float(status.get("progress") or 0.0)
            overall_pct = max(file_progress, completed_count / total_stages if total_stages else 0)
            st.progress(min(overall_pct, 1.0), text=f"Overall: {completed_count}/{total_stages} stages")
            st.caption(f"Workspace: `{workspace}`")
            if status.get("updated_at"):
                st.caption(f"Last status update: {status['updated_at']}")

            # Per-stage status
            for stage_key, stage_label in STAGE_NAMES:
                stage_info = stages_data.get(stage_key, {})
                stage_status = stage_info.get("status", "pending")

                status_class = stage_status if stage_status in ("completed", "running", "failed") else "pending"
                st.markdown(f"""
                <div class="stage-item {status_class}">
                    <span class="stage-label">{stage_label}</span>
                    <span class="stage-status {status_class}">{stage_status.upper()}</span>
                </div>
                """, unsafe_allow_html=True)

            # Live status message
            if status.get("message"):
                st.caption(f"Status: {status['message']}")
            render_live_log(Path(workspace), expanded=st.session_state.pipeline_running)
        elif st.session_state.pipeline_running:
            st.info("Pipeline worker is starting. Workspace and log will appear here after initialization.")

            for _, stage_label in STAGE_NAMES:
                st.markdown(f"""
                <div class="stage-item pending">
                    <span class="stage-label">{stage_label}</span>
                    <span class="stage-status pending">WAITING</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("*No active pipeline. Upload a video and start the pipeline.*")

            for _, stage_label in STAGE_NAMES:
                st.markdown(f"""
                <div class="stage-item pending">
                    <span class="stage-label">{stage_label}</span>
                    <span class="stage-status pending">PENDING</span>
                </div>
                """, unsafe_allow_html=True)

# ---- Tab 2: SRT Editor -----------------------------------------------------
with tab_srt_editor:
    st.markdown("### Subtitle Editor")
    st.caption("Review and edit the translated subtitles before TTS synthesis.")

    workspace = st.session_state.current_workspace
    srt_path = None
    srt_content = ""

    if workspace:
        candidate = Path(workspace) / "stage2" / "transcript_translated.srt"
        if candidate.exists():
            srt_path = candidate
            srt_content = candidate.read_text(encoding="utf-8")

    if srt_path and srt_content:
        col_orig, col_edit = st.columns(2)

        with col_orig:
            st.markdown("**Original Transcript**")
            raw_srt_path = Path(workspace) / "stage1" / "transcript_raw.srt"
            if raw_srt_path.exists():
                st.text_area(
                    "Original (read-only)",
                    value=raw_srt_path.read_text(encoding="utf-8"),
                    height=500,
                    disabled=True,
                    key="srt_original",
                )
            else:
                st.info("Original transcript not yet available.")

        with col_edit:
            st.markdown("**Translated Subtitle (editable)**")
            edited_srt = st.text_area(
                "Edit translated SRT",
                value=srt_content,
                height=500,
                key="srt_editor",
            )

            if st.button("Save Changes", use_container_width=True):
                srt_path.write_text(edited_srt, encoding="utf-8")
                st.success("Subtitles saved!")

                # Also update JSON
                try:
                    ensure_package_import_path()
                    from videotransdub.utils.commands import write_json
                    from videotransdub.utils.srt import read_srt
                    segments = read_srt(srt_path)
                    json_path = Path(workspace) / "stage2" / "transcript_translated.json"
                    write_json(json_path, {"segments": [s.model_dump(mode="json") for s in segments]})
                except Exception:
                    pass
    else:
        st.info("No translated subtitles available yet. Run the pipeline first (stages 0-2).")

# ---- Tab 3: Output & Preview -----------------------------------------------
with tab_output:
    st.markdown("### Output & Preview")

    workspace = st.session_state.current_workspace
    if workspace:
        output_dir = Path(workspace) / "output"
        final_video = output_dir / "final.mp4"

        if final_video.exists() and final_video.stat().st_size > 100:
            st.markdown("**Result Video**")
            st.video(str(final_video))

            # Download button
            with open(final_video, "rb") as f:
                st.download_button(
                    label="Download Video",
                    data=f.read(),
                    file_name=final_video.name,
                    mime="video/mp4",
                    use_container_width=True,
                )

            # Google Drive sync
            gdrive = get_gdrive_path()
            if gdrive and auto_sync:
                sync_to_gdrive(final_video, gdrive)
                st.success(f"Synced to Google Drive: {gdrive / final_video.name}")
            elif gdrive:
                if st.button("Sync to Google Drive"):
                    sync_to_gdrive(final_video, gdrive)
                    st.success("Synced!")
        else:
            st.info("Final video not yet available. Complete the pipeline first.")

        # Show intermediate artifacts
        with st.expander("Intermediate Artifacts"):
            for stage_key, stage_label in STAGE_NAMES:
                stage_dir = Path(workspace) / stage_key.replace("stage", "stage").split("_")[0]
                # Map stage names to actual directories
                dir_map = {
                    "stage0_preprocess": "stage0",
                    "stage1_asr": "stage1",
                    "stage2_translate": "stage2",
                    "stage3_tts": "stage3",
                    "stage3_5_sync": "stage3_5",
                    "stage4_mix": "stage4",
                    "stage5_video": "stage5",
                    "stage6_finalize": "output",
                }
                actual_dir = Path(workspace) / dir_map.get(stage_key, "")
                if actual_dir.exists():
                    files = list(actual_dir.iterdir())
                    if files:
                        st.markdown(f"**{stage_label}**")
                        for f in sorted(files):
                            st.text(f"  {f.name} ({f.stat().st_size:,} bytes)")

        render_live_log(Path(workspace), title="Pipeline Log", expanded=False)
    else:
        st.info("No pipeline output yet. Start a pipeline to see results here.")

# ---------------------------------------------------------------------------
# Auto-refresh while pipeline is running
# ---------------------------------------------------------------------------
if st.session_state.pipeline_running:
    time.sleep(2)
    st.rerun()
