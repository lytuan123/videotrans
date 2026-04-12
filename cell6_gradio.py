# pyVideoTrans Studio — FastAPI Stable Edition
#
# Filename kept as "cell6_gradio.py" for continuity — the content is now
# FastAPI + inline HTML (Tailwind CDN) + polling. Rationale: Gradio's
# WebSocket-based architecture was unreliable on Colab:
#   - share=True  → *.gradio.live tunnel flaky ("Failed to fetch")
#   - share=False → Colab proxy mangles WS frames ("vỡ giao diện")
# Plain HTTP + polling fixes both issues completely.
#
# Architecture (unchanged): detached worker thread + job_state.json.
# Mất mạng / đóng tab / reload → job vẫn chạy trong background.

import os, sys, re, shutil, tempfile, time, json, threading, subprocess, traceback
from pathlib import Path

REPO = '/content/pyvideotrans'
if os.path.exists(REPO):
    os.chdir(REPO)
os.makedirs('/content/input', exist_ok=True)

STATE_FILE = f'{REPO}/job_state.json' if os.path.exists(REPO) else '/content/job_state.json'
LOG_FILE = f'{REPO}/pipeline.log' if os.path.exists(REPO) else '/content/pipeline.log'
API_KEYS_FILE = '/content/drive/MyDrive/pyvideotrans_backup/api_keys.json'

# ===================== CONSTANTS =====================

# label → (translate_type, provider_hint)
TRANSLATORS = {
    '🌐 Google (free, online)':              (0,  None),
    '🌐 Microsoft (free, online)':           (1,  None),
    '💻 M2M100 (LOCAL GPU, no key) ⭐':       (2,  None),
    '🔀 OpenRouter — free models ⭐':         (3,  'openrouter'),
    '🤖 OpenAI GPT (cần key)':               (3,  None),
    '🤖 DeepSeek (cần key)':                 (4,  None),
    '🤖 Google Gemini (cần key)':            (5,  None),
    '🤖 Local LLM / Ollama':                 (8,  None),
    '🌐 MyMemory API (free)':                (21, None),
}

OPENROUTER_FREE_MODELS = [
    'google/gemma-4-26b-a4b-it:free',
    'google/gemma-2-9b-it:free',
    'google/gemini-2.0-flash-exp:free',
    'meta-llama/llama-3.3-70b-instruct:free',
    'meta-llama/llama-3.1-70b-instruct:free',
    'deepseek/deepseek-chat-v3.1:free',
    'qwen/qwen-2.5-72b-instruct:free',
    'nousresearch/hermes-3-llama-3.1-405b:free',
    'microsoft/phi-3-mini-128k-instruct:free',
    'mistralai/mistral-7b-instruct:free',
]

TTS_TYPES = {
    '🔊 Edge-TTS (Microsoft, free, online)': 0,
    '🔊 Azure TTS (cần key)':                1,
    '🔊 Google Cloud TTS':                   2,
    '🔊 OpenAI TTS (cần key)':               3,
    '🔊 ElevenLabs (cần key)':               4,
    '🔊 F5-TTS (LOCAL clone giọng) ⭐':       10,
}

# STT channels: label → (recogn_type, model_name, env_key_needed_or_None)
# recogn_type values match videotrans/recognition/__init__.py:
#   0 = FASTER_WHISPER (local GPU, free)   5 = OPENAI_API (Whisper API, paid)
#   6 = GEMINI_SPEECH (free tier)          10 = DEEPGRAM (paid)
#   17 = ELEVENLABS (paid)
STT_CHANNELS = {
    '🏠 Faster-Whisper large-v3-turbo (local GPU, FREE) ⭐': (0, 'large-v3-turbo', None),
    '🏠 Faster-Whisper large-v3 (local GPU, FREE)':         (0, 'large-v3', None),
    '🏠 Faster-Whisper large-v2 (local GPU, FREE)':         (0, 'large-v2', None),
    '🏠 Faster-Whisper medium (local GPU, FREE)':           (0, 'medium', None),
    '🏠 Faster-Whisper small (local GPU, FREE, nhanh)':     (0, 'small', None),
    '🏠 Faster-Whisper tiny (local GPU, siêu nhanh)':       (0, 'tiny', None),
    '☁ OpenAI whisper-1 (paid, ~$0.006/phút)':              (5, 'whisper-1', 'OPENAI_API_KEY'),
    '☁ OpenAI gpt-4o-transcribe (paid, chất lượng cao)':    (5, 'gpt-4o-transcribe', 'OPENAI_API_KEY'),
    '☁ OpenAI gpt-4o-mini-transcribe (paid, rẻ)':           (5, 'gpt-4o-mini-transcribe', 'OPENAI_API_KEY'),
    '☁ Google Gemini Speech (free tier)':                   (6, 'gemini-2.0-flash', 'GEMINI_API_KEY'),
    '☁ Deepgram Nova-2 (paid, cực nhanh)':                  (10, 'nova-2', 'DEEPGRAM_API_KEY'),
    '☁ ElevenLabs Scribe v1 (paid, chính xác)':             (17, 'scribe_v1', 'ELEVENLABS_API_KEY'),
}
DEFAULT_STT_LABEL = '🏠 Faster-Whisper large-v3-turbo (local GPU, FREE) ⭐'

TARGET_LANGS = {
    '🇻🇳 Vietnamese':             'vi',
    '🇬🇧 English':                'en',
    '🇨🇳 Chinese (Simplified)':   'zh-cn',
    '🇹🇼 Chinese (Traditional)':  'zh-tw',
    '🇯🇵 Japanese':               'ja',
    '🇰🇷 Korean':                 'ko',
    '🇫🇷 French':                 'fr',
    '🇩🇪 German':                 'de',
    '🇪🇸 Spanish':                'es',
    '🇮🇹 Italian':                'it',
    '🇵🇹 Portuguese':             'pt',
    '🇷🇺 Russian':                'ru',
    '🇹🇭 Thai':                   'th',
    '🇮🇩 Indonesian':             'id',
}

API_KEY_FIELDS = [
    ('OPENROUTER_API_KEY',  '🔀 OpenRouter API Key (free models)', 'sk-or-v1-...'),
    ('OPENAI_API_KEY',      '🤖 OpenAI API Key (dùng cho cả GPT + Whisper API)', 'sk-...'),
    ('GEMINI_API_KEY',      '🤖 Google Gemini API Key (dùng cho cả Gemini Translate + Gemini Speech)', 'AIza...'),
    ('DEEPSEEK_API_KEY',    '🤖 DeepSeek API Key',                 'sk-...'),
    ('ANTHROPIC_API_KEY',   '🤖 Anthropic (Claude) API Key',       'sk-ant-...'),
    ('DEEPGRAM_API_KEY',    '🎧 Deepgram API Key (Nova-2 STT)',    ''),
    ('AZURE_SPEECH_KEY',    '🎙 Azure Speech Key',                 ''),
    ('AZURE_SPEECH_REGION', '🎙 Azure Speech Region',              'eastus'),
    ('ELEVENLABS_API_KEY',  '🎙 ElevenLabs API Key (dùng cho cả TTS + Scribe STT)', ''),
]


# ----- Edge-TTS voice catalog (from pyvideotrans' bundled JSON) -----
def _load_edge_voices():
    try:
        p = Path(f'{REPO}/videotrans/voicejson/edge_tts.json')
        d = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}
    out = {}
    for lang, vmap in d.items():
        if not isinstance(vmap, dict):
            continue
        pairs = []
        for display, vid in vmap.items():
            if isinstance(vid, str):
                pairs.append({'label': f'{display} — {vid}', 'id': vid})
            elif isinstance(vid, list) and vid:
                pairs.append({'label': f'{display} — {vid[0]}', 'id': vid[0]})
        if pairs:
            out[lang] = pairs
    return out

EDGE_VOICES = _load_edge_voices()

def _voices_for_short(short):
    return EDGE_VOICES.get(short, [])


# ===================== STATE + LOG =====================

def _fmt_elapsed(sec):
    sec = int(sec)
    return f'{sec // 60:d}m{sec % 60:02d}s'

def _read_state():
    try:
        return json.loads(Path(STATE_FILE).read_text(encoding='utf-8'))
    except Exception:
        return {'status': 'idle', 'message': 'Sẵn sàng. Chọn video và nhấn 🚀.', 'started_at': 0}

def _write_state(s):
    try:
        Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    Path(STATE_FILE).write_text(json.dumps(s, ensure_ascii=False), encoding='utf-8')

def _append_log(msg):
    try:
        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')

def _read_log(lines=100):
    try:
        all_lines = Path(LOG_FILE).read_text(encoding='utf-8').splitlines()
        return '\n'.join(all_lines[-lines:])
    except Exception:
        return ''


# ===================== API KEYS =====================

def _load_api_keys():
    try:
        return json.loads(Path(API_KEYS_FILE).read_text(encoding='utf-8'))
    except Exception:
        return {}

def _save_api_keys(**kwargs):
    existing = _load_api_keys()
    existing.update(kwargs)
    try:
        Path(API_KEYS_FILE).parent.mkdir(parents=True, exist_ok=True)
        Path(API_KEYS_FILE).write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        for k, v in kwargs.items():
            if v:
                os.environ[k] = v
            elif k in os.environ:
                del os.environ[k]
        n_set = sum(1 for v in existing.values() if v)
        return f'✅ Đã lưu {n_set} API key(s) vào Drive.'
    except Exception as e:
        return f'❌ Lỗi lưu: {e}'


# ===================== PIPELINE HELPERS =====================

def detect_language(audio_path):
    script = f'''
import torch
from faster_whisper import WhisperModel
device = "cuda" if torch.cuda.is_available() else "cpu"
compute = "float16" if device == "cuda" else "int8"
m = WhisperModel("tiny", device=device, compute_type=compute)
_, info = m.transcribe({audio_path!r}, language=None, vad_filter=True)
print("DETECTED_LANG:" + info.language, flush=True)
'''
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
        f.write(script)
        script_path = f.name
    try:
        r = subprocess.run(['uv', 'run', 'python', script_path],
                           cwd=REPO, capture_output=True, text=True, timeout=300)
    finally:
        os.unlink(script_path)
    m = re.search(r'DETECTED_LANG:(\S+)', (r.stdout or '') + (r.stderr or ''))
    if not m:
        raise RuntimeError(f'Detect fail:\n{(r.stderr or "")[-300:]}')
    return m.group(1)


def find_latest_output(input_path):
    stem = Path(input_path).stem
    nospace = re.sub(r'[\s\.#*?!:"]', '-', stem)
    cands = sorted(Path(REPO, 'output').glob(f'{nospace}*'),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def _patch_params_json(updates):
    pp = f'{REPO}/videotrans/params.json'
    os.makedirs(os.path.dirname(pp), exist_ok=True)
    d = {}
    if Path(pp).exists():
        try:
            d = json.loads(Path(pp).read_text(encoding='utf-8'))
        except Exception:
            pass
    d.update(updates)
    Path(pp).write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')


def _patch_cfg_json(updates):
    """Patch videotrans/cfg.json (global settings like aisendsrt, aitrans_context, cuda_com_type)."""
    pp = f'{REPO}/videotrans/cfg.json'
    os.makedirs(os.path.dirname(pp), exist_ok=True)
    d = {}
    if Path(pp).exists():
        try:
            d = json.loads(Path(pp).read_text(encoding='utf-8'))
        except Exception:
            pass
    d.update(updates)
    Path(pp).write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')


# ----- H100 / A100 / T4 GPU tuning -----
def _detect_gpu_and_tune():
    """Detect GPU model and write optimal compute_type + threading settings to cfg.json.

    - H100 / A100 / L4 / L40: float16, large batch, high concurrency
    - T4 / V100: float16 (fallback int8_float16 if OOM)
    - No GPU: int8 on CPU
    """
    gpu_name = ''
    try:
        r = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5,
        )
        gpu_name = (r.stdout or '').strip().split('\n')[0]
    except Exception:
        gpu_name = ''

    name_lower = gpu_name.lower()
    if 'h100' in name_lower or 'h200' in name_lower:
        tune = {
            'cuda_com_type': 'float16',
            'beam_size': 5,
            'best_of': 5,
            'trans_thread': 20,
            'aitrans_thread': 80,
            'dubbing_thread': 4,
            'edgetts_max_concurrent_tasks': 20,
        }
        tier = 'H100 (tối đa hiệu năng)'
    elif 'a100' in name_lower:
        tune = {
            'cuda_com_type': 'float16',
            'beam_size': 5,
            'best_of': 5,
            'trans_thread': 15,
            'aitrans_thread': 60,
            'dubbing_thread': 3,
            'edgetts_max_concurrent_tasks': 15,
        }
        tier = 'A100'
    elif 'l4' in name_lower or 'l40' in name_lower:
        tune = {
            'cuda_com_type': 'float16',
            'beam_size': 5,
            'best_of': 5,
            'trans_thread': 12,
            'aitrans_thread': 50,
            'dubbing_thread': 2,
            'edgetts_max_concurrent_tasks': 12,
        }
        tier = 'L4/L40'
    elif 't4' in name_lower or 'v100' in name_lower:
        tune = {
            'cuda_com_type': 'float16',
            'beam_size': 5,
            'trans_thread': 8,
            'aitrans_thread': 30,
            'dubbing_thread': 1,
            'edgetts_max_concurrent_tasks': 10,
        }
        tier = 'T4/V100'
    elif gpu_name:
        tune = {'cuda_com_type': 'float16'}
        tier = gpu_name
    else:
        tune = {'cuda_com_type': 'int8'}
        tier = 'CPU fallback'

    _patch_cfg_json(tune)
    return gpu_name, tier, tune


# ----- LLM prompt injection for "Translation context" feature -----
# List of prompt files pyvideotrans reads for LLM translators. We inject a
# USER_CONTEXT section into each of these so the feature works regardless of
# which LLM translator the user picks (OpenRouter, ChatGPT, DeepSeek, Gemini, ...).
_LLM_PROMPT_FILES = [
    'videotrans/prompts/srt/openrouter.txt',
    'videotrans/prompts/srt/chatgpt.txt',
    'videotrans/prompts/srt/deepseek.txt',
    'videotrans/prompts/srt/gemini.txt',
    'videotrans/prompts/srt/localllm.txt',
    'videotrans/prompts/srt/ai302.txt',
    'videotrans/prompts/srt/zhipuai.txt',
    'videotrans/prompts/srt/siliconflow.txt',
    'videotrans/prompts/text/openrouter.txt',
    'videotrans/prompts/text/chatgpt.txt',
    'videotrans/prompts/text/deepseek.txt',
    'videotrans/prompts/text/gemini.txt',
    'videotrans/prompts/text/localllm.txt',
    'videotrans/prompts/text/ai302.txt',
    'videotrans/prompts/text/zhipuai.txt',
    'videotrans/prompts/text/siliconflow.txt',
]


def _inject_translation_context(context_text, reference_text=''):
    """Inject user-provided context into every LLM prompt file.

    Idempotent: we keep a one-time backup `.orig` per file and always restore
    from backup before injecting — so calling this with empty context restores
    all prompts to vanilla upstream state.

    Injection point: just above the `# ACTUAL TASK` marker. We wrap the block
    in <USER_CONTEXT> tags and instruct the LLM to treat it as background.
    """
    ctx = (context_text or '').strip()
    ref = (reference_text or '').strip()
    for rel in _LLM_PROMPT_FILES:
        p = Path(REPO) / rel
        if not p.exists():
            continue
        bak = p.with_suffix(p.suffix + '.orig')
        try:
            if not bak.exists():
                shutil.copy(str(p), str(bak))
            original = bak.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        if not ctx and not ref:
            # Restore vanilla
            try:
                p.write_text(original, encoding='utf-8')
            except Exception:
                pass
            continue

        block_parts = [
            '',
            '# USER TRANSLATION CONTEXT (CRITICAL — READ FIRST)',
            '<USER_CONTEXT>',
        ]
        if ctx:
            block_parts.append(ctx)
        if ref:
            block_parts.append('')
            block_parts.append('---REFERENCE SCRIPTS---')
            block_parts.append(ref)
        block_parts += [
            '</USER_CONTEXT>',
            '',
            '**[INSTRUCTION]:** The `<USER_CONTEXT>` above describes the world, characters, tone, style, and terminology of the source material. Use it to:',
            '1. Translate character names, place names, and jargon CONSISTENTLY with the reference (do NOT re-invent).',
            '2. Match the narration tone and register the user described (e.g., shonen anime, noir thriller, documentary, etc.).',
            '3. Resolve ambiguous pronouns / typos using the context.',
            '**DO NOT translate the USER_CONTEXT itself — it is background only.**',
            '',
        ]
        injection = '\n'.join(block_parts)

        if '# ACTUAL TASK' in original:
            patched = original.replace('# ACTUAL TASK', injection + '# ACTUAL TASK', 1)
        else:
            patched = injection + original
        try:
            p.write_text(patched, encoding='utf-8')
        except Exception:
            pass


# ===================== BACKGROUND WORKER =====================
# Unchanged architecture: detached thread, all state to job_state.json.
# This is the SAME business logic as the Gradio version — only the UI layer
# (Gradio Blocks → FastAPI + HTML) has changed.

_worker_lock = threading.Lock()
_worker_thread = None


def _worker(params):
    try:
        t_start = time.time()
        Path(LOG_FILE).write_text(f'[Bắt đầu: {time.ctime()}]\n', encoding='utf-8')
        _write_state({'status': 'running', 'message': '📁 Chuẩn bị input...', 'started_at': t_start})

        # GPU auto-tune (H100 / A100 / T4 → optimal float16 + threading)
        try:
            gpu_name, tier, tune = _detect_gpu_and_tune()
            if gpu_name:
                _append_log(f'🏎 GPU detected: {gpu_name} → tier "{tier}" → {tune}')
            else:
                _append_log(f'🖥 No GPU detected → CPU fallback ({tune}).')
        except Exception as _e:
            _append_log(f'⚠ GPU auto-tune skipped: {_e}')

        video_path = params['video_path']
        safe_name = re.sub(r'[^\w\-.]', '_', os.path.basename(video_path))
        input_path = f'/content/input/{safe_name}'
        if os.path.abspath(video_path) != os.path.abspath(input_path):
            shutil.copy(video_path, input_path)
        _append_log(f'📁 Input: {input_path}')

        # -------- STT channel routing: patch params.json with credentials if a cloud STT is chosen --------
        stt_recogn_type = int(params.get('stt_recogn_type', 0))
        stt_model_name = params.get('stt_model') or 'large-v3-turbo'
        saved_keys = _load_api_keys()
        def _key(env_name):
            return saved_keys.get(env_name) or os.environ.get(env_name, '')

        if stt_recogn_type == 5:  # OpenAI Whisper API
            k = _key('OPENAI_API_KEY')
            if not k:
                _append_log('❌ STT OpenAI API: thiếu OPENAI_API_KEY (vào 🔑 API Keys).')
                _write_state({'status': 'error', 'message': '❌ Thiếu OPENAI_API_KEY cho STT.', 'started_at': t_start})
                return
            _patch_params_json({
                'openairecognapi_key': k,
                'openairecognapi_api': 'https://api.openai.com/v1',
                'openairecognapi_model': stt_model_name,
            })
            _append_log(f'☁ STT = OpenAI API / {stt_model_name}')
        elif stt_recogn_type == 6:  # Gemini Speech
            k = _key('GEMINI_API_KEY')
            if not k:
                _append_log('❌ STT Gemini: thiếu GEMINI_API_KEY.')
                _write_state({'status': 'error', 'message': '❌ Thiếu GEMINI_API_KEY cho STT.', 'started_at': t_start})
                return
            _patch_params_json({'gemini_key': k, 'gemini_model': stt_model_name})
            _append_log(f'☁ STT = Gemini / {stt_model_name}')
        elif stt_recogn_type == 10:  # Deepgram
            k = _key('DEEPGRAM_API_KEY')
            if not k:
                _append_log('❌ STT Deepgram: thiếu DEEPGRAM_API_KEY.')
                _write_state({'status': 'error', 'message': '❌ Thiếu DEEPGRAM_API_KEY.', 'started_at': t_start})
                return
            _patch_params_json({'deepgram_apikey': k, 'deepgram_model': stt_model_name})
            _append_log(f'☁ STT = Deepgram / {stt_model_name}')
        elif stt_recogn_type == 17:  # ElevenLabs Scribe
            k = _key('ELEVENLABS_API_KEY')
            if not k:
                _append_log('❌ STT ElevenLabs: thiếu ELEVENLABS_API_KEY.')
                _write_state({'status': 'error', 'message': '❌ Thiếu ELEVENLABS_API_KEY.', 'started_at': t_start})
                return
            _patch_params_json({'elevenlabstts_key': k, 'elevenlabs_stt_model': stt_model_name})
            _append_log(f'☁ STT = ElevenLabs Scribe / {stt_model_name}')
        else:
            _append_log(f'🏠 STT = Faster-Whisper local / {stt_model_name}')

        # -------- Translation context: inject into all LLM prompts --------
        ctx_text = (params.get('context_text') or '').strip()
        ref_text = (params.get('reference_text') or '').strip()
        if ctx_text or ref_text:
            _inject_translation_context(ctx_text, ref_text)
            _patch_cfg_json({'aisendsrt': True, 'aitrans_context': True})
            _append_log(f'🎭 Translation context: {len(ctx_text)} chars + {len(ref_text)} ref chars injected into LLM prompts.')
        else:
            # Ensure vanilla prompts when user clears context across runs
            _inject_translation_context('', '')

        # Reference voice — only F5-TTS uses this
        if params['tts_code'] == 10:
            dst = f'{REPO}/f5-tts/vi_default.wav'
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if params.get('ref_upload'):
                shutil.copy(params['ref_upload'], dst)
                try:
                    from pydub import AudioSegment
                    a = AudioSegment.from_file(dst)
                    if len(a) > 10000:
                        a[:10000].export(dst, format='wav')
                except Exception as e:
                    _append_log(f'⚠️ pydub trim: {e}')
                ref_txt = (params.get('ref_text') or '').strip() or 'Xin chào, tôi là trợ lý lồng tiếng AI.'
                _append_log('🎙 Reference voice (user upload).')
            else:
                ref_txt = 'Xin chào, tôi là trợ lý lồng tiếng AI.'
                if not os.path.exists(dst):
                    _append_log('⚠️ Tạo mẫu HoaiMyNeural...')
                    subprocess.run(
                        ['uv', 'run', 'edge-tts', '--voice', 'vi-VN-HoaiMyNeural',
                         '--text', ref_txt, '--write-media', dst],
                        cwd=REPO,
                    )
                _append_log('🎙 Default HoaiMyNeural.')

            _patch_params_json({
                'f5tts_role': f'vi_default.wav#{ref_txt}',
                'f5tts_url': 'http://127.0.0.1:7860',
            })

        # OpenRouter override (patches videotrans/params.json chatgpt_* fields)
        provider = params.get('provider_hint')
        if provider == 'openrouter':
            or_key = os.environ.get('OPENROUTER_API_KEY', '') or _load_api_keys().get('OPENROUTER_API_KEY', '')
            if not or_key:
                _append_log('❌ OpenRouter: thiếu OPENROUTER_API_KEY (vào 🔑 API Keys để nhập).')
                _write_state({'status': 'error', 'message': '❌ Thiếu OPENROUTER_API_KEY.', 'started_at': t_start})
                return
            model_id = (params.get('openrouter_model') or '').strip() or OPENROUTER_FREE_MODELS[0]
            _append_log(f'🔀 OpenRouter model: {model_id}')
            _patch_params_json({
                'chatgpt_key': or_key,
                'chatgpt_api': 'https://openrouter.ai/api/v1',
                'chatgpt_model': model_id,
            })

        # Source language detection
        if params['auto_detect']:
            _write_state({'status': 'running', 'message': '🔍 Detecting source language...', 'started_at': t_start})
            _append_log('🔍 Detecting...')
            source_lang = detect_language(input_path)
            _append_log(f'✅ Detected: {source_lang}')
        else:
            source_lang = (params['manual_source'] or 'en').strip()
            _append_log(f'ℹ Manual source: {source_lang}')

        tgt_code = params['target_code']

        # Pre-translated SRT injection (skip translation step)
        use_pretranslated = bool(params.get('translated_srt'))
        if use_pretranslated:
            _nospacebasename = re.sub(r'[\s\. #*?!:"]', '-', Path(input_path).stem)
            _target_dir = f'{REPO}/output/{_nospacebasename}'
            os.makedirs(_target_dir, exist_ok=True)
            _tgt_srt = f'{_target_dir}/{tgt_code}.srt'
            shutil.copy(params['translated_srt'], _tgt_srt)
            _append_log(f'📄 Pre-translated SRT injected → {_tgt_srt}')
            _append_log('   Bước dịch máy sẽ được BỎ QUA — lồng tiếng theo đúng SRT này.')

        cmd = [
            'uv', 'run', 'cli.py', '--task', 'vtv',
            '--name', input_path,
            '--recogn_type', str(stt_recogn_type),
            '--model_name', stt_model_name,
            '--detect_language', source_lang,
            '--translate_type', str(params['translator_code']),
            '--source_language_code', source_lang,
            '--target_language_code', tgt_code,
            '--tts_type', str(params['tts_code']),
            '--subtitle_type', '1',
            '--cuda',
        ]
        if use_pretranslated:
            cmd += ['--no-clear-cache']

        tts_code = params['tts_code']
        if tts_code == 10:
            cmd += ['--voice_role', 'vi_default.wav']
        else:
            voice_id = (params.get('voice_id') or '').strip()
            if voice_id:
                cmd += ['--voice_role', voice_id]

        def _fmt_pct(v):
            v = int(v or 0)
            return f'+{v}%' if v >= 0 else f'{v}%'
        def _fmt_hz(v):
            v = int(v or 0)
            return f'+{v}Hz' if v >= 0 else f'{v}Hz'

        vr = _fmt_pct(params.get('voice_rate', 0))
        vol = _fmt_pct(params.get('volume', 0))
        pitch = _fmt_hz(params.get('pitch', 0))
        if vr != '+0%':
            cmd += ['--voice_rate', vr]
        if vol != '+0%':
            cmd += ['--volume', vol]
        if pitch != '+0Hz':
            cmd += ['--pitch', pitch]

        if params.get('voice_autorate'):
            cmd += ['--voice_autorate']

        _append_log('🚀 CMD: ' + ' '.join(cmd))
        _write_state({'status': 'running', 'message': f'🚀 {source_lang} → {tgt_code}', 'started_at': t_start})

        env = {
            **os.environ,
            'PYTHONUNBUFFERED': '1',
            'TQDM_DISABLE': '1',
            'HF_HUB_DISABLE_PROGRESS_BARS': '1',
            # H100/A100 optimizations: expandable segments avoid OOM at large batches,
            # TF32 lets M2M100/Transformers use tensor cores at fp32 paths.
            'PYTORCH_CUDA_ALLOC_CONF': 'expandable_segments:True',
            'NVIDIA_TF32_OVERRIDE': '1',
            'TORCH_ALLOW_TF32_CUBLAS_OVERRIDE': '1',
            # Faster-Whisper / CTranslate2 threading
            'OMP_NUM_THREADS': '8',
            'MKL_NUM_THREADS': '8',
        }
        saved = _load_api_keys()
        for k, v in saved.items():
            if v:
                env[k] = v
        if provider == 'openrouter':
            or_key = saved.get('OPENROUTER_API_KEY') or os.environ.get('OPENROUTER_API_KEY', '')
            if or_key:
                env['OPENAI_API_KEY'] = or_key
                env['OPENAI_BASE_URL'] = 'https://openrouter.ai/api/v1'
                env['OPENAI_MODEL'] = (params.get('openrouter_model') or OPENROUTER_FREE_MODELS[0])

        with open(LOG_FILE, 'a', encoding='utf-8') as f_log:
            rc = subprocess.run(cmd, cwd=REPO, stdout=f_log,
                                stderr=subprocess.STDOUT, env=env).returncode

        elapsed = _fmt_elapsed(time.time() - t_start)
        if rc != 0:
            _append_log(f'\n❌ Lỗi (rc={rc}) sau {elapsed}')
            _write_state({'status': 'error', 'message': f'❌ Lỗi sau {elapsed}. Xem log.', 'started_at': t_start})
            return

        out_dir = find_latest_output(input_path)
        result = {'final_video': None, 'src_srt': None, 'tgt_srt': None, 'audio': None}
        if out_dir and out_dir.is_dir():
            files_all = list(out_dir.rglob('*'))
            vids = [str(p) for p in files_all if p.suffix.lower() in ('.mp4', '.mkv', '.mov')]
            srts = [str(p) for p in files_all if p.suffix.lower() == '.srt']
            auds = [str(p) for p in files_all if p.suffix.lower() in ('.wav', '.m4a', '.mp3')]
            result['final_video'] = vids[0] if vids else None
            result['src_srt'] = next((s for s in srts if f'_{source_lang}' in s),
                                     srts[0] if srts else None)
            result['tgt_srt'] = next((s for s in srts if f'_{tgt_code}' in s),
                                     srts[-1] if len(srts) > 1 else None)
            result['audio'] = auds[0] if auds else None
            if params.get('save_drive') and os.path.exists('/content/drive/MyDrive'):
                dest = f'/content/drive/MyDrive/pyvideotrans_output/{out_dir.name}'
                shutil.copytree(str(out_dir), dest, dirs_exist_ok=True)
                _append_log(f'📁 Saved to Drive: {dest}')

        _append_log(f'\n✅ Hoàn thành sau {elapsed}')
        _write_state({
            'status': 'done',
            'message': f'✅ Hoàn thành sau {elapsed}',
            'started_at': t_start,
            'result': result,
        })
    except Exception as e:
        _append_log(f'\n❌ Exception: {e}\n{traceback.format_exc()}')
        _write_state({'status': 'error', 'message': f'❌ {e}', 'started_at': time.time()})


# ===================== FASTAPI APP =====================

try:
    from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
except ImportError:
    print('📦 Installing FastAPI stack (one-time)...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                    'fastapi', 'uvicorn', 'python-multipart'], check=True)
    from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

import uvicorn

app = FastAPI(title='pyVideoTrans Studio')


HTML_PAGE = r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>pyVideoTrans Studio</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body { font-family: system-ui, -apple-system, "Segoe UI", "Noto Sans", "Noto Sans Vietnamese", sans-serif; }
  .card { background: white; border-radius: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 1.25rem; border: 1px solid rgb(226 232 240); }
  .btn-primary { background-image: linear-gradient(to right, rgb(37 99 235), rgb(8 145 178)); color: white; font-weight: 600; border-radius: 0.5rem; padding: 0.75rem 1.25rem; box-shadow: 0 1px 2px rgba(0,0,0,0.1); transition: all 0.15s; }
  .btn-primary:hover { background-image: linear-gradient(to right, rgb(29 78 216), rgb(14 116 144)); }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-secondary { background: rgb(241 245 249); color: rgb(30 41 59); font-weight: 500; border-radius: 0.5rem; padding: 0.5rem 1rem; transition: background 0.15s; display: inline-block; text-decoration: none; }
  .btn-secondary:hover { background: rgb(226 232 240); }
  .input { width: 100%; border: 1px solid rgb(203 213 225); border-radius: 0.5rem; padding: 0.5rem 0.75rem; outline: none; transition: ring 0.15s; }
  .input:focus { border-color: rgb(59 130 246); box-shadow: 0 0 0 3px rgba(59,130,246,0.15); }
  .label { display: block; font-size: 0.875rem; font-weight: 500; color: rgb(51 65 85); margin-bottom: 0.25rem; }
  .badge { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.25rem 0.625rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
  details > summary { list-style: none; cursor: pointer; font-weight: 600; color: rgb(51 65 85); display: flex; justify-content: space-between; padding: 0.5rem 0; }
  details > summary::-webkit-details-marker { display: none; }
  details[open] > summary .chev { transform: rotate(180deg); }
  .chev { transition: transform 0.2s; }
  .slider-row { display: flex; align-items: center; gap: 0.75rem; margin: 0.5rem 0; }
</style>
</head>
<body class="bg-gradient-to-br from-slate-50 to-blue-50 min-h-screen">
<div class="max-w-6xl mx-auto p-4 sm:p-6">

  <header class="flex items-center justify-between mb-6 flex-wrap gap-2">
    <div>
      <h1 class="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent">🎬 pyVideoTrans Studio</h1>
      <p class="text-slate-600 text-sm mt-1">Stable FastAPI edition • Zero "connection lost" • OpenRouter free models</p>
    </div>
    <div class="flex gap-2 items-center">
      <span id="conn-badge" class="badge" style="background:#dcfce7;color:#15803d">● Connected</span>
      <button id="btn-keys" class="btn-secondary">🔑 API Keys</button>
    </div>
  </header>

  <div class="grid md:grid-cols-2 gap-5">
    <!-- LEFT: video upload + action + status -->
    <div class="card space-y-3">
      <label class="label">📹 Video input</label>
      <input type="file" id="video" accept="video/*" class="input">
      <video id="video-preview" controls class="w-full rounded-lg hidden bg-black"></video>

      <button id="btn-start" class="btn-primary w-full text-lg">🚀 BẮT ĐẦU DỊCH</button>
      <div id="start-msg" class="text-sm text-slate-600 min-h-[1.25rem]"></div>

      <div class="border-t pt-3">
        <div class="flex items-center gap-2 flex-wrap">
          <span id="status-badge" class="badge" style="background:#f1f5f9;color:#475569">● Sẵn sàng</span>
          <span id="elapsed" class="text-xs text-slate-500"></span>
        </div>
        <div id="status-msg" class="text-sm text-slate-700 mt-2">Sẵn sàng. Chọn video và nhấn 🚀.</div>
      </div>

      <details class="border-t pt-1">
        <summary>🎙 Clone giọng (F5-TTS) <span class="chev">▾</span></summary>
        <div class="pt-2 space-y-2">
          <input type="file" id="ref-upload" accept="audio/*" class="input">
          <input type="text" id="ref-text" class="input" placeholder="Transcript của reference (bỏ trống = HoaiMy mặc định)">
        </div>
      </details>

      <details class="border-t pt-1">
        <summary>📄 Dùng bản dịch có sẵn <span class="chev">▾</span></summary>
        <div class="pt-2">
          <input type="file" id="translated-srt" accept=".srt,.txt" class="input">
          <p class="text-xs text-slate-500 mt-1">Nếu upload, bước dịch máy sẽ <b>bị bỏ qua</b> — hệ thống lồng tiếng theo đúng SRT này.</p>
        </div>
      </details>
    </div>

    <!-- RIGHT: pipeline config -->
    <div class="card space-y-3">
      <h3 class="font-semibold text-slate-800">⚙️ Cấu hình pipeline</h3>
      <div>
        <label class="label">🎧 STT channel (Whisper local hoặc API trả phí)</label>
        <select id="stt-channel" class="input"></select>
        <p class="text-xs text-slate-500 mt-1">Local Faster-Whisper trên H100/A100 cực nhanh và miễn phí. Chọn API trả phí nếu cần độ chính xác tối đa.</p>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="label">Auto-detect source</label>
          <select id="auto-detect" class="input">
            <option value="true">Bật (khuyến nghị)</option>
            <option value="false">Tắt</option>
          </select>
        </div>
        <div>
          <label class="label">Source (khi tắt auto)</label>
          <input type="text" id="manual-source" value="en" class="input">
        </div>
      </div>
      <div>
        <label class="label">🌐 Translator</label>
        <select id="translator" class="input"></select>
      </div>
      <div>
        <label class="label">🔀 OpenRouter model (chỉ dùng khi chọn OpenRouter)</label>
        <input list="openrouter-list" id="openrouter-model" class="input">
        <datalist id="openrouter-list"></datalist>
      </div>
      <div>
        <label class="label">🎯 Target language</label>
        <select id="target-lang" class="input"></select>
      </div>
      <div>
        <label class="label">🔊 TTS engine</label>
        <select id="tts" class="input"></select>
      </div>

      <details class="border-t pt-1">
        <summary>🎛 Điều chỉnh giọng <span class="chev">▾</span></summary>
        <div class="pt-2 space-y-2">
          <div>
            <label class="label">🗣 Voice (tự lọc theo target)</label>
            <input list="voices-list" id="voice-role" class="input" placeholder="Chọn hoặc gõ voice ID">
            <datalist id="voices-list"></datalist>
          </div>
          <div class="slider-row">
            <label class="w-24 text-sm">⚡ Rate</label>
            <input type="range" id="voice-rate" min="-50" max="100" step="5" value="0" class="flex-1">
            <span id="voice-rate-val" class="w-14 text-right text-sm font-mono">+0%</span>
          </div>
          <div class="slider-row">
            <label class="w-24 text-sm">🔊 Volume</label>
            <input type="range" id="volume" min="-50" max="50" step="5" value="0" class="flex-1">
            <span id="volume-val" class="w-14 text-right text-sm font-mono">+0%</span>
          </div>
          <div class="slider-row">
            <label class="w-24 text-sm">🎵 Pitch</label>
            <input type="range" id="pitch" min="-50" max="50" step="5" value="0" class="flex-1">
            <span id="pitch-val" class="w-14 text-right text-sm font-mono">+0Hz</span>
          </div>
        </div>
      </details>

      <div class="flex gap-4 border-t pt-3 text-sm">
        <label class="flex items-center gap-2"><input type="checkbox" id="voice-autorate" checked> Voice autorate</label>
        <label class="flex items-center gap-2"><input type="checkbox" id="save-drive" checked> 💾 Lưu Drive</label>
      </div>
    </div>
  </div>

  <!-- TRANSLATION CONTEXT -->
  <div class="card mt-5">
    <h3 class="font-semibold text-slate-800">🎭 Translation context &nbsp;<span class="text-xs font-normal text-slate-500">(chỉ áp dụng cho các translator dùng LLM: OpenRouter / GPT / Gemini / DeepSeek / Local LLM)</span></h3>
    <p class="text-sm text-slate-600 mt-1 mb-3">Mô tả thế giới / nhân vật / phong cách của video để LLM dịch nhất quán. Ví dụ: <i>"Đây là một tập One Piece. Nhân vật chính: Luffy (thuyền trưởng Mũ Rơm, năng nổ), Zoro (kiếm sĩ), Nami (thông minh, hám tiền). Phong cách: shonen anime, nhiệt huyết, có yếu tố hài. Giữ nguyên các thuật ngữ: Haki, Devil Fruit, Grand Line, Akuma no Mi."</i></p>
    <textarea id="context-text" class="input" rows="5" placeholder="Dán mô tả bối cảnh, nhân vật, phong cách, thuật ngữ chuyên ngành..."></textarea>
    <div class="mt-3">
      <label class="label">📚 Reference scripts (tuỳ chọn, .txt/.md/.srt)</label>
      <input type="file" id="reference-script" accept=".txt,.md,.srt" class="input">
      <p class="text-xs text-slate-500 mt-1">Upload script của các tập/chương liên quan — LLM sẽ đọc để nhất quán thuật ngữ & văn phong. Tối đa ~60KB (sẽ cắt nếu vượt).</p>
    </div>
    <div class="flex gap-2 mt-2">
      <button id="btn-context-preset-onepiece" class="btn-secondary text-xs">🏴‍☠ Preset One Piece</button>
      <button id="btn-context-preset-docu" class="btn-secondary text-xs">🎬 Preset Documentary</button>
      <button id="btn-context-clear" class="btn-secondary text-xs">🗑 Clear</button>
    </div>
  </div>

  <!-- RESULTS -->
  <div id="results-card" class="card mt-5 hidden">
    <h3 class="font-semibold text-slate-800 mb-3">🎁 Kết quả</h3>
    <div class="grid md:grid-cols-2 gap-4">
      <video id="result-video" controls class="w-full rounded-lg bg-black"></video>
      <div class="space-y-2 text-sm">
        <a id="dl-video" class="block btn-secondary text-center" download>⬇ Video đã dịch</a>
        <a id="dl-src-srt" class="block btn-secondary text-center" download>⬇ SRT gốc</a>
        <a id="dl-tgt-srt" class="block btn-secondary text-center" download>⬇ SRT đã dịch</a>
        <a id="dl-audio" class="block btn-secondary text-center" download>⬇ Audio dub</a>
      </div>
    </div>
  </div>

  <!-- LOG -->
  <div class="card mt-5">
    <div class="flex items-center justify-between mb-2">
      <h3 class="font-semibold text-slate-800">📜 Log pipeline (auto-refresh 2s)</h3>
      <button id="btn-clear-log" class="btn-secondary text-sm">🗑 Clear</button>
    </div>
    <pre id="log" class="bg-slate-900 text-green-300 text-xs p-3 rounded-lg overflow-auto whitespace-pre-wrap" style="max-height:24rem">(chưa có log)</pre>
  </div>

  <footer class="text-center text-xs text-slate-400 mt-6">
    pyVideoTrans Studio • FastAPI stable edition • <a href="https://github.com/jianchang512/pyvideotrans" class="underline">upstream</a>
  </footer>
</div>

<!-- API KEYS MODAL -->
<div id="keys-modal" class="fixed inset-0 bg-black/40 hidden items-center justify-center z-50 p-4">
  <div class="bg-white rounded-xl shadow-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-auto">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-bold">🔑 API Keys</h2>
      <button id="btn-keys-close" class="text-slate-500 text-2xl leading-none">&times;</button>
    </div>
    <p class="text-sm text-slate-600 mb-4">Lưu 1 lần trên Drive, dùng mãi. Free options (Google/MS/M2M100/Edge-TTS/<b>OpenRouter free</b>) không cần key riêng.</p>
    <div id="keys-form" class="space-y-3"></div>
    <div class="flex items-center gap-3 mt-5">
      <button id="btn-keys-save" class="btn-primary">💾 Lưu vào Drive</button>
      <span id="keys-msg" class="text-sm text-slate-600"></span>
    </div>
    <div class="mt-4 text-xs text-slate-500">
      OpenRouter miễn phí: lấy key tại <a href="https://openrouter.ai/keys" target="_blank" class="underline">openrouter.ai/keys</a>, dùng qua OpenAI SDK với <code>base_url="https://openrouter.ai/api/v1"</code>.
    </div>
  </div>
</div>

<script>
const $ = (id) => document.getElementById(id);
let CONFIG = {};
let lastConnOk = null;

async function fetchJSON(url, opts) {
  try {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    setConn(true);
    return await r.json();
  } catch (e) {
    setConn(false);
    throw e;
  }
}

function setConn(ok) {
  if (ok === lastConnOk) return;
  lastConnOk = ok;
  const b = $('conn-badge');
  if (ok) { b.textContent = '● Connected'; b.style.background = '#dcfce7'; b.style.color = '#15803d'; }
  else    { b.textContent = '● Retrying';  b.style.background = '#fef3c7'; b.style.color = '#b45309'; }
}

async function loadConfig() {
  CONFIG = await fetchJSON('/api/config');
  CONFIG.stt_channels.forEach(label => $('stt-channel').add(new Option(label, label)));
  $('stt-channel').value = CONFIG.stt_default;

  CONFIG.translators.forEach(t => $('translator').add(new Option(t.label, t.label)));
  $('translator').value = '💻 M2M100 (LOCAL GPU, no key) ⭐';

  CONFIG.openrouter_models.forEach(m => {
    const o = document.createElement('option'); o.value = m; $('openrouter-list').appendChild(o);
  });
  $('openrouter-model').value = CONFIG.openrouter_models[0];

  Object.keys(CONFIG.target_langs).forEach(l => $('target-lang').add(new Option(l, l)));
  $('target-lang').value = '🇻🇳 Vietnamese';

  Object.keys(CONFIG.tts_types).forEach(t => $('tts').add(new Option(t, t)));
  $('tts').value = '🔊 F5-TTS (LOCAL clone giọng) ⭐';

  await updateVoices();

  // Build API keys form
  const form = $('keys-form');
  form.innerHTML = '';
  CONFIG.api_key_fields.forEach(f => {
    const [env, label, placeholder] = f;
    const isPw = env !== 'AZURE_SPEECH_REGION';
    const wrap = document.createElement('div');
    wrap.innerHTML =
      '<label class="label">' + label + '</label>' +
      '<input type="' + (isPw ? 'password' : 'text') + '" id="key-' + env +
      '" class="input" placeholder="' + placeholder + '">';
    form.appendChild(wrap);
  });
  try {
    const keys = await fetchJSON('/api/keys');
    Object.entries(keys).forEach(([env, val]) => {
      const inp = $('key-' + env);
      if (inp && val) inp.value = val;
    });
  } catch (e) {}
}

async function updateVoices() {
  const langLabel = $('target-lang').value;
  const langCode = CONFIG.target_langs[langLabel] || 'vi';
  const short = langCode.split('-')[0];
  try {
    const data = await fetchJSON('/api/voices?lang=' + encodeURIComponent(short));
    const list = $('voices-list');
    list.innerHTML = '';
    data.voices.forEach(v => {
      const o = document.createElement('option');
      o.value = v.label;
      list.appendChild(o);
    });
    if (data.voices.length > 0) $('voice-role').value = data.voices[0].label;
  } catch (e) {}
}

$('target-lang').addEventListener('change', updateVoices);

$('video').addEventListener('change', (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const p = $('video-preview');
  p.src = URL.createObjectURL(f);
  p.classList.remove('hidden');
});

// Slider live display
['voice-rate', 'volume', 'pitch'].forEach(id => {
  const el = $(id);
  const lbl = $(id + '-val');
  const unit = id === 'pitch' ? 'Hz' : '%';
  const upd = () => {
    const v = parseInt(el.value);
    lbl.textContent = (v >= 0 ? '+' : '') + v + unit;
  };
  el.addEventListener('input', upd); upd();
});

$('btn-start').addEventListener('click', async () => {
  const f = $('video').files[0];
  if (!f) { $('start-msg').textContent = '❌ Chưa chọn video.'; return; }
  const fd = new FormData();
  fd.append('video', f);
  if ($('ref-upload').files[0]) fd.append('ref_upload', $('ref-upload').files[0]);
  if ($('translated-srt').files[0]) fd.append('translated_srt', $('translated-srt').files[0]);
  if ($('reference-script').files[0]) fd.append('reference_script', $('reference-script').files[0]);
  fd.append('stt_channel_label', $('stt-channel').value);
  fd.append('translator_label', $('translator').value);
  fd.append('context_text', $('context-text').value);
  fd.append('openrouter_model', $('openrouter-model').value);
  fd.append('target_label', $('target-lang').value);
  fd.append('tts_label', $('tts').value);
  fd.append('auto_detect', $('auto-detect').value);
  fd.append('manual_source', $('manual-source').value);
  fd.append('ref_text', $('ref-text').value);
  fd.append('voice_role', $('voice-role').value);
  fd.append('voice_rate', $('voice-rate').value);
  fd.append('volume', $('volume').value);
  fd.append('pitch', $('pitch').value);
  fd.append('voice_autorate', $('voice-autorate').checked ? '1' : '0');
  fd.append('save_drive', $('save-drive').checked ? '1' : '0');

  $('btn-start').disabled = true;
  $('start-msg').textContent = '⏳ Đang upload video...';
  try {
    const r = await fetchJSON('/api/start', { method: 'POST', body: fd });
    $('start-msg').textContent = r.message || '🚀 Đã bắt đầu.';
  } catch (e) {
    $('start-msg').textContent = '❌ ' + e.message;
  } finally {
    $('btn-start').disabled = false;
  }
});

async function poll() {
  try {
    const s = await fetchJSON('/api/state');
    const status = s.status || 'idle';
    const map = {
      idle:    ['#f1f5f9', '#475569', '● Sẵn sàng'],
      running: ['#dbeafe', '#1d4ed8', '● Đang chạy'],
      done:    ['#dcfce7', '#15803d', '● Hoàn thành'],
      error:   ['#fee2e2', '#b91c1c', '● Lỗi'],
    };
    const [bg, fg, txt] = map[status] || map.idle;
    const badge = $('status-badge');
    badge.style.background = bg; badge.style.color = fg; badge.textContent = txt;
    $('status-msg').textContent = s.message || '';
    $('elapsed').textContent = s.elapsed ? ('• ⏱ ' + s.elapsed) : '';
    if (s.log) {
      const logEl = $('log');
      const atBottom = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 50;
      logEl.textContent = s.log;
      if (atBottom) logEl.scrollTop = logEl.scrollHeight;
    }
    if (status === 'done' && s.result) {
      const r = s.result;
      $('results-card').classList.remove('hidden');
      if (r.final_video) {
        const url = '/api/download?path=' + encodeURIComponent(r.final_video);
        $('result-video').src = url;
        $('dl-video').href = url;
      }
      if (r.src_srt) $('dl-src-srt').href = '/api/download?path=' + encodeURIComponent(r.src_srt);
      if (r.tgt_srt) $('dl-tgt-srt').href = '/api/download?path=' + encodeURIComponent(r.tgt_srt);
      if (r.audio)   $('dl-audio').href   = '/api/download?path=' + encodeURIComponent(r.audio);
    }
  } catch (e) { /* connection dropped — poll will retry */ }
}

// API keys modal
$('btn-keys').addEventListener('click', () => {
  const m = $('keys-modal');
  m.classList.remove('hidden');
  m.style.display = 'flex';
});
$('btn-keys-close').addEventListener('click', () => {
  const m = $('keys-modal');
  m.classList.add('hidden');
  m.style.display = '';
});
$('btn-keys-save').addEventListener('click', async () => {
  const payload = {};
  CONFIG.api_key_fields.forEach(f => {
    const env = f[0];
    const val = $('key-' + env).value.trim();
    // Don't overwrite masked values
    if (val && !val.startsWith('••••')) payload[env] = val;
  });
  $('keys-msg').textContent = '⏳ Đang lưu...';
  try {
    const r = await fetchJSON('/api/keys', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    $('keys-msg').textContent = r.message;
  } catch (e) {
    $('keys-msg').textContent = '❌ ' + e.message;
  }
});

// Translation context presets
const CTX_PRESETS = {
  onepiece:
    'Đây là một tập One Piece (anime shonen phiêu lưu của Eiichiro Oda).\n' +
    'Nhân vật chính: Monkey D. Luffy (thuyền trưởng Mũ Rơm, năng nổ, ngây thơ), Roronoa Zoro (kiếm sĩ ba kiếm), Nami (hoa tiêu, thông minh, hám tiền), Usopp (bắn tỉa, nhát gan), Sanji (đầu bếp), Tony Tony Chopper (y sĩ tuần lộc), Nico Robin (khảo cổ học), Franky (thợ máy), Brook (nhạc sĩ xương).\n' +
    'Phong cách: shonen anime, nhiệt huyết, có yếu tố hài, câu thoại ngắn gọn, kêu tên chiêu thức to rõ.\n' +
    'Thuật ngữ cần giữ nguyên (không dịch): Haki, Devil Fruit / Akuma no Mi, Grand Line, New World, Yonko, Shichibukai, Marine, Nakama, Berry (đơn vị tiền), Gomu Gomu no Mi, Gear Second, Gear Third, Gear Fourth, Gear Fifth.',
  docu:
    'Đây là một video tài liệu / phim tài liệu (documentary).\n' +
    'Phong cách: trang trọng, khách quan, câu văn hoàn chỉnh, sử dụng thuật ngữ chính xác.\n' +
    'Giữ nguyên tên riêng (người, địa điểm, tổ chức, thương hiệu) bằng tiếng Anh. Với thuật ngữ khoa học, dùng từ Việt phổ thông nếu có, kèm chú thích tiếng Anh trong ngoặc lần đầu xuất hiện.',
};
$('btn-context-preset-onepiece').addEventListener('click', () => {
  $('context-text').value = CTX_PRESETS.onepiece;
});
$('btn-context-preset-docu').addEventListener('click', () => {
  $('context-text').value = CTX_PRESETS.docu;
});
$('btn-context-clear').addEventListener('click', () => {
  $('context-text').value = '';
  $('reference-script').value = '';
});

$('btn-clear-log').addEventListener('click', async () => {
  try {
    await fetchJSON('/api/log/clear', { method: 'POST' });
    $('log').textContent = '';
  } catch (e) {}
});

// Bootstrap — load config then start polling every 2s
loadConfig().then(() => {
  poll();
  setInterval(poll, 2000);
}).catch(e => {
  $('start-msg').textContent = '❌ Không load được config: ' + e.message;
});
</script>
</body>
</html>
"""


@app.get('/')
def index():
    return HTMLResponse(HTML_PAGE)

@app.get('/api/config')
def api_config():
    return {
        'stt_channels': list(STT_CHANNELS.keys()),
        'stt_default': DEFAULT_STT_LABEL,
        'translators': [{'label': k, 'code': v[0], 'provider': v[1]} for k, v in TRANSLATORS.items()],
        'openrouter_models': OPENROUTER_FREE_MODELS,
        'tts_types': TTS_TYPES,
        'target_langs': TARGET_LANGS,
        'api_key_fields': API_KEY_FIELDS,
    }

@app.get('/api/voices')
def api_voices(lang: str = 'vi'):
    return {'voices': _voices_for_short(lang)}

@app.get('/api/state')
def api_state():
    s = _read_state()
    if s.get('status') == 'running' and s.get('started_at'):
        s['elapsed'] = _fmt_elapsed(time.time() - s['started_at'])
    s['log'] = _read_log()
    return s

@app.post('/api/start')
async def api_start(
    video: UploadFile = File(...),
    ref_upload: UploadFile = File(None),
    translated_srt: UploadFile = File(None),
    reference_script: UploadFile = File(None),
    stt_channel_label: str = Form(...),
    translator_label: str = Form(...),
    openrouter_model: str = Form(''),
    target_label: str = Form(...),
    tts_label: str = Form(...),
    auto_detect: str = Form('true'),
    manual_source: str = Form('en'),
    ref_text: str = Form(''),
    voice_role: str = Form(''),
    voice_rate: str = Form('0'),
    volume: str = Form('0'),
    pitch: str = Form('0'),
    voice_autorate: str = Form('1'),
    save_drive: str = Form('1'),
    context_text: str = Form(''),
):
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return {'ok': False, 'message': '⚠️ Đã có 1 job đang chạy.'}

        upload_dir = '/content/input'
        os.makedirs(upload_dir, exist_ok=True)

        def _save(upload, prefix):
            if upload is None or not upload.filename:
                return None
            safe = re.sub(r'[^\w\-.]', '_', os.path.basename(upload.filename))
            p = f'{upload_dir}/{prefix}_{safe}'
            with open(p, 'wb') as f:
                f.write(upload.file.read())
            return p

        video_path = _save(video, 'video')
        ref_upload_path = _save(ref_upload, 'ref')
        translated_srt_path = _save(translated_srt, 'srt')
        reference_script_path = _save(reference_script, 'refscript')

        reference_text = ''
        if reference_script_path:
            try:
                reference_text = Path(reference_script_path).read_text(encoding='utf-8', errors='ignore')
                if len(reference_text) > 60000:
                    reference_text = reference_text[:60000] + '\n...[truncated — reference too long]'
            except Exception:
                reference_text = ''

        tcode, provider = TRANSLATORS.get(translator_label, (0, None))
        # Edge-TTS requires the DISPLAY NAME (e.g. "HoaiMy(Female/VN)") not the
        # voice ID (e.g. "vi-VN-HoaiMyNeural"). pyvideotrans' get_edge_rolelist()
        # looks up display_name → voice_id via edge_tts.json.
        # Our datalist format is "DisplayName — voiceId", so extract the LEFT part.
        voice_id = voice_role.rsplit(' — ', 1)[0].strip() if ' — ' in voice_role else voice_role

        stt_recogn_type, stt_model_name, _stt_key_env = STT_CHANNELS.get(
            stt_channel_label, STT_CHANNELS[DEFAULT_STT_LABEL])

        params = {
            'video_path': video_path,
            'stt_recogn_type': stt_recogn_type,
            'stt_model': stt_model_name,
            'translator_code': tcode,
            'provider_hint': provider,
            'openrouter_model': openrouter_model,
            'target_code': TARGET_LANGS.get(target_label, 'vi'),
            'tts_code': TTS_TYPES.get(tts_label, 0),
            'auto_detect': auto_detect == 'true',
            'manual_source': manual_source,
            'ref_upload': ref_upload_path,
            'ref_text': ref_text,
            'voice_autorate': voice_autorate == '1',
            'save_drive': save_drive == '1',
            'translated_srt': translated_srt_path,
            'voice_id': voice_id,
            'voice_rate': voice_rate,
            'volume': volume,
            'pitch': pitch,
            'context_text': context_text,
            'reference_text': reference_text,
        }
        _worker_thread = threading.Thread(target=_worker, args=(params,), daemon=True)
        _worker_thread.start()
        return {'ok': True, 'message': '🚀 Đã bắt đầu. Job chạy ngầm — đóng tab/reload vẫn OK.'}

@app.get('/api/keys')
def api_get_keys():
    keys = _load_api_keys()
    # Return masked values (show last 4 chars only) so user sees which keys are saved.
    return {k: (('••••' + v[-4:]) if v and len(v) > 4 else '') for k, v in keys.items()}

@app.post('/api/keys')
async def api_save_keys(request: Request):
    data = await request.json()
    msg = _save_api_keys(**data)
    return {'message': msg}

@app.get('/api/download')
def api_download(path: str):
    p = Path(path).resolve()
    # Security: only allow files under REPO/output or /content/input or /content/drive
    allowed_roots = [
        Path(f'{REPO}/output').resolve(),
        Path('/content/input').resolve(),
        Path('/content/drive').resolve(),
    ]
    if not any(str(p).startswith(str(root)) for root in allowed_roots):
        raise HTTPException(403, 'Forbidden path')
    if not p.exists():
        raise HTTPException(404, 'Not found')
    return FileResponse(str(p), filename=p.name)

@app.post('/api/log/clear')
def api_log_clear():
    try:
        Path(LOG_FILE).write_text('', encoding='utf-8')
    except Exception:
        pass
    return {'ok': True}


# ===================== LAUNCH =====================

def _run_server():
    uvicorn.run(app, host='0.0.0.0', port=7865,
                log_level='warning', access_log=False)

_server_thread = threading.Thread(target=_run_server, daemon=True)
_server_thread.start()
time.sleep(2)  # wait for uvicorn to bind

print('\n' + '=' * 60)
print('✅ pyVideoTrans Studio (FastAPI) đang chạy trên :7865')
print('   — Plain HTTP + polling → KHÔNG bao giờ "Connection lost"')
print('=' * 60)

try:
    from google.colab import output as _colab_output
    _colab_output.serve_kernel_port_as_window(7865)
except Exception as _e:
    print(f'(Không phải Colab: {_e}) → mở http://localhost:7865')
