# VideoTransDub v0.2 - Huong dan su dung chi tiet

> Pipeline dich va long tieng video cap Production, ho tro Streamlit UI, checkpoint/resume,
> va nhieu engine thuc (Whisper, Edge-TTS, Qwen-MT, OpenCV inpainting).

---

## Muc luc

1. [Tong quan kien truc](#1-tong-quan-kien-truc)
2. [Cai dat tren Local](#2-cai-dat-tren-local)
3. [Cai dat tren Google Colab](#3-cai-dat-tren-google-colab)
4. [Su dung qua CLI (dong lenh)](#4-su-dung-qua-cli-dong-lenh)
5. [Su dung qua Streamlit UI](#5-su-dung-qua-streamlit-ui)
6. [Cau hinh Preset chi tiet](#6-cau-hinh-preset-chi-tiet)
7. [Tuy chinh nang cao](#7-tuy-chinh-nang-cao)
8. [Quy trinh lam viec voi SRT Editor](#8-quy-trinh-lam-viec-voi-srt-editor)
9. [Google Drive Integration](#9-google-drive-integration)
10. [Xu ly loi thuong gap](#10-xu-ly-loi-thuong-gap)
11. [Cau truc thu muc du an](#11-cau-truc-thu-muc-du-an)

---

## 1. Tong quan kien truc

### Pipeline 8 giai doan

```
Video dau vao
    |
    v
[Stage 0] Preprocess    -- Kiem tra video, lay metadata (ffprobe)
    |
    v
[Stage 1] ASR (STT)     -- Chuyen giong noi thanh van ban (Whisper / Qwen-ASR)
    |
    v
[Stage 2] Translation   -- Dich phu de (Google Free / Qwen-MT / Gemini)
    |
    v
    *** TAM DUNG de sua SRT (tuy chon) ***
    |
    v
[Stage 3] TTS           -- Tong hop giong noi tu ban dich (Edge-TTS / Qwen-TTS)
    |
    v
[Stage 3.5] Audio Sync  -- Dong bo thoi gian audio voi video goc
    |
    v
[Stage 4] Audio Mix     -- Tron am thanh (dubbing + nhac nen)
    |
    v
[Stage 5] Video Render  -- Ghi phu de len video + inpainting (tuy chon)
    |
    v
[Stage 6] Finalize      -- Ghep video + audio thanh file cuoi cung
    |
    v
Video dau ra (MP4)
```

### Cac engine co san

| Thanh phan | Engine | Mien phi? | Can API key? |
|-----------|--------|-----------|-------------|
| ASR | `faster-whisper` (tiny/small/large-v3) | Co | Khong |
| ASR | `pyvideotrans-stt` (upstream CLI) | Tuy model | Tuy model |
| Translation | `qwen-mt` (Qwen-MT-Turbo) | Co (free tier) | Co (DashScope) |
| Translation | `pyvideotrans-sts` (Google Free) | Co | Khong |
| Translation | `pyvideotrans-sts` (Gemini/GPT) | Khong | Co |
| TTS | `edge-tts` (Microsoft Edge) | Co | Khong |
| TTS | `pyvideotrans-tts` (upstream CLI) | Tuy engine | Tuy engine |
| Inpainting | `opencv` (OpenCV morphology) | Co | Khong |
| Inpainting | `passthrough` (khong xu ly) | -- | -- |

---

## 2. Cai dat tren Local

### 2.1. Yeu cau he thong

- **Python**: >= 3.10
- **FFmpeg + FFprobe**: bat buoc
- **GPU (tuy chon)**: NVIDIA GPU voi CUDA de ASR nhanh hon
- **OS**: Linux, macOS, hoac Windows (WSL khuyen dung)

### 2.2. Cai dat FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Windows:**
- Tai tu https://ffmpeg.org/download.html
- Them vao PATH he thong

Kiem tra:
```bash
ffmpeg -version
ffprobe -version
```

### 2.3. Cai dat Python dependencies

```bash
# Di chuyen vao thu muc du an
cd pyvideotrans-main

# Cai dat package co ban
pip install -e apps/videotransdub

# Cai dat DAY DU tat ca engine (khuyen dung)
pip install -e "apps/videotransdub[full]"

# Hoac cai tung phan:
pip install -e "apps/videotransdub[asr]"      # faster-whisper
pip install -e "apps/videotransdub[tts]"      # edge-tts
pip install -e "apps/videotransdub[inpaint]"  # opencv
pip install -e "apps/videotransdub[ui]"       # streamlit
pip install -e "apps/videotransdub[qwen]"     # dashscope (Alibaba)
```

### 2.4. Cai dat nhanh bang script (1 lenh)

```bash
# Tu thu muc goc du an
bash apps/videotransdub/install_deps.sh
```

Script nay se tu dong:
- Cai ffmpeg qua apt-get
- Cai tat ca Python packages
- Cai cloudflared (cho tunnel)
- Tao thu muc runtime
- Kiem tra GPU

### 2.5. Kiem tra cai dat

```bash
# Kiem tra config load duoc
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli validate \
  --config apps/videotransdub/configs/default.yaml
```

Neu in ra JSON settings ma khong bao loi -> cai dat thanh cong.

---

## 3. Cai dat tren Google Colab

### 3.1. File Notebook o dau?

File notebook nam tai:
```
apps/videotransdub/notebooks/videotransdub_colab.ipynb
```

Khi ban push repo len GitHub, file nay cung duoc push theo.

### 3.2. Cach mo Notebook tren Colab

**Cach 1: Mo truc tiep tu GitHub (nhanh nhat)**
1. Vao https://colab.research.google.com
2. Chon tab **GitHub**
3. Dan URL repo cua ban, tim file `apps/videotransdub/notebooks/videotransdub_colab.ipynb`
4. Click mo

**Cach 2: Upload thu cong**
1. Vao https://colab.research.google.com
2. Chon **Upload** -> chon file `videotransdub_colab.ipynb` tu may tinh

**Cach 3: Tu Google Drive**
1. Copy file `.ipynb` vao Google Drive
2. Click chuot phai -> **Open with** -> **Google Colaboratory**

### 3.3. Chay Notebook (3 buoc)

**Buoc 1**: Chon GPU
- Menu **Runtime** -> **Change runtime type** -> chon **T4 GPU** -> Save

**Buoc 2**: Sua URL repo (chi lan dau)
- Mo Cell 1, sua dong `GITHUB_REPO = "..."` thanh URL repo GitHub cua ban

**Buoc 3**: Chay tat ca
- Menu **Runtime** -> **Run all** (hoac nhan Ctrl+F9)
- Doi 3-5 phut de cai dat
- Khi Cell 4 chay xong, se hien **1 nut mau xanh co URL**
- **Click vao URL do** = mo giao dien web VideoTransDub

### 3.4. Dien gi xay ra khi chay Run All?

```
Cell 1: Mount Google Drive + clone repo tu GitHub cua ban
         |
Cell 2: Cai dat ffmpeg, Whisper, Edge-TTS, Streamlit, tunnel...  (3-5 phut)
         |
Cell 3: Hien thi thong tin GPU/RAM/Disk
         |
Cell 4: Khoi dong Streamlit server + tao Cloudflare tunnel
         |
         +---> HIEN THI URL: https://xxx.trycloudflare.com
                  |
                  v
         BAN CLICK VAO URL DO
                  |
                  v
         MO GIAO DIEN WEB (Dark Mode Dashboard)
         - Upload video
         - Chon ngon ngu dich
         - Nhan "Start Pipeline"
         - Xem tien do tung buoc
         - Chinh sua phu de (SRT Editor)
         - Xem truoc + tai video ket qua
```

### 3.5. `pip install videotransdub[colab]` co duoc khong?

**Khong** -- vi package nay chua duoc dang len PyPI. No chi cai duoc tu source code:

```python
# Cai tu source (sau khi da clone repo)
!pip install -e apps/videotransdub[colab]
```

Notebook da lam buoc nay tu dong trong Cell 2. Ban khong can chay thu cong.

### 3.6. Luu y quan trong cho Colab

- **Luon chon T4 GPU** (mien phi) de Whisper chay nhanh
- **URL thay doi moi session** -- nhung video dang xu ly luu tren Google Drive, khong bi mat
- Colab mien phi **timeout sau 90 phut** -- dung checkpoint/resume de tiep tuc
- Neu mat ket noi: **chay lai Cell 4** de lay URL moi, pipeline tu dong tiep tuc
- **Khong can copy code thu cong** -- notebook da chua san tat ca

---

## 4. Su dung qua CLI (dong lenh)

### 4.1. Lenh co ban

```bash
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/<PRESET>.yaml \
  --video-path /duong/dan/video.mp4 \
  --target-language vi \
  --source-language auto
```

### 4.2. Vi du cu the

**Dich video tieng Anh sang tieng Viet (mien phi, khong can API key):**
```bash
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/real_free.yaml \
  --video-path ~/Downloads/english_video.mp4 \
  --target-language vi
```

**Dich nhanh (hy sinh chat luong, lay toc do):**
```bash
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/fast_free.yaml \
  --video-path ~/Downloads/video.mp4 \
  --target-language vi
```

**Dich bang Qwen-MT (Alibaba free tier):**
```bash
export QWEN_API_KEY="sk-abd0a732837b414696fc23a8f933aa3b"

PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/qwen_free.yaml \
  --video-path ~/Downloads/video.mp4 \
  --target-language vi
```

**Smoke test (khong can GPU, khong can model):**
```bash
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/mock.yaml \
  --video-path ~/Downloads/video.mp4
```

### 4.3. Kiem tra config truoc khi chay

```bash
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli validate \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/real_free.yaml
```

Se in ra JSON cua toan bo settings da merge. Kiem tra cac truong quan trong:
- `asr.engine`, `asr.model`
- `translation.engine`, `translation.model`
- `tts.engine`, `tts.voice_role`

### 4.4. Resume pipeline bi gian doan

Pipeline tu dong luu checkpoint sau moi stage. Neu bi gian doan, chi can chay lai **cung lenh**, he thong se tu dong bo qua cac stage da hoan thanh:

```bash
# Chay lai cung lenh -- stages da xong se duoc skip
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/real_free.yaml \
  --video-path ~/Downloads/video.mp4 \
  --target-language vi
```

Log se hien:
```
skip stage0_preprocess (checkpoint)
skip stage1_asr (checkpoint)
run stage2_translate
...
```

### 4.5. Output

Sau khi pipeline hoan thanh, output nam tai:

```
apps/videotransdub/runtime/workspace/<job-id>/
  output/
    final.mp4              <-- Video da dich + long tieng
    final_manifest.json    <-- Metadata output
  stage1/
    transcript_raw.srt     <-- Phu de goc
  stage2/
    transcript_translated.srt  <-- Phu de da dich
  logs/
    pipeline.log           <-- Log chi tiet
```

---

## 5. Su dung qua Streamlit UI

### Streamlit UI la gi?

La giao dien web chay tren trinh duyet. Ban upload video, chon cau hinh, nhan nut --
moi thu deu thao tac bang chuot, khong can go lenh.

Giao dien nay **khong tu co san** khi ban `pip install`. Ban can **khoi dong server** truoc,
roi mo URL tren trinh duyet.

### 5.1. Khoi dong tren Local

```bash
cd pyvideotrans-main

# Cai dat (neu chua)
pip install -e "apps/videotransdub[full]"

# Khoi dong server
streamlit run apps/videotransdub/src/videotransdub/app.py \
  --server.port 8501 \
  --theme.base dark
```

Terminal se in ra:
```
  Local URL: http://localhost:8501
```

**Mo trinh duyet, vao http://localhost:8501** -- do la giao dien.

### 5.2. Khoi dong tren Colab

**Ban KHONG can lam buoc nay thu cong.** Notebook Cell 4 da tu dong:
1. Khoi dong Streamlit server
2. Tao Cloudflare tunnel
3. Hien thi URL dang `https://xxxx.trycloudflare.com`

**Chi can click vao URL do** = mo giao dien tren trinh duyet (ke ca tren dien thoai).

### 5.3. Giao dien UI gom 3 tab

#### Tab 1: Pipeline

- **Sidebar (ben trai):**
  - Upload video (keo tha hoac chon file)
  - Hoac nhap duong dan truc tiep (huu ich tren Colab: `/content/drive/MyDrive/video.mp4`)
  - Chon Preset tu dropdown
  - Chon ngon ngu nguon/dich
  - Bat/tat "Pause for SRT review"
  - Hien thi RAM/Disk/GPU
  
- **Khu vuc chinh:**
  - Nut **Start Pipeline** de bat dau
  - Progress bar tong the va trang thai tung stage
  - Tu dong cap nhat khi pipeline dang chay

#### Tab 2: SRT Editor

- Hien thi song song: phu de goc (ben trai) vs phu de da dich (ben phai)
- Phu de da dich **co the chinh sua truc tiep**
- Nhan **Save Changes** de luu
- Nhan **Continue Pipeline** (o Tab 1) de tiep tuc TTS voi ban dich moi

#### Tab 3: Output & Preview

- Xem truoc video ket qua ngay tren trinh duyet
- Nut **Download Video** de tai ve
- Nut **Sync to Google Drive** (tren Colab)
- Xem cac artifact trung gian (metadata, SRT, audio...)
- Xem log pipeline

### 5.4. Quy trinh su dung UI dien hinh

```
1. Upload video (hoac nhap path)
2. Chon preset: "Real Free" (khuyen dung cho lan dau)
3. Chon Target Language: "vi"
4. Bat "Pause for SRT review" (khuyen dung)
5. Nhan "Start Pipeline"
6. Doi stages 0-1-2 chay xong (STT + Translation)
7. Chuyen sang Tab "SRT Editor"
8. Doc va chinh sua ban dich cho chinh xac
9. Nhan "Save Changes"
10. Quay lai Tab "Pipeline", nhan "Continue Pipeline"
11. Doi stages 3-4-5-6 chay xong (TTS + Render)
12. Chuyen sang Tab "Output & Preview"
13. Xem truoc video, tai ve hoac sync len Drive
```

---

## 6. Cau hinh Preset chi tiet

### Bang so sanh Preset

| Preset | ASR Engine | ASR Model | Translation | TTS | Toc do | Chat luong | Can API key? |
|--------|-----------|-----------|-------------|-----|--------|------------|-------------|
| `mock` | Mock | -- | Mock | Mock | Cuc nhanh | Khong co | Khong |
| `fast_free` | faster-whisper | tiny | Google Free | Edge-TTS | Nhanh | Trung binh | Khong |
| `real_free` | faster-whisper | small | Google Free | Edge-TTS | Vua | Kha | Khong |
| `qwen_free` | faster-whisper | small | Qwen-MT-Turbo | Edge-TTS | Vua | Tot | Co (DashScope) |
| `balanced` | faster-whisper | large-v3 | Gemini 2.5 Flash | Edge-TTS | Cham | Rat tot | Co (Google) |
| `quality_api` | GPT-4o Transcribe | -- | GPT-4o Mini | Premium | Cham | Xuat sac | Co (OpenAI) |

### Khuyen nghi

- **Lan dau thu nghiem**: Dung `mock` de kiem tra pipeline chay khong loi
- **Su dung hang ngay (mien phi)**: Dung `real_free` hoac `qwen_free`
- **Can chat luong cao**: Dung `balanced` (can Gemini API key)
- **Video quan trong**: Dung `quality_api` (can OpenAI API key)

### Tao Preset tuy chinh

Tao file YAML moi trong `configs/presets/`:

```yaml
# configs/presets/my_custom.yaml
runtime:
  mode: execute

asr:
  engine: faster-whisper
  model: medium          # tiny < small < medium < large-v3
  compute_type: float16  # float16 (GPU) hoac int8 (CPU)
  cuda: true

translation:
  engine: qwen-mt
  model: qwen-mt-turbo
  qwen_api_key: "${QWEN_API_KEY:your-key-here}"

tts:
  engine: edge-tts
  voice_role: vi-VN-NamMinhNeural  # Giong nam Viet Nam
  voice_rate: "+10%"               # Tang toc 10%

video_processing:
  burn_subtitle: true
  remove_hardcoded_sub: true       # Bat inpainting xoa sub cung
  inpaint_engine: opencv
```

Su dung:
```bash
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/my_custom.yaml \
  --video-path video.mp4
```

---

## 7. Tuy chinh nang cao

### 7.1. Thay doi giong TTS (Edge-TTS)

Cac giong tieng Viet co san:
- `vi-VN-HoaiMyNeural` -- Giong nu (mac dinh)
- `vi-VN-NamMinhNeural` -- Giong nam

Cac giong tieng Anh pho bien:
- `en-US-JennyNeural` -- Giong nu My
- `en-US-GuyNeural` -- Giong nam My
- `en-GB-SoniaNeural` -- Giong nu Anh

Xem danh sach day du:
```bash
pip install edge-tts
edge-tts --list-voices | grep vi-VN
edge-tts --list-voices | grep en-US
```

### 7.2. Cau hinh Qwen API

1. Dang ky tai https://bailian.console.aliyun.com/
2. Tao API key tai trang Dashboard
3. Cau hinh bang 1 trong 2 cach:

**Cach 1: Bien moi truong (khuyen dung)**
```bash
export QWEN_API_KEY="sk-your-key-here"
```

**Cach 2: Ghi truc tiep trong YAML**
```yaml
translation:
  engine: qwen-mt
  qwen_api_key: "sk-your-key-here"
```

Cac model Qwen free tier:
- `qwen-mt-turbo` -- Dich may chuyen dung, nhanh, chinh xac
- `qwen-mt-plus` -- Dich may chat luong cao hon
- `qwen-turbo` -- LLM tong quat, dich bang prompt
- `qwen-plus` -- LLM manh hon

### 7.3. Xoa phu de cung (Hard-sub Removal)

Bat trong config:
```yaml
video_processing:
  remove_hardcoded_sub: true
  inpaint_engine: opencv  # Su dung OpenCV
```

Luu y:
- Hoat dong tot voi phu de tren nen don gian (mau den, trang)
- Kem hieu qua hon voi nen phuc tap (canh phim, hoat hinh)
- Xu ly toan bo frame nen **rat cham** voi video dai
- Nen dung cho video ngan hoac khi that su can thiet

### 7.4. Ghi de config bang dong lenh

Moi tham so co the ghi de khi chay CLI:
```bash
python3 -m videotransdub.cli run \
  --config configs/default.yaml \
  --config configs/presets/real_free.yaml \
  --video-path video.mp4 \
  --target-language ja \        # Ghi de ngon ngu dich
  --source-language en           # Ghi de ngon ngu nguon
```

### 7.5. Bien moi truong trong config

Config YAML ho tro cu phap `${VAR_NAME:default_value}`:

```yaml
translation:
  qwen_api_key: "${QWEN_API_KEY:}"           # Lay tu env, mac dinh rong
  model: "${TRANSLATION_MODEL:qwen-mt-turbo}" # Lay tu env, mac dinh qwen-mt-turbo
```

---

## 8. Quy trinh lam viec voi SRT Editor

### Tai sao can SRT Editor?

- Dich may thuong sai nghe nghia, ten rieng, thuat ngu chuyen nganh
- Sua phu de **truoc** khi TTS giup giong doc chinh xac hon
- Tiet kiem thoi gian re-render

### Quy trinh

1. **Bat "Pause for SRT review"** truoc khi Start Pipeline
2. Pipeline chay Stage 0 -> 1 -> 2 roi **tam dung**
3. Mo tab **SRT Editor**
4. Ben trai: phu de goc (chi doc)
5. Ben phai: phu de da dich (chinh sua duoc)
6. Sua cac loi dich, ten rieng, cach dien dat
7. Nhan **Save Changes**
8. Quay lai tab Pipeline, nhan **Continue Pipeline**
9. He thong chay tiep Stage 3 -> 4 -> 5 -> 6

### Dinh dang SRT

```
1
00:00:01,000 --> 00:00:04,500
Dong phu de thu nhat

2
00:00:05,000 --> 00:00:08,200
Dong phu de thu hai
```

Khi chinh sua, giu nguyen:
- So thu tu dong
- Timestamp (00:00:01,000 --> 00:00:04,500)
- Chi sua noi dung text

---

## 9. Google Drive Integration

### Tu dong mount (Colab)

Notebook Cell 1 tu dong mount Google Drive va tao cau truc:
```
Google Drive/
  MyDrive/
    VideoTransDub/
      output/         <-- Video da xu ly
      checkpoints/    <-- Checkpoint de resume
```

### Sync thu cong

Chay Cell 6 trong notebook hoac trong UI:
- Tab Output -> nhan **Sync to Google Drive**
- Tu dong copy video cuoi va manifest len Drive

### Loi ich cua Drive integration

1. **Khong mat data khi Colab ngat**: Checkpoint luu tren Drive, pipeline resume duoc
2. **Chia se de dang**: Video output tren Drive co the chia se link
3. **Luu tru lau dai**: Khong bi xoa khi Colab session het han

---

## 10. Xu ly loi thuong gap

### "ffmpeg not found"

```bash
# Ubuntu/Debian
sudo apt-get install -y ffmpeg

# Kiem tra
which ffmpeg
ffmpeg -version
```

### "faster-whisper: CUDA out of memory"

Giai phap:
- Dung model nho hon: `tiny` hoac `small` thay vi `large-v3`
- Dung `compute_type: int8` thay vi `float16`
- Hoac tat GPU: `cuda: false` (chay CPU, cham hon)

```yaml
asr:
  model: small
  compute_type: int8
  cuda: true  # Dat false neu khong co GPU
```

### "edge-tts: Connection error"

Edge-TTS can ket noi Internet. Kiem tra:
```bash
pip install edge-tts
edge-tts --text "Hello" --voice vi-VN-HoaiMyNeural --write-media test.mp3
```

### "dashscope: AuthenticationError"

- Kiem tra API key dung chua
- Kiem tra bien moi truong: `echo $QWEN_API_KEY`
- Kiem tra free tier con quota: https://bailian.console.aliyun.com/

### "Pipeline failed at stage X"

1. Kiem tra log:
   ```bash
   cat apps/videotransdub/runtime/workspace/<job-id>/logs/pipeline.log
   ```
2. Pipeline se tu dong resume tu stage loi khi chay lai
3. Neu muon chay lai tu dau, xoa thu muc workspace:
   ```bash
   rm -rf apps/videotransdub/runtime/workspace/<job-id>
   ```

### "Streamlit UI khong truy cap duoc tren Colab"

- Kiem tra cloudflared da cai chua: `which cloudflared`
- Thu dung port khac: `--server.port 8502`
- Neu tunnel loi, doi 30s roi chay lai Cell 4

### "Video output khong co tieng / tieng bi lech"

- Kiem tra TTS da tao audio chua: xem file trong `stage3/`
- Kiem tra audio_sync: xem `stage3_5/sync_plan.json`
- Thu tang `audio_sync.max_speedup` len 1.6 hoac 1.8

---

## 11. Cau truc thu muc du an

```
apps/videotransdub/
|
|-- configs/
|   |-- default.yaml              # Config goc (tat ca tham so)
|   |-- presets/
|       |-- mock.yaml             # Test khong can model
|       |-- fast_free.yaml        # Nhanh + mien phi
|       |-- real_free.yaml        # Chat luong kha + mien phi
|       |-- qwen_free.yaml        # Qwen-MT + mien phi
|       |-- balanced.yaml         # Can bot + can API key
|       |-- quality_api.yaml      # Chat luong cao nhat
|
|-- notebooks/
|   |-- videotransdub_colab.ipynb # Notebook Colab (one-click)
|
|-- src/videotransdub/
|   |-- app.py                    # Streamlit UI (Dark Mode)
|   |-- cli.py                    # CLI interface
|   |-- api.py                    # FastAPI (minimal)
|   |-- orchestrator.py           # Dieu phoi pipeline
|   |-- settings.py               # Quan ly cau hinh
|   |-- models.py                 # Data models (Pydantic)
|   |-- checkpoint.py             # Checkpoint/resume
|   |-- workspace.py              # Quan ly thu muc workspace
|   |-- registry.py               # Dang ky engine
|   |-- logging.py                # Cau hinh log
|   |
|   |-- engines/
|   |   |-- asr/
|   |   |   |-- whisper_engine.py     # faster-whisper (GPU/CPU)
|   |   |   |-- pyvideotrans_engine.py # Adapter upstream CLI
|   |   |   |-- mock_engine.py        # Mock test
|   |   |
|   |   |-- translate/
|   |   |   |-- qwen_engine.py        # Alibaba Qwen-MT
|   |   |   |-- pyvideotrans_engine.py # Adapter upstream CLI
|   |   |   |-- mock_engine.py        # Mock test
|   |   |
|   |   |-- tts/
|   |   |   |-- edge_tts_engine.py    # Microsoft Edge-TTS
|   |   |   |-- pyvideotrans_engine.py # Adapter upstream CLI
|   |   |   |-- mock_engine.py        # Mock test
|   |   |
|   |   |-- inpaint/
|   |       |-- opencv_engine.py      # OpenCV text removal
|   |       |-- passthrough_engine.py # Khong xu ly
|   |
|   |-- stages/                   # 8 giai doan pipeline
|   |   |-- preprocess.py         # Stage 0
|   |   |-- asr.py                # Stage 1
|   |   |-- translate.py          # Stage 2
|   |   |-- tts.py                # Stage 3
|   |   |-- audio_sync.py         # Stage 3.5
|   |   |-- audio_mix.py          # Stage 4
|   |   |-- video.py              # Stage 5
|   |   |-- finalize.py           # Stage 6
|   |
|   |-- utils/
|       |-- commands.py           # Chay lenh shell
|       |-- srt.py                # Doc/ghi file SRT
|
|-- runtime/                      # Thu muc chay (tu dong tao)
|   |-- workspace/                # Workspace moi job
|   |-- output/                   # Output chung
|   |-- uploads/                  # File upload tu UI
|
|-- install_deps.sh               # Script cai dat 1 lenh
|-- pyproject.toml                # Package definition
|-- GUIDE.md                      # File nay
|-- README.md                     # Gioi thieu ngan
```

---

## Phu luc: Lenh nhanh (Cheat Sheet)

```bash
# === LOCAL ===

# Smoke test (khong can GPU/model)
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/mock.yaml \
  --video-path video.mp4

# Dich video mien phi
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/real_free.yaml \
  --video-path video.mp4 --target-language vi

# Dich bang Qwen
export QWEN_API_KEY="sk-abd0a732837b414696fc23a8f933aa3b"
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/qwen_free.yaml \
  --video-path video.mp4 --target-language vi

# Khoi dong UI
streamlit run apps/videotransdub/src/videotransdub/app.py --theme.base dark

# Kiem tra config
PYTHONPATH=apps/videotransdub/src \
python3 -m videotransdub.cli validate \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/real_free.yaml


# === COLAB ===

# Cai dat 1 lenh
!bash apps/videotransdub/install_deps.sh

# Chay pipeline
!PYTHONPATH=apps/videotransdub/src python3 -m videotransdub.cli run \
  --config apps/videotransdub/configs/default.yaml \
  --config apps/videotransdub/configs/presets/real_free.yaml \
  --video-path /content/drive/MyDrive/video.mp4 \
  --target-language vi
```
