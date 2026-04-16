"""
VideoTransDub - Streamlit Production UI
Dark Mode Dashboard with full pipeline control.

Run: videotransdub-ui
"""
from __future__ import annotations

import json
import os
import shutil
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
# Dark Mode CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Dark theme overrides */
    .stApp { background-color: #0e1117; color: #fafafa; }
    .stSidebar > div:first-child { background-color: #161b22; }

    /* Cards */
    .metric-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.5rem 0;
    }
    .metric-card h3 { color: #58a6ff; margin: 0 0 0.5rem 0; font-size: 0.9rem; }
    .metric-card .value { color: #f0f6fc; font-size: 1.8rem; font-weight: 700; }

    /* Stage progress */
    .stage-item {
        display: flex;
        align-items: center;
        padding: 0.6rem 1rem;
        margin: 0.3rem 0;
        border-radius: 8px;
        background: #161b22;
        border-left: 4px solid #30363d;
    }
    .stage-item.completed { border-left-color: #3fb950; }
    .stage-item.running { border-left-color: #d29922; background: #1c1e23; }
    .stage-item.failed { border-left-color: #f85149; }
    .stage-item.pending { border-left-color: #484f58; }
    .stage-label { flex: 1; color: #c9d1d9; font-weight: 500; }
    .stage-status { font-size: 0.85rem; padding: 0.2rem 0.6rem; border-radius: 12px; }
    .stage-status.completed { background: #0d3220; color: #3fb950; }
    .stage-status.running { background: #3d2e00; color: #d29922; }
    .stage-status.failed { background: #3d1418; color: #f85149; }
    .stage-status.pending { background: #21262d; color: #484f58; }

    /* SRT Editor */
    .srt-editor textarea {
        font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
        font-size: 13px !important;
        background: #0d1117 !important;
        color: #c9d1d9 !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
    }

    /* Header */
    .app-header {
        background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
        border: 1px solid #30363d;
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
    }
    .app-header h1 {
        color: #f0f6fc;
        font-size: 1.8rem;
        margin: 0;
        background: linear-gradient(90deg, #58a6ff, #bc8cff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .app-header p { color: #8b949e; margin: 0.3rem 0 0 0; }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #238636, #2ea043) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.5rem !important;
        font-weight: 600 !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2ea043, #3fb950) !important;
    }

    /* Hide default streamlit elements */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants & Paths
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent.parent.parent  # apps/videotransdub/
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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
):
    """Run the pipeline in a background thread."""
    try:
        from .settings import load_settings
        from .orchestrator import VideoTransDubOrchestrator

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
        st.session_state.current_workspace = orch.workspace.root

        if pause_for_srt:
            orch.run_until_translate()
            st.session_state.waiting_for_srt_confirm = True
        else:
            orch.run()

        st.session_state.pipeline_done = True
    except Exception as exc:
        st.session_state.pipeline_error = str(exc)
    finally:
        st.session_state.pipeline_running = False


def run_post_translate_thread():
    """Resume pipeline from TTS after SRT edit."""
    try:
        from .settings import load_settings
        from .orchestrator import VideoTransDubOrchestrator

        workspace = st.session_state.current_workspace
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
        st.session_state.pipeline_done = True
    except Exception as exc:
        st.session_state.pipeline_error = str(exc)
    finally:
        st.session_state.pipeline_running = False
        st.session_state.waiting_for_srt_confirm = False


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

                    thread = threading.Thread(
                        target=run_pipeline_thread,
                        args=(video_path, preset_key, target_lang, source_lang, pause_for_srt),
                        daemon=True,
                    )
                    thread.start()
                    st.session_state.pipeline_thread = thread
                    st.rerun()

        if st.session_state.pipeline_running:
            st.info("Pipeline is running... Status updates automatically from checkpoint.")
            st.button("Refresh Status", on_click=lambda: None)

        if st.session_state.waiting_for_srt_confirm:
            st.warning("Pipeline paused. Review subtitles in the SRT Editor tab, then click Continue.")
            if st.button("Continue Pipeline (after SRT review)", type="primary", use_container_width=True):
                st.session_state.pipeline_running = True
                st.session_state.waiting_for_srt_confirm = False
                thread = threading.Thread(target=run_post_translate_thread, daemon=True)
                thread.start()
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
            overall_pct = completed_count / total_stages if total_stages else 0
            st.progress(overall_pct, text=f"Overall: {completed_count}/{total_stages} stages")

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
                    from .utils.srt import read_srt
                    from .utils.commands import write_json
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

        # Pipeline log
        with st.expander("Pipeline Log"):
            log_file = Path(workspace) / "logs" / "pipeline.log"
            if log_file.exists():
                log_text = log_file.read_text(encoding="utf-8")
                st.code(log_text[-5000:] if len(log_text) > 5000 else log_text, language="text")
            else:
                st.info("No log file yet.")
    else:
        st.info("No pipeline output yet. Start a pipeline to see results here.")

# ---------------------------------------------------------------------------
# Auto-refresh while pipeline is running
# ---------------------------------------------------------------------------
if st.session_state.pipeline_running:
    time.sleep(2)
    st.rerun()
