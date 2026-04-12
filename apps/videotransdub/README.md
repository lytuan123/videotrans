# VideoTransDub

Hệ thống pipeline biên dịch/lồng tiếng video mới, tách biệt khỏi `pyvideotrans` cũ để tránh phụ thuộc GUI/Colab wrapper cũ.

## Mục tiêu

- Headless-first, checkpoint/resume được
- Config-driven, stage-based
- Tái sử dụng upstream `cli.py` theo từng stage khi phù hợp
- Giữ mã cũ nguyên trạng; toàn bộ hệ mới nằm trong `apps/videotransdub/`

## Những gì đã có trong bản này

- CLI mới: `python -m videotransdub.cli`
- Pipeline theo stage: preprocess → asr → translate → tts → sync → mix → video → finalize
- Checkpoint manager + workspace layout rõ ràng
- Adapter cho upstream `pyvideotrans` CLI (`stt` / `sts` / `tts`)
- Chế độ `mock` để test/smoke nội bộ không cần model nặng
- Notebook Colab mỏng để chạy hệ mới thay vì vá notebook cũ

## Những gì cố ý để cấu hình theo môi trường

- Hard subtitle removal production-grade cho mọi video
- Voice cloning production-grade
- Multi-speaker diarization phức tạp
- FastAPI runtime đầy đủ dependency trong sandbox hiện tại

## Cấu trúc

```text
apps/videotransdub/
├── configs/
├── notebooks/
├── src/videotransdub/
└── tests/
```

## Quick start

### 1. Smoke test cục bộ

```bash
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/mock.yaml \
  --video-path input/video.mp4
```

### 2. Chạy với upstream `pyvideotrans`

Chuẩn bị dependency của repo gốc, sau đó dùng preset `balanced.yaml` hoặc `fast_free.yaml`.

```bash
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/fast_free.yaml \
  --video-path /abs/path/video.mp4
```

## Lưu ý production

Bản này là **production-oriented foundation**: orchestration, checkpoint, artifact contract, preset config, test nội bộ đã sẵn. Chất lượng đầu ra thực tế còn phụ thuộc vào:

- GPU/runtime thực tế
- model/API key được cấu hình
- FFmpeg/Demucs/Whisper/TTS có mặt trong môi trường
- loại video đầu vào (đặc biệt hard-sub removal vẫn nên xem là experimental)
