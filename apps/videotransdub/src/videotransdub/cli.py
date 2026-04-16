from __future__ import annotations

import argparse
import json
import sys

from .diagnostics import build_pipeline_overrides, collect_preflight, run_smoke
from .orchestrator import VideoTransDubOrchestrator
from .settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VideoTransDub CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the pipeline")
    run.add_argument("--config", action="append", required=True, help="YAML config path; can be passed multiple times")
    run.add_argument("--video-path", help="Override input video path")
    run.add_argument("--target-language", help="Override target language")
    run.add_argument("--source-language", help="Override source language")

    validate = sub.add_parser("validate", help="Validate merged config")
    validate.add_argument("--config", action="append", required=True)

    preflight = sub.add_parser("preflight", help="Check whether the environment is ready for the selected config")
    preflight.add_argument("--config", action="append", required=True)
    preflight.add_argument("--video-path", help="Override input video path")
    preflight.add_argument("--target-language", help="Override target language")
    preflight.add_argument("--source-language", help="Override source language")
    preflight.add_argument("--check-ui", action="store_true", help="Also check Streamlit/cloudflared availability")

    smoke = sub.add_parser("smoke", help="Create a short clip and run a smoke test")
    smoke.add_argument("--config", action="append", required=True)
    smoke.add_argument("--video-path", required=True, help="Input video path")
    smoke.add_argument("--target-language", help="Override target language")
    smoke.add_argument("--source-language", help="Override source language")
    smoke.add_argument("--clip-seconds", type=int, default=15, help="How many seconds to keep in the smoke clip")
    smoke.add_argument("--work-root", help="Optional output root for smoke artifacts")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "validate":
            settings = load_settings(*args.config)
            print(settings.model_dump_json(indent=2))
            return 0

        overrides = build_pipeline_overrides(
            getattr(args, "video_path", None),
            getattr(args, "target_language", None),
            getattr(args, "source_language", None),
        )

        if args.command == "preflight":
            settings = load_settings(*args.config, overrides=overrides)
            report = collect_preflight(settings, check_ui=args.check_ui)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["ready"] else 1

        if args.command == "smoke":
            settings = load_settings(*args.config, overrides=overrides)
            report = run_smoke(settings, clip_seconds=args.clip_seconds, work_root=args.work_root)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        settings = load_settings(*args.config, overrides=overrides)
        orchestrator = VideoTransDubOrchestrator(settings)
        manifest = orchestrator.run()
        print(manifest.model_dump_json(indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
