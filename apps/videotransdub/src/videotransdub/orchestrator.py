from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .checkpoint import CheckpointManager
from .logging import build_logger
from .models import JobManifest, StageResult, SubtitleSegment, utc_now
from .settings import AppSettings
from .workspace import Workspace

ProgressCallback = Callable[[str, str, float], None]
"""(stage_name, status_message, progress_0_to_1) -> None"""


@dataclass
class PipelineContext:
    settings: AppSettings
    workspace: Workspace
    checkpoint: CheckpointManager
    logger: Any
    artifacts: dict[str, str] = field(default_factory=dict)
    segments: list[SubtitleSegment] = field(default_factory=list)
    translated_segments: list[SubtitleSegment] = field(default_factory=list)
    voice_over_segments: list[SubtitleSegment] = field(default_factory=list)
    manifest: JobManifest | None = None
    on_progress: ProgressCallback | None = None

    @property
    def log_path(self) -> Path:
        return self.workspace.log_file

    def persist_manifest(self) -> None:
        if self.manifest is None:
            return
        self.manifest.artifacts = dict(self.artifacts)
        self.manifest.dump_json(self.workspace.manifest_file)

    def report_progress(self, stage: str, message: str, pct: float = 0.0) -> None:
        if self.on_progress:
            self.on_progress(stage, message, pct)
        self._write_status(stage, message, pct)

    def _write_status(self, stage: str, message: str, pct: float) -> None:
        status_file = self.workspace.root / "manifests" / "status.json"
        status_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_stage": stage,
            "message": message,
            "progress": round(pct, 3),
            "updated_at": utc_now(),
        }
        status_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class VideoTransDubOrchestrator:
    STAGE_LABELS = {
        "stage0_preprocess": "Preprocessing",
        "stage1_asr": "Speech-to-Text",
        "stage2_translate": "Translation",
        "stage3_tts": "Text-to-Speech",
        "stage3_5_sync": "Audio Sync",
        "stage4_mix": "Audio Mix",
        "stage5_video": "Video Render",
        "stage6_finalize": "Finalize",
    }

    def __init__(
        self,
        settings: AppSettings,
        on_progress: ProgressCallback | None = None,
        pause_after_translate: bool = False,
    ) -> None:
        self.settings = settings
        self.pause_after_translate = pause_after_translate
        self.workspace = Workspace.from_settings(settings)
        self.workspace.prepare()
        self.logger = build_logger(self.workspace.log_file)
        self.checkpoint = CheckpointManager(self.workspace.checkpoint_file)
        source_video = settings.pipeline.video_path or ""
        manifest = JobManifest(
            job_id=self.workspace.job_id,
            source_video=source_video,
            workspace_root=str(self.workspace.root),
        )
        if settings.pipeline.resume and self.workspace.manifest_file.exists():
            manifest = JobManifest.model_validate_json(self.workspace.manifest_file.read_text(encoding="utf-8"))
        self.ctx = PipelineContext(
            settings=settings,
            workspace=self.workspace,
            checkpoint=self.checkpoint,
            logger=self.logger,
            artifacts=dict(manifest.artifacts),
            manifest=manifest,
            on_progress=on_progress,
        )

    def run(self) -> JobManifest:
        return self._run_stages()

    def run_until_translate(self) -> JobManifest:
        """Run stages 0-2 only (preprocess -> ASR -> translate), then pause."""
        return self._run_stages(stop_after="stage2_translate")

    def run_from_tts(self) -> JobManifest:
        """Run stages 3-6 (TTS -> sync -> mix -> video -> finalize)."""
        return self._run_stages(start_from="stage3_tts")

    def _run_stages(
        self,
        stop_after: str | None = None,
        start_from: str | None = None,
    ) -> JobManifest:
        from .stages.audio_mix import AudioMixStage
        from .stages.audio_sync import AudioSyncStage
        from .stages.asr import ASRStage
        from .stages.finalize import FinalizeStage
        from .stages.preprocess import PreprocessStage
        from .stages.translate import TranslateStage
        from .stages.tts import TTSStage
        from .stages.video import VideoStage

        all_stages = [
            PreprocessStage(),
            ASRStage(),
            TranslateStage(),
            TTSStage(),
            AudioSyncStage(),
            AudioMixStage(),
            VideoStage(),
            FinalizeStage(),
        ]

        # Filter stages based on start/stop
        stages = all_stages
        if start_from:
            idx = next((i for i, s in enumerate(all_stages) if s.name == start_from), 0)
            stages = all_stages[idx:]
        if stop_after:
            idx = next((i for i, s in enumerate(all_stages) if s.name == stop_after), len(all_stages) - 1)
            stages = stages[:idx + 1] if not start_from else stages

        total = len(stages)
        for i, stage in enumerate(stages):
            label = self.STAGE_LABELS.get(stage.name, stage.name)

            if self.settings.pipeline.resume and self.checkpoint.is_completed(stage.name):
                self.logger.info("skip %s (checkpoint)", stage.name)
                self.ctx.manifest.stages[stage.name] = StageResult(stage=stage.name, status="skipped")
                self.ctx.persist_manifest()
                self.ctx.report_progress(stage.name, f"{label}: skipped (cached)", (i + 1) / total)
                continue

            self.logger.info("run %s", stage.name)
            self.ctx.report_progress(stage.name, f"{label}: running...", i / total)
            self.checkpoint.mark_running(stage.name)
            try:
                outputs = stage.run(self.ctx)
                self.ctx.artifacts.update(outputs)
                self.checkpoint.mark_completed(stage.name, outputs=outputs)
                self.ctx.manifest.stages[stage.name] = StageResult(
                    stage=stage.name, status="completed", outputs=outputs, completed_at=utc_now()
                )
                self.ctx.persist_manifest()
                self.ctx.report_progress(stage.name, f"{label}: done", (i + 1) / total)
            except Exception as exc:
                self.ctx.manifest.stages[stage.name] = StageResult(
                    stage=stage.name, status="failed", notes=[str(exc)], completed_at=utc_now()
                )
                self.checkpoint.mark_failed(stage.name, str(exc))
                self.ctx.persist_manifest()
                self.ctx.report_progress(stage.name, f"{label}: FAILED - {exc}", (i + 1) / total)
                raise

            if self.pause_after_translate and stage.name == "stage2_translate":
                self.ctx.report_progress(stage.name, "Paused for SRT review", (i + 1) / total)
                break

        assert self.ctx.manifest is not None
        return self.ctx.manifest

    def get_translated_srt_path(self) -> Path | None:
        srt = self.ctx.artifacts.get("transcript_translated_srt")
        if srt and Path(srt).exists():
            return Path(srt)
        return None

    def update_translated_srt(self, srt_content: str) -> None:
        """Overwrite the translated SRT and invalidate downstream checkpoints."""
        srt_path = self.ctx.artifacts.get("transcript_translated_srt")
        if not srt_path:
            srt_path = str(self.ctx.workspace.stage_dir("stage2") / "transcript_translated.srt")
        Path(srt_path).write_text(srt_content, encoding="utf-8")
        self.ctx.artifacts["transcript_translated_srt"] = srt_path
        # Invalidate stages after translate
        for stage_name in ["stage3_tts", "stage3_5_sync", "stage4_mix", "stage5_video", "stage6_finalize"]:
            entry = self.checkpoint.stage(stage_name)
            if entry.get("status") == "completed":
                entry["status"] = "invalidated"
                self.checkpoint.save()
        self.logger.info("Updated translated SRT and invalidated downstream stages")

    @staticmethod
    def read_status(workspace_root: Path) -> dict[str, Any]:
        status_file = workspace_root / "manifests" / "status.json"
        if status_file.exists():
            return json.loads(status_file.read_text(encoding="utf-8"))
        return {"current_stage": "unknown", "message": "No status", "progress": 0.0}
