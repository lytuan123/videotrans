from __future__ import annotations

import argparse
import json
from pathlib import Path

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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate":
        settings = load_settings(*args.config)
        print(settings.model_dump_json(indent=2))
        return 0

    overrides = {"pipeline": {}}
    if args.video_path:
        overrides["pipeline"]["video_path"] = args.video_path
    if args.target_language:
        overrides["pipeline"]["target_language"] = args.target_language
    if args.source_language:
        overrides["pipeline"]["source_language"] = args.source_language
    if not overrides["pipeline"]:
        overrides = None

    settings = load_settings(*args.config, overrides=overrides)
    orchestrator = VideoTransDubOrchestrator(settings)
    manifest = orchestrator.run()
    print(manifest.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
