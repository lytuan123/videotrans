from __future__ import annotations

from pathlib import Path

from ..registry import create_inpaint_engine
from ..utils.commands import run_command, which, write_json
from .base import BaseStage


class VideoStage(BaseStage):
    name = "stage5_video"

    def run(self, ctx):
        stage_dir = ctx.workspace.stage_dir("stage5")
        source_video = Path(ctx.artifacts["source_video"])
        cleaned_video = stage_dir / f"video_clean{source_video.suffix}"
        inpaint = create_inpaint_engine(ctx.settings)
        cleaned = inpaint.clean(source_video, cleaned_video)

        subtitle_input = Path(ctx.artifacts["transcript_translated_srt"])
        rendered_video = stage_dir / f"video_subbed.{ctx.settings.output.format}"
        manifest_path = stage_dir / "video_render.json"
        payload = {
            "cleaned_video": str(cleaned),
            "subtitle": str(subtitle_input),
            "burn_subtitle": ctx.settings.video_processing.burn_subtitle,
        }
        ffmpeg = which(ctx.settings.runtime.ffmpeg_bin)
        if ffmpeg and ctx.settings.runtime.mode == "execute" and ctx.settings.video_processing.burn_subtitle:
            style = ctx.settings.video_processing.subtitle_style
            filter_expr = (
                f"subtitles={subtitle_input}:force_style='FontName={style.font},FontSize={style.size},"
                f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline={style.outline}'"
            )
            run_command([
                ctx.settings.runtime.ffmpeg_bin,
                "-y",
                "-i", str(cleaned),
                "-vf", filter_expr,
                str(rendered_video),
            ], cwd=None, log_path=ctx.log_path)
            payload["render_mode"] = "ffmpeg-burn"
        else:
            rendered_video.write_text("render skipped; see manifest", encoding="utf-8")
            payload["render_mode"] = "manifest-only"
        write_json(manifest_path, payload)
        return {"video_clean": str(cleaned), "video_subbed": str(rendered_video), "video_render_manifest": str(manifest_path)}
