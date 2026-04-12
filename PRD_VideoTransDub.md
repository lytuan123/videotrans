# PRD: VideoTransDub — Pipeline Biên Dịch & Lồng Tiếng Video
## Production-Ready Tool cho Google Colab A100/H100

**Version:** 1.0  
**Ngày tạo:** 12/04/2026  
**Tham chiếu:** Cải tiến từ pyvideotrans (jianchang512), thiết kế lại cho môi trường headless Colab  

---

## 1. Tổng Quan Sản Phẩm

### 1.1 Vấn đề cần giải quyết

Hiện tại, **pyvideotrans** là công cụ mạnh nhất trong hệ sinh thái open-source cho việc dịch video, nhưng nó được thiết kế chủ yếu cho desktop Windows với GUI (PyQt). Việc triển khai trên Colab gặp nhiều trở ngại: phụ thuộc vào display server, cấu trúc code monolithic khó tách module, xung đột dependency giữa các model AI, và thiếu cơ chế quản lý VRAM hiệu quả cho GPU cloud.

### 1.2 Mục tiêu

Xây dựng một pipeline **headless, modular, cloud-native** có thể:

- Chạy hoàn toàn trên Google Colab (A100 40/80GB hoặc H100 80GB) mà không cần GUI
- Xử lý end-to-end: **Tách tiếng → Nhận dạng giọng nói → Dịch → Tổng hợp giọng nói → Xóa sub cũ → Ghi sub mới → Ghép video**
- Hỗ trợ cả model miễn phí (local inference) và model trả phí (API)
- Output là video hoàn chỉnh: **không còn sub gốc, không còn giọng gốc**, thay bằng sub + giọng đã dịch
- Thiết kế pipeline có thể dừng/tiếp tục ở từng bước (checkpoint)

### 1.3 Phạm vi

| Trong phạm vi | Ngoài phạm vi |
|---|---|
| Video có người nói (phỏng vấn, bài giảng, vlog, phim tài liệu) | Video nhạc/MV (đồng bộ môi) |
| Ngôn ngữ nguồn: EN, ZH, JA, KO, và hầu hết ngôn ngữ Whisper hỗ trợ | Lip-sync deepfake (Wav2Lip/MuseTalk) — để mở rộng sau |
| Ngôn ngữ đích: VI (ưu tiên), EN, ZH | Dịch real-time/streaming |
| Video ≤ 2 giờ, ≤ 4K resolution | Xử lý batch song song nhiều video cùng lúc |

---

## 2. Kiến Trúc Pipeline

### 2.1 Tổng quan luồng xử lý

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        INPUT VIDEO (MP4/MKV/AVI/MOV)                        │
└──────────────────────────┬───────────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  STAGE 0: TIỀN XỬ LÝ   │
              │  - Trích xuất audio     │
              │  - Trích xuất metadata  │
              │  - Tách vocal/BGM       │
              └────────────┬───────────┘
                           │
               ┌───────────┴───────────┐
               ▼                       ▼
    ┌──────────────────┐    ┌──────────────────┐
    │   Vocal Track    │    │    BGM Track      │
    │   (giọng nói)    │    │ (nhạc nền/SFX)   │
    └────────┬─────────┘    └────────┬─────────┘
             │                       │ (giữ nguyên)
             ▼                       │
  ┌────────────────────────┐         │
  │  STAGE 1: ASR           │         │
  │  Nhận dạng giọng nói    │         │
  │  → SRT gốc với timestamp│         │
  └────────────┬───────────┘         │
               │                     │
               ▼                     │
  ┌────────────────────────┐         │
  │  STAGE 2: DỊCH THUẬT    │         │
  │  SRT gốc → SRT đích     │         │
  │  (giữ nguyên timestamp) │         │
  └────────────┬───────────┘         │
               │                     │
               ▼                     │
  ┌────────────────────────┐         │
  │  STAGE 3: TTS           │         │
  │  SRT đích → Audio đích  │         │
  │  (voice cloning hoặc    │         │
  │   chọn giọng có sẵn)    │         │
  └────────────┬───────────┘         │
               │                     │
               ▼                     │
  ┌────────────────────────┐         │
  │  STAGE 3.5: ĐỒNG BỘ    │         │
  │  - Speed up/slow down   │         │
  │    audio cho khớp       │         │
  │    timestamp gốc        │         │
  │  - Chèn khoảng lặng     │         │
  └────────────┬───────────┘         │
               │                     │
               ▼                     ▼
  ┌──────────────────────────────────────┐
  │  STAGE 4: TRỘN AUDIO                 │
  │  Vocal đã dịch + BGM gốc → Audio mới│
  └────────────────────┬─────────────────┘
                       │
                       ▼
  ┌────────────────────────────┐
  │  STAGE 5: XỬ LÝ VIDEO      │
  │  5a. Xóa hardcoded sub cũ  │
  │      (AI inpainting)        │
  │  5b. Burn sub mới           │
  │      (hoặc softcode)        │
  └────────────────┬───────────┘
                   │
                   ▼
  ┌────────────────────────────┐
  │  STAGE 6: GHÉP FINAL        │
  │  Video đã xử lý + Audio mới│
  │  → OUTPUT VIDEO              │
  └──────────────────────────────┘
```

### 2.2 Checkpoint System

Mỗi stage lưu output vào thư mục `workspace/{video_id}/`:

```
workspace/
└── abc123/
    ├── config.json           # Cấu hình pipeline
    ├── input.mp4             # Video gốc
    ├── stage0/
    │   ├── vocal.wav         # Giọng nói tách riêng
    │   ├── bgm.wav           # Nhạc nền
    │   └── metadata.json     # FPS, resolution, codec...
    ├── stage1/
    │   ├── transcript_raw.srt
    │   └── transcript_raw.json  # Với word-level timestamps
    ├── stage2/
    │   ├── transcript_translated.srt
    │   └── transcript_translated.json
    ├── stage3/
    │   ├── dubbed_segments/   # Từng đoạn audio đã TTS
    │   └── dubbed_full.wav    # Audio đã dịch, đồng bộ
    ├── stage4/
    │   └── mixed_audio.wav    # Vocal dịch + BGM
    ├── stage5/
    │   ├── video_clean.mp4    # Video đã xóa sub cũ
    │   └── video_subbed.mp4   # Video + sub mới
    └── output/
        └── final.mp4          # Sản phẩm cuối
```

Pipeline tự động phát hiện checkpoint đã có và **bỏ qua stage đã hoàn thành**, cho phép resume khi Colab bị ngắt.

---

## 3. Chi Tiết Từng Stage

### 3.0 Stage 0: Tiền Xử Lý

**Mục đích:** Tách audio khỏi video, phân tách vocal và nhạc nền.

**Công cụ:**

| Công cụ | Loại | Ghi chú |
|---|---|---|
| **FFmpeg** | CLI | Trích xuất audio track, metadata |
| **Demucs v4 (htdemucs_ft)** | Free/Local | Model tách vocal/BGM tốt nhất, chạy tốt trên GPU. Dùng model `htdemucs_ft` cho chất lượng cao |
| **UVR5 (Ultimate Vocal Remover)** | Free/Local | Thay thế nếu Demucs gặp vấn đề |

**Lưu ý kỹ thuật:**
- Trích xuất audio ở 16kHz mono cho ASR, 44.1kHz stereo cho mixing
- Demucs `htdemucs_ft` cần ~4GB VRAM, inference nhanh trên A100
- Lưu cả 2 track: `vocals.wav` và `no_vocals.wav` (accompaniment)

---

### 3.1 Stage 1: ASR (Nhận Dạng Giọng Nói)

**Mục đích:** Chuyển audio thành text có timestamp chính xác đến từng từ.

**Bảng so sánh model:**

| Model | Loại | VRAM | Tốc độ | Chất lượng | Ngôn ngữ | Chi phí |
|---|---|---|---|---|---|---|
| **Faster-Whisper large-v3** | Free/Local | ~5GB | Nhanh (CTranslate2) | Rất tốt | 99 ngôn ngữ | $0 |
| **WhisperX** | Free/Local | ~5GB | Nhanh + word-level alignment | Tốt nhất cho timestamp | 99 ngôn ngữ | $0 |
| **OpenAI Whisper API** | Trả phí | 0 (cloud) | Nhanh | Tốt | 57 ngôn ngữ | $0.006/phút |
| **Qwen-ASR (Alibaba)** | Trả phí | 0 (cloud) | Nhanh | Tốt cho ZH | ZH, EN, JA, KO | ~¥0.008/giây |
| **Google Cloud STT v2** | Trả phí | 0 (cloud) | Nhanh | Tốt | 125 ngôn ngữ | $0.016/phút |
| **Azure Speech** | Trả phí | 0 (cloud) | Nhanh | Tốt | 100+ ngôn ngữ | $1/giờ audio |

**Khuyến nghị mặc định:** `WhisperX` (Faster-Whisper + forced alignment) — miễn phí, chạy tốt trên A100, cho word-level timestamps cần thiết cho TTS sync.

**Cấu hình WhisperX:**
```python
asr_config = {
    "model": "large-v3",          # hoặc "large-v3-turbo" cho tốc độ
    "device": "cuda",
    "compute_type": "float16",    # A100 hỗ trợ tốt
    "batch_size": 16,             # Tăng batch trên A100
    "language": None,             # Auto-detect hoặc chỉ định
    "vad_filter": True,           # Lọc khoảng im lặng
    "word_timestamps": True,      # Bắt buộc cho sync
    "chunk_length": 30,           # seconds
}
```

**Output format:**
```json
{
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.52,
      "text": "Hello everyone, welcome to this tutorial",
      "words": [
        {"word": "Hello", "start": 0.0, "end": 0.32},
        {"word": "everyone", "start": 0.35, "end": 0.82}
      ]
    }
  ]
}
```

---

### 3.2 Stage 2: Dịch Thuật

**Mục đích:** Dịch text từ ngôn ngữ nguồn sang ngôn ngữ đích, giữ nguyên cấu trúc segment và timestamp.

**Bảng so sánh:**

| Engine | Loại | Chất lượng | Chi phí | Ghi chú |
|---|---|---|---|---|
| **Gemini 2.5 Flash** | Trả phí | Rất tốt, hiểu ngữ cảnh | ~$0.15/1M token input | Giá cực rẻ, context window lớn, dịch cả batch |
| **DeepSeek V3/R1** | Trả phí | Tốt | ~$0.27/1M token input | Giỏi ZH↔VI, giá rẻ |
| **Claude Sonnet** | Trả phí | Rất tốt | $3/1M token input | Dịch tự nhiên, giữ ngữ cảnh tốt |
| **GPT-4o-mini** | Trả phí | Tốt | $0.15/1M token input | Nhanh, rẻ |
| **Meta NLLB-200 (3.3B)** | Free/Local | Khá | $0 | Offline, 200 ngôn ngữ, ~8GB VRAM |
| **Ollama (Qwen2.5/Gemma2)** | Free/Local | Khá | $0 | Chạy local, tùy chỉnh prompt |
| **Google Translate API** | Trả phí | Khá | $20/1M ký tự | Nhanh, ổn định |

**Khuyến nghị:** Dùng **Gemini 2.5 Flash** làm mặc định (chất lượng cao, rẻ, context dài cho phép gửi cả transcript 1 lần). Fallback: **NLLB-200** cho offline.

**Chiến lược dịch cho video:**

Không dịch từng câu riêng lẻ. Thay vào đó, gửi **cả block 20-30 segments** cùng lúc để LLM hiểu ngữ cảnh. Prompt template:

```
Bạn là dịch giả chuyên nghiệp. Dịch các đoạn subtitle sau từ {src_lang} sang {tgt_lang}.
Giữ nguyên ID và format. Dịch tự nhiên, phù hợp văn nói.
Cố gắng giữ độ dài tương đương bản gốc (rất quan trọng cho đồng bộ audio).

[0] Hello everyone, welcome to this tutorial
[1] Today we're going to learn about machine learning
...

Output format: Chỉ trả lời phần dịch, giữ nguyên [ID]:
[0] Xin chào mọi người, chào mừng đến với hướng dẫn này
[1] Hôm nay chúng ta sẽ tìm hiểu về học máy
```

**Constraint quan trọng:** Yêu cầu LLM giữ số ký tự/từ gần với bản gốc để giảm áp lực đồng bộ audio ở Stage 3.5.

---

### 3.3 Stage 3: TTS (Text-to-Speech / Lồng Tiếng)

**Mục đích:** Tạo audio tiếng Việt (hoặc ngôn ngữ đích) từ text đã dịch.

**Bảng so sánh model TTS — Cập nhật 2026:**

| Model | Loại | Voice Clone | Tiếng Việt | VRAM | Chất lượng | Chi phí |
|---|---|---|---|---|---|---|
| **IndexTTS-2** | Free/Local | ✅ Zero-shot | ❌ (EN, ZH) | ~6GB | Xuất sắc, kiểm soát duration | $0 |
| **F5-TTS** | Free/Local | ✅ Zero-shot | ✅ (hạn chế) | ~3GB | Rất tốt, nhẹ | $0 |
| **CosyVoice2-0.5B** | Free/Local | ✅ Zero-shot | ❌ (ZH, EN, JA, KO) | ~4GB | Rất tốt, streaming | $0 |
| **CosyVoice3** | Free/Local | ✅ Zero-shot | ⚠️ (thử nghiệm) | ~4GB | Tốt, nhiều ngôn ngữ hơn | $0 |
| **Fish Speech 1.5** | Free/Local | ✅ Zero-shot | ⚠️ (hạn chế) | ~6GB | Xuất sắc cho EN/ZH | $0 |
| **ChatterBox** | Free/Local | ✅ | ✅ Multilingual | ~4GB | Tốt | $0 |
| **Edge-TTS** | Free/API | ❌ (giọng có sẵn) | ✅ (vi-VN) | 0 | Khá | $0 (Free) |
| **OpenAI TTS** | Trả phí | ❌ | ✅ | 0 | Rất tốt | $15/1M ký tự |
| **ElevenLabs** | Trả phí | ✅ | ✅ | 0 | Xuất sắc | $0.18/1K ký tự |
| **Azure TTS** | Trả phí | ✅ (Custom Neural) | ✅ (vi-VN) | 0 | Rất tốt | Từ $15/1M ký tự |
| **Minimax TTS** | Trả phí | ✅ | ⚠️ | 0 | Tốt | ~¥0.1/1K ký tự |

**Khuyến nghị theo use case:**

1. **Giọng tiếng Việt tự nhiên, miễn phí:** `Edge-TTS` (giọng `vi-VN-HoaiMyNeural` hoặc `vi-VN-NamMinhNeural`) — không voice clone nhưng chất lượng đủ tốt cho production.

2. **Voice clone giọng gốc, miễn phí:** `F5-TTS` hoặc `ChatterBox Multilingual` — dùng vocal track gốc (10-30s) làm reference audio.

3. **Chất lượng cao nhất, chấp nhận trả phí:** `ElevenLabs` (voice clone + VI support) hoặc `OpenAI TTS` (giọng tự nhiên).

4. **Video EN/ZH, cần kiểm soát duration:** `IndexTTS-2` — có chế độ điều khiển chính xác thời lượng audio, lý tưởng cho đồng bộ lip-sync.

**Flow TTS:**
```
Foreach segment in translated_srt:
    1. Tạo audio segment bằng TTS engine được chọn
    2. Đo duration output vs duration gốc
    3. Nếu chênh lệch > ngưỡng → điều chỉnh (Stage 3.5)
    4. Lưu segment audio + metadata
```

---

### 3.4 Stage 3.5: Đồng Bộ Audio-Time

**Mục đích:** Đảm bảo audio TTS khớp với timeline gốc của video.

**Vấn đề thực tế:** Khi dịch từ EN → VI, văn bản tiếng Việt thường **dài hơn** bản gốc (nhiều âm tiết hơn), dẫn đến audio TTS dài hơn khoảng thời gian gốc. Ngược lại, ZH → VI thường ngắn hơn.

**Chiến lược xử lý:**

```python
sync_config = {
    # Tốc độ tối đa cho phép tăng/giảm (so với 1.0x)
    "max_speedup_ratio": 1.4,     # Tăng tốc tối đa 40%
    "max_slowdown_ratio": 0.8,    # Giảm tốc tối đa 20%
    
    # Nếu vượt giới hạn speed → cắt khoảng lặng hoặc split segment
    "silence_trim_threshold_db": -40,
    
    # Thuật toán time-stretch (không thay đổi pitch)
    "time_stretch_method": "rubberband",  # hoặc "pyrubberband", "soundtouch"
    
    # Nếu audio ngắn hơn → chèn silence padding
    "pad_short_segments": True,
}
```

**Thuật toán:**
1. So sánh `tts_duration` vs `original_duration` cho mỗi segment
2. Nếu `ratio = tts_duration / original_duration` nằm trong `[0.8, 1.4]` → dùng time-stretch (rubberband)
3. Nếu `ratio > 1.4` → trim silence trước, nếu vẫn quá → tua nhanh tối đa 1.4x + cho phép chồng nhẹ vào silence gap trước segment tiếp theo
4. Nếu `ratio < 0.8` → padding silence ở cuối segment

---

### 3.5 Stage 4: Trộn Audio

**Mục đích:** Ghép vocal đã dịch + BGM gốc thành 1 audio track hoàn chỉnh.

**Công cụ:** `pydub` hoặc `FFmpeg`

**Tham số mixing:**
```python
mix_config = {
    "vocal_volume_db": 0,        # Giữ nguyên volume vocal dịch
    "bgm_volume_db": -3,         # Giảm BGM 3dB so với gốc (optional)
    "crossfade_ms": 50,          # Fade nhẹ giữa các segment
    "normalize": True,           # Normalize loudness cuối cùng
    "target_lufs": -16,          # Broadcast standard
}
```

---

### 3.6 Stage 5: Xử Lý Video

#### 5a. Xóa Hardcoded Subtitle Cũ

**Đây là stage phức tạp nhất.** Có 2 trường hợp:

**Trường hợp 1: Video có soft subtitle (SRT/ASS embedded)**
→ Đơn giản: FFmpeg extract video stream, bỏ qua subtitle track.

**Trường hợp 2: Video có hardcoded subtitle (burn-in)**
→ Cần AI inpainting. Đây là bài toán video inpainting.

**Bảng so sánh giải pháp xóa hard sub:**

| Công cụ | Loại | VRAM | Chất lượng | Tốc độ | Ghi chú |
|---|---|---|---|---|---|
| **video-subtitle-remover (STTN)** | Free/Local | ~4GB | Tốt cho live-action | Nhanh | Có thể skip detection |
| **video-subtitle-remover (LaMa)** | Free/Local | ~3GB | Tốt cho anime/tĩnh | Trung bình | Frame-by-frame |
| **video-subtitle-remover (ProPainter)** | Free/Local | ~8-12GB | Tốt nhất cho chuyển động mạnh | Chậm | VRAM cao |
| **Tự xây: OCR detect + LaMa/STTN** | Free/Local | ~4-6GB | Tùy chỉnh | Tùy chỉnh | Linh hoạt nhất |
| **IOPaint (lama-cleaner)** | Free/Local | ~3GB | Tốt | Trung bình | API-based, dễ tích hợp |

**Khuyến nghị:** Dùng `video-subtitle-remover` với mode STTN cho live-action, LaMa cho animation. Trên A100 80GB, có thể dùng ProPainter cho chất lượng tối ưu.

**Pipeline xóa sub:**
```
1. Xác định vùng subtitle (bottom 15-25% frame, hoặc OCR detect)
2. Tạo binary mask cho mỗi frame có text
3. Chạy inpainting model (STTN/LaMa/ProPainter)
4. Re-encode video với original codec settings
```

**Lưu ý quan trọng:**
- Nếu video gốc **không có hardcoded sub**, bỏ qua stage 5a hoàn toàn
- Cung cấp option cho user chỉ định vùng sub (y_min, y_max) để tăng accuracy
- A100 có đủ VRAM để chạy ProPainter cho video 1080p

#### 5b. Burn Subtitle Mới

**Công cụ:** FFmpeg với filter `subtitles` hoặc `ass`

**2 chế độ output:**

1. **Hardcode (burn-in):** Subtitle được render trực tiếp vào frame → không tắt được, nhưng đảm bảo hiển thị trên mọi player
2. **Softcode:** Subtitle được embed dưới dạng track riêng → có thể bật/tắt

```bash
# Hardcode subtitle
ffmpeg -i video_clean.mp4 -vf "subtitles=translated.srt:force_style='FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'" output.mp4

# Softcode subtitle  
ffmpeg -i video_clean.mp4 -i translated.srt -c copy -c:s mov_text output.mp4
```

**Style mặc định cho sub tiếng Việt:**
```
FontName=Be Vietnam Pro  (hoặc Arial)
FontSize=22
PrimaryColour=White
OutlineColour=Black  
Outline=2
Shadow=1
Alignment=2 (bottom center)
MarginV=30
```

---

### 3.7 Stage 6: Ghép Final

```bash
ffmpeg -i video_subbed.mp4 -i mixed_audio.wav \
    -c:v copy -c:a aac -b:a 192k \
    -map 0:v:0 -map 1:a:0 \
    -shortest \
    output_final.mp4
```

---

## 4. Cấu Hình & API Keys

### 4.1 File cấu hình `config.yaml`

```yaml
# === PIPELINE CONFIG ===
pipeline:
  video_path: "/content/input.mp4"
  output_dir: "/content/output"
  workspace_dir: "/content/workspace"
  source_language: "auto"        # auto-detect hoặc: en, zh, ja, ko...
  target_language: "vi"
  resume: true                   # Tự động resume từ checkpoint

# === STAGE 0: Vocal Separation ===
vocal_separation:
  engine: "demucs"               # demucs | uvr5
  model: "htdemucs_ft"
  device: "cuda"

# === STAGE 1: ASR ===
asr:
  engine: "whisperx"             # whisperx | faster-whisper | openai-api | azure
  model: "large-v3"
  compute_type: "float16"
  batch_size: 16
  vad_filter: true
  word_timestamps: true
  # Cho API engines:
  # api_key: "${OPENAI_API_KEY}"

# === STAGE 2: Translation ===
translation:
  engine: "gemini"               # gemini | deepseek | claude | gpt4o | nllb | ollama | google
  model: "gemini-2.5-flash"
  api_key: "${GEMINI_API_KEY}"
  batch_size: 25                 # Số segments gửi 1 lần
  keep_length: true              # Yêu cầu giữ độ dài tương đương
  glossary: {}                   # Từ điển thuật ngữ chuyên ngành
  # Cho NLLB local:
  # model: "facebook/nllb-200-3.3B"
  # device: "cuda"

# === STAGE 3: TTS ===
tts:
  engine: "edge-tts"             # edge-tts | f5-tts | cosyvoice2 | indextts2 | openai | elevenlabs | azure
  voice: "vi-VN-HoaiMyNeural"   # Cho Edge-TTS
  # voice_clone:
  #   enabled: true
  #   reference_audio: "auto"    # "auto" = dùng vocal track gốc
  #   reference_duration: 15     # Seconds

# === STAGE 3.5: Audio Sync ===
audio_sync:
  max_speedup: 1.4
  max_slowdown: 0.8
  method: "rubberband"
  silence_trim: true

# === STAGE 4: Audio Mix ===
audio_mix:
  bgm_volume_adjust_db: -3
  normalize: true
  target_lufs: -16

# === STAGE 5: Video Processing ===
video_processing:
  remove_hardcoded_sub: false    # true nếu video có hardsub
  sub_region:                    # Vùng subtitle (% of frame height)
    y_start: 0.80
    y_end: 1.00
  inpaint_mode: "sttn"           # sttn | lama | propainter
  burn_subtitle: true            # true = hardcode, false = softcode
  subtitle_style:
    font: "Arial"
    size: 22
    color: "white"
    outline: 2

# === STAGE 6: Final Output ===
output:
  format: "mp4"
  video_codec: "copy"            # copy | h264 | h265
  audio_codec: "aac"
  audio_bitrate: "192k"
```

### 4.2 Biến môi trường (Colab Secrets)

```python
import os
# Trong Colab, dùng userdata secrets:
from google.colab import userdata

os.environ["GEMINI_API_KEY"] = userdata.get("GEMINI_API_KEY")
os.environ["OPENAI_API_KEY"] = userdata.get("OPENAI_API_KEY")      # Optional
os.environ["ELEVENLABS_API_KEY"] = userdata.get("ELEVENLABS_API_KEY")  # Optional
os.environ["DEEPSEEK_API_KEY"] = userdata.get("DEEPSEEK_API_KEY")  # Optional
```

---

## 5. Thiết Kế Module & Cấu Trúc Code

### 5.1 Cấu trúc thư mục

```
videotransdub/
├── README.md
├── setup.py
├── requirements/
│   ├── base.txt               # Core dependencies
│   ├── asr.txt                # WhisperX, faster-whisper
│   ├── tts-local.txt          # F5-TTS, CosyVoice, IndexTTS
│   ├── inpaint.txt            # video-subtitle-remover deps
│   └── colab.txt              # Colab-specific overrides
├── configs/
│   ├── default.yaml
│   └── presets/
│       ├── fast_free.yaml     # All-free, tốc độ ưu tiên
│       ├── quality_paid.yaml  # Trả phí, chất lượng ưu tiên
│       └── balanced.yaml      # Cân bằng
├── videotransdub/
│   ├── __init__.py
│   ├── pipeline.py            # Orchestrator chính
│   ├── config.py              # Config loader + validator
│   ├── checkpoint.py          # Checkpoint manager
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── stage0_preprocess.py
│   │   ├── stage1_asr.py
│   │   ├── stage2_translate.py
│   │   ├── stage3_tts.py
│   │   ├── stage3_5_sync.py
│   │   ├── stage4_mix.py
│   │   ├── stage5_video.py
│   │   └── stage6_final.py
│   ├── engines/
│   │   ├── asr/
│   │   │   ├── base.py        # Abstract ASR engine
│   │   │   ├── whisperx_engine.py
│   │   │   ├── faster_whisper_engine.py
│   │   │   └── openai_asr_engine.py
│   │   ├── translate/
│   │   │   ├── base.py
│   │   │   ├── gemini_engine.py
│   │   │   ├── deepseek_engine.py
│   │   │   ├── nllb_engine.py
│   │   │   └── ollama_engine.py
│   │   ├── tts/
│   │   │   ├── base.py
│   │   │   ├── edge_tts_engine.py
│   │   │   ├── f5_tts_engine.py
│   │   │   ├── cosyvoice_engine.py
│   │   │   ├── indextts_engine.py
│   │   │   ├── openai_tts_engine.py
│   │   │   └── elevenlabs_engine.py
│   │   └── inpaint/
│   │       ├── base.py
│   │       ├── sttn_engine.py
│   │       ├── lama_engine.py
│   │       └── propainter_engine.py
│   └── utils/
│       ├── audio.py           # Audio processing helpers
│       ├── video.py           # Video processing helpers
│       ├── srt.py             # SRT parsing/generation
│       ├── gpu.py             # VRAM monitoring
│       └── logger.py          # Structured logging
├── notebooks/
│   ├── VideoTransDub_Colab.ipynb    # Notebook chính
│   └── VideoTransDub_Quick.ipynb    # Quick start
└── tests/
    ├── test_pipeline.py
    └── test_engines/
```

### 5.2 Abstract Engine Interface

```python
# videotransdub/engines/tts/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class TTSSegment:
    text: str
    start: float          # Original timestamp
    end: float
    audio: Optional[np.ndarray] = None
    sample_rate: int = 24000
    duration: float = 0.0

class BaseTTSEngine(ABC):
    """Abstract base class cho mọi TTS engine."""
    
    @abstractmethod
    def initialize(self, config: dict) -> None:
        """Load model/setup API connection."""
        pass
    
    @abstractmethod
    def synthesize(self, text: str, **kwargs) -> tuple[np.ndarray, int]:
        """Tạo audio từ text. Returns (audio_array, sample_rate)."""
        pass
    
    @abstractmethod
    def synthesize_batch(self, segments: list[TTSSegment]) -> list[TTSSegment]:
        """Tạo audio cho nhiều segments."""
        pass
    
    def cleanup(self) -> None:
        """Giải phóng GPU memory."""
        pass
    
    @property
    @abstractmethod
    def supports_voice_clone(self) -> bool:
        pass
    
    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        pass
```

### 5.3 Pipeline Orchestrator

```python
# videotransdub/pipeline.py
class VideoTransDubPipeline:
    """Orchestrator chính điều phối toàn bộ pipeline."""
    
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.checkpoint = CheckpointManager(self.config.workspace_dir)
        self.stages = self._init_stages()
    
    def run(self, video_path: str = None):
        """Chạy toàn bộ pipeline với checkpoint support."""
        if video_path:
            self.config.video_path = video_path
        
        video_id = self._get_video_id()
        
        for stage in self.stages:
            stage_name = stage.name
            
            if self.checkpoint.is_completed(video_id, stage_name):
                logger.info(f"⏭️ Bỏ qua {stage_name} (đã hoàn thành)")
                continue
            
            logger.info(f"▶️ Bắt đầu {stage_name}...")
            try:
                stage.execute(video_id)
                self.checkpoint.mark_completed(video_id, stage_name)
                
                # Giải phóng GPU memory giữa các stage
                stage.cleanup()
                torch.cuda.empty_cache()
                
                logger.info(f"✅ Hoàn thành {stage_name}")
            except Exception as e:
                logger.error(f"❌ Lỗi tại {stage_name}: {e}")
                raise
        
        return self.checkpoint.get_output_path(video_id)
```

---

## 6. Tối Ưu Cho Colab A100/H100

### 6.1 Quản lý VRAM

```python
# GPU Memory Budget trên A100 80GB:
# Stage 0 (Demucs):     ~4GB  → còn 76GB
# Stage 1 (WhisperX):   ~5GB  → còn 75GB
# Stage 3 (F5-TTS):     ~3GB  → còn 77GB
# Stage 5 (ProPainter): ~12GB → còn 68GB
# 
# Lưu ý: Các stage chạy TUẦN TỰ, không đồng thời
# → Chỉ cần max(VRAM của từng stage) ≈ 12GB
# → A100 40GB cũng dư sức chạy

class GPUMemoryManager:
    @staticmethod
    def clear():
        import gc
        gc.collect()
        torch.cuda.empty_cache()
        if torch.cuda.is_available():
            torch.cuda.synchronize()
    
    @staticmethod
    def get_free_memory():
        return torch.cuda.mem_get_info()[0] / 1024**3  # GB
    
    @staticmethod
    def log_usage(stage_name: str):
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        logger.info(f"[{stage_name}] VRAM: {allocated:.1f}GB allocated, {reserved:.1f}GB reserved")
```

### 6.2 Colab Notebook Entry Point

```python
# Cell 1: Setup
!pip install videotransdub[colab]

# Cell 2: Config
from videotransdub import VideoTransDubPipeline

config = {
    "video_path": "/content/drive/MyDrive/videos/input.mp4",
    "target_language": "vi",
    "asr_engine": "whisperx",
    "translate_engine": "gemini",
    "tts_engine": "edge-tts",
    "tts_voice": "vi-VN-HoaiMyNeural",
    "remove_hardcoded_sub": False,
    "output_dir": "/content/drive/MyDrive/videos/output",
}

# Cell 3: Run
pipeline = VideoTransDubPipeline(config)
output_path = pipeline.run()

print(f"✅ Video đã dịch: {output_path}")
```

### 6.3 Xử lý Colab Timeout

```python
# Auto-save checkpoint mỗi segment
# Pipeline có thể resume bất kỳ lúc nào
# Mount Google Drive để persist workspace:

from google.colab import drive
drive.mount('/content/drive')

# Workspace trên Drive để không mất khi runtime reset:
config["workspace_dir"] = "/content/drive/MyDrive/videotransdub_workspace"
```

---

## 7. Preset Cấu Hình

### 7.1 Preset "Fast & Free" (Không tốn xu nào)

```yaml
asr: { engine: "faster-whisper", model: "large-v3-turbo" }
translation: { engine: "nllb", model: "facebook/nllb-200-3.3B" }
tts: { engine: "edge-tts", voice: "vi-VN-HoaiMyNeural" }
video_processing: { inpaint_mode: "sttn" }
# Ước tính: Video 10 phút → ~5-8 phút xử lý trên A100
```

### 7.2 Preset "Balanced" (Chi phí thấp, chất lượng tốt)

```yaml
asr: { engine: "whisperx", model: "large-v3" }
translation: { engine: "gemini", model: "gemini-2.5-flash" }
tts: { engine: "edge-tts", voice: "vi-VN-HoaiMyNeural" }
video_processing: { inpaint_mode: "sttn" }
# Chi phí ước tính: ~$0.01-0.05 cho video 10 phút (chỉ dịch)
```

### 7.3 Preset "Quality Max" (Chất lượng tối đa)

```yaml
asr: { engine: "whisperx", model: "large-v3" }
translation: { engine: "claude", model: "claude-sonnet-4-20250514" }
tts: { engine: "elevenlabs", voice_clone: true }
video_processing: { inpaint_mode: "propainter" }
# Chi phí ước tính: ~$0.50-2.00 cho video 10 phút
```

### 7.4 Preset "Voice Clone Free" (Clone giọng, không trả phí)

```yaml
asr: { engine: "whisperx", model: "large-v3" }
translation: { engine: "gemini", model: "gemini-2.5-flash" }
tts: { engine: "f5-tts", voice_clone: { enabled: true, reference_audio: "auto" } }
video_processing: { inpaint_mode: "sttn" }
# F5-TTS dùng vocal track gốc làm reference
```

---

## 8. Yêu Cầu Kỹ Thuật

### 8.1 Dependencies chính

```
# Core
torch>=2.1.0
torchaudio>=2.1.0
ffmpeg-python
pydub
pysrt
pyyaml
tqdm

# ASR
whisperx (hoặc faster-whisper)
ctranslate2

# Vocal Separation
demucs

# Translation (local)
transformers
sentencepiece  # cho NLLB

# TTS
edge-tts           # Free, async
f5-tts             # Local voice clone
# cosyvoice2       # Optional
# indextts2        # Optional

# Video Inpainting
opencv-python
onnxruntime-gpu    # cho STTN/LaMa

# Audio Processing
pyrubberband
soundfile
librosa
pyloudnorm
```

### 8.2 Yêu cầu phần cứng tối thiểu

| Thành phần | Tối thiểu | Khuyến nghị |
|---|---|---|
| GPU | T4 16GB | A100 40GB / H100 80GB |
| RAM | 12GB | 32GB+ |
| Disk | 20GB free | 50GB+ (cho model cache) |
| CUDA | 11.8+ | 12.1+ |

---

## 9. Lộ Trình Phát Triển

### Phase 1 — MVP (2-3 tuần)

- [ ] Core pipeline orchestrator + checkpoint system
- [ ] Stage 0: FFmpeg + Demucs integration
- [ ] Stage 1: WhisperX integration
- [ ] Stage 2: Gemini Flash translation
- [ ] Stage 3: Edge-TTS integration
- [ ] Stage 3.5: Basic audio sync (time-stretch)
- [ ] Stage 4: Audio mixing
- [ ] Stage 5b: FFmpeg subtitle burn
- [ ] Stage 6: Final merge
- [ ] Colab notebook v1

### Phase 2 — Enhancement (2-3 tuần)

- [ ] Stage 5a: Hard subtitle removal (STTN)
- [ ] Thêm TTS engines: F5-TTS, OpenAI TTS
- [ ] Thêm translate engines: DeepSeek, NLLB
- [ ] Gradio UI cho Colab
- [ ] Google Drive integration
- [ ] Preset configs

### Phase 3 — Production (2-3 tuần)

- [ ] Voice cloning pipeline (F5-TTS / CosyVoice)
- [ ] Multi-speaker detection + diarization
- [ ] Batch processing (queue system)
- [ ] ProPainter inpainting
- [ ] Quality metrics (PESQ, MOS estimation)
- [ ] Docker image cho self-hosted

### Phase 4 — Advanced (Future)

- [ ] Lip-sync với Wav2Lip/MuseTalk
- [ ] Streaming/real-time mode
- [ ] Web UI (Streamlit/Gradio standalone)
- [ ] API server mode
- [ ] Hỗ trợ SRT/ASS input (skip ASR)

---

## 10. So Sánh Với pyvideotrans

| Tiêu chí | pyvideotrans | VideoTransDub (PRD này) |
|---|---|---|
| Giao diện | PyQt GUI (desktop) | Headless CLI + Notebook + Gradio |
| Môi trường | Windows desktop | Colab / Linux server / Docker |
| Checkpoint | Không | Có (resume khi Colab restart) |
| VRAM management | Cơ bản | Tự động clear giữa stages |
| Hard sub removal | Không tích hợp | STTN / LaMa / ProPainter |
| Voice cloning | F5-TTS, CosyVoice, GPT-SoVITS | F5-TTS, CosyVoice, IndexTTS2, ChatterBox |
| Config | GUI settings | YAML file + presets |
| Mở rộng engine | Sửa code trực tiếp | Plugin architecture (Abstract base class) |
| CI/CD | Không | Unit tests + Colab test notebook |

---

## 11. Rủi Ro & Giải Pháp

| Rủi ro | Mức độ | Giải pháp |
|---|---|---|
| Colab disconnect giữa chừng | Cao | Checkpoint system + Google Drive workspace |
| VRAM OOM trên T4 | Trung bình | Auto-detect GPU → điều chỉnh batch size, model size |
| TTS quality cho tiếng Việt chưa tốt | Trung bình | Fallback chain: F5-TTS → Edge-TTS → OpenAI TTS |
| Hard sub removal artifact | Trung bình | Cho user chọn skip nếu không cần, hoặc dùng ProPainter |
| Audio sync bị lệch | Trung bình | Thuật toán multi-pass: trim silence → stretch → split |
| API rate limit (Gemini/OpenAI) | Thấp | Retry with backoff + fallback engine |
| Dependency conflict | Trung bình | Requirements files tách riêng, lazy import |

---

## 12. Metrics Đo Lường Thành Công

- **Thời gian xử lý:** Video 10 phút → xử lý trong < 10 phút trên A100 (real-time hoặc nhanh hơn)
- **Tỉ lệ thành công:** > 95% video chạy end-to-end không lỗi
- **Chất lượng dịch:** BLEU score > 0.3 (so với human translation)
- **Chất lượng audio:** MOS > 3.5/5.0 (đánh giá chủ quan)
- **Đồng bộ audio-video:** Lệch < 500ms cho mỗi segment
- **Resume success rate:** > 99% khi Colab restart

---

*Tài liệu này được thiết kế để làm foundation cho việc phát triển. Mỗi section có thể được mở rộng thành spec chi tiết riêng khi bắt đầu implement.*
