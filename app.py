"""
ClipAI — Interface Web
Flask app com dashboard, queue de vídeos, gestão de canais e definições.
"""

import os
import sys
import logging

# Garantir que o venv correto é usado
VENV_PYTHON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "Scripts", "python.exe")
if os.path.exists(VENV_PYTHON) and os.path.abspath(sys.executable).lower() != os.path.abspath(VENV_PYTHON).lower():
    print(f"⚠️  A relançar com o Python do venv: {VENV_PYTHON}")
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import json
import subprocess
import shutil
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify, send_from_directory

import database as db
from worker import worker

app = Flask(__name__, static_folder="static", template_folder="templates")


def _silenciar_logs_http():
    """Silencia logs de acesso HTTP do servidor de desenvolvimento Flask/Werkzeug."""
    werkzeug_log = logging.getLogger("werkzeug")
    werkzeug_log.setLevel(logging.ERROR)
    werkzeug_log.disabled = True
    app.logger.setLevel(logging.ERROR)


def _parse_upload_date(date_str):
    if not date_str:
        return None
    try:
        dt = datetime.strptime(str(date_str), "%Y%m%d").replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _current_clip_status_for_video(source_video_id):
    queue = db.get_queue()
    matched = [q for q in queue if q.get("source_video_id") == source_video_id]
    if any(q.get("status") == "done" for q in matched):
        return "done"
    if any(q.get("status") == "error" for q in matched):
        return "error"
    if any(q.get("status") in ("queued", "downloading", "analyzing", "editing") for q in matched):
        return "queued"

    recents = db.get_recent_source_videos()
    for r in recents:
        if r.get("source_video_id") == source_video_id:
            return r.get("clip_status") or "not_clipped"
    return "not_clipped"


import re


def _normalize_channel_url(url):
    """Normaliza uma URL de canal YouTube para o formato /videos.
    Aceita formatos:
      https://youtube.com/@handle?si=xxx
      https://www.youtube.com/channel/UCxxx
      https://www.youtube.com/@handle/shorts
    Retorna: URL limpa terminando em /videos
    """
    if not url:
        return url
    # Remove tracking params (?si=..., &feature=..., etc.)
    url = re.split(r'[?&]', url)[0].rstrip('/')
    # Se já termina em /videos, /streams ou /shorts, substituir pelo /videos
    url = re.sub(r'/(videos|shorts|streams|featured|playlists|community|about)$', '', url)
    return url + '/videos'


def _extract_channel_thumbnail(channel_url):
    """Extrai a foto do canal a partir da URL.
    Retorna a URL da thumbnail ou string vazia.
    """
    if not channel_url:
        return ""
    
    try:
        # Tenta extrair o handle ou channel ID
        # @handle format: https://youtube.com/@handle
        handle_match = re.search(r'/@([^/?]+)', channel_url)
        if handle_match:
            handle = handle_match.group(1)
            # Thumbnail baseada no handle (pode não funcionar sempre)
            return f"https://www.youtube.com/ytimg/www_unauthenticated/img/emotes/emotes_placeholder.png"
        
        # Channel ID format: https://www.youtube.com/channel/UCxxxxx
        channel_match = re.search(r'/channel/([A-Za-z0-9_-]+)', channel_url)
        if channel_match:
            channel_id = channel_match.group(1)
            # Usar o channel ID para construir uma URL de thumbnail
            # YouTube torna disponível: https://yt4.ggpht.com/[channel_id]
            # Mas a forma mais comum é sem thumbnail direto
            # Fallback vazio - a UI usa o ícone do YouTube
            return ""
        
        return ""
    except Exception:
        return ""


def _yt_extract_flat(source_url, max_entries=10):
    """Extração rápida (flat) da lista de vídeos de um canal."""
    try:
        import yt_dlp
    except ImportError:
        return []
    # Normaliza a URL para garantir que aponta para /videos
    source_url = _normalize_channel_url(source_url)
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "playlistend": max_entries,
        "ignoreerrors": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source_url, download=False)
        return (info or {}).get("entries") or []
    except Exception:
        return []


def _yt_video_info(video_id):
    """Busca metadados completos de um vídeo individual."""
    try:
        import yt_dlp
    except ImportError:
        return {}
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "ignoreerrors": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False
            ) or {}
    except Exception:
        return {}


def _resolve_upload_dt(entry):
    """Obtém datetime de publicação de um entry flat (sem chamada extra)."""
    # upload_date (YYYYMMDD string)
    dt = _parse_upload_date(entry.get("upload_date"))
    if dt:
        return dt
    # Unix timestamp seconds
    for key in ("timestamp", "release_timestamp"):
        ts = entry.get(key)
        if ts:
            try:
                return datetime.fromtimestamp(int(ts), tz=timezone.utc)
            except Exception:
                pass
    return None


def _scan_followed_channel(follow_item):
    try:
        import yt_dlp  # noqa — just to check presence
    except ImportError:
        return {"ok": False, "error": "yt-dlp não instalado"}

    max_age_days = int(follow_item.get("max_age_days", 7))
    target_channel_id = follow_item.get("target_channel_id")
    now_utc = datetime.now(timezone.utc)
    cutoff_dt = now_utc - timedelta(days=max_age_days)

    # ── Fase 1: listagem rápida (flat) ──────────────────────────────────
    flat_entries = _yt_extract_flat(follow_item.get("source_url"), max_entries=10)

    enqueued = 0
    scanned = 0

    for entry in flat_entries:
        if not entry:
            continue

        source_video_id = entry.get("id") or ""
        # IDs do YouTube têm sempre 11 caracteres
        if len(source_video_id) != 11:
            continue

        title = (entry.get("title") or "").strip() or f"Vídeo {source_video_id}"
        video_url = f"https://www.youtube.com/watch?v={source_video_id}"

        # ── Tenta obter data de publicação ─────────────────────────────
        upload_dt = _resolve_upload_dt(entry)

        # Se a data não estiver no entry flat, busca metadados individuais
        if upload_dt is None:
            full = _yt_video_info(source_video_id)
            upload_dt = _parse_upload_date(full.get("upload_date"))
            if not upload_dt:
                for key in ("timestamp", "release_timestamp"):
                    ts = full.get(key)
                    if ts:
                        try:
                            upload_dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                            break
                        except Exception:
                            pass
            # Aproveita título do full se o flat estava vazio
            if full.get("title") and title == f"Vídeo {source_video_id}":
                title = full["title"]

        age_days = None
        too_old = False
        if upload_dt:
            age_days = (now_utc - upload_dt).days
            too_old = upload_dt < cutoff_dt

        status = _current_clip_status_for_video(source_video_id)

        if not too_old and status == "not_clipped":
            db.add_to_queue_with_meta(
                url=video_url,
                title=title,
                channel_id=target_channel_id,
                source_video_id=source_video_id,
                source_channel_name=follow_item.get("name", ""),
            )
            status = "queued"
            enqueued += 1

        db.upsert_recent_source_video({
            "id": f"{follow_item['id']}_{source_video_id}",
            "follow_id": follow_item["id"],
            "follow_name": follow_item.get("name", ""),
            "source_video_id": source_video_id,
            "title": title,
            "video_url": video_url,
            "published_at": upload_dt.isoformat() if upload_dt else None,
            "age_days": age_days,
            "max_age_days": max_age_days,
            "destination_channel_id": target_channel_id,
            "clip_status": status,
            "scanned_at": now_utc.isoformat(),
        })
        scanned += 1

    db.update_followed_channel(follow_item["id"], last_scan_at=now_utc.isoformat())
    return {"ok": True, "scanned": scanned, "enqueued": enqueued}


# ═══════════════════════════════════════════════
#  PÁGINAS
# ═══════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


# ═══════════════════════════════════════════════
#  API — QUEUE
# ═══════════════════════════════════════════════

@app.route("/api/queue", methods=["GET"])
def api_get_queue():
    return jsonify(db.get_queue())


@app.route("/api/queue", methods=["POST"])
def api_add_to_queue():
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL é obrigatória"}), 400
    item = db.add_to_queue(
        url=url,
        title=data.get("title", ""),
        channel_id=data.get("channel_id"),
        priority=data.get("priority", 0),
        auto_publish=data.get("auto_publish"),
    )
    return jsonify(item), 201


@app.route("/api/queue/clear", methods=["DELETE"])
def api_clear_queue():
    """Remove todos os vídeos da queue."""
    queue = db.get_queue()
    for item in queue:
        db.remove_from_queue(item["id"])
    return jsonify({"ok": True, "cleared": len(queue)})


@app.route("/api/queue/<item_id>", methods=["DELETE"])
def api_remove_from_queue(item_id):
    db.remove_from_queue(item_id)
    return jsonify({"ok": True})


@app.route("/api/queue/<item_id>", methods=["PATCH"])
def api_update_queue_item(item_id):
    data = request.json or {}
    item = db.update_queue_item(item_id, **data)
    if item:
        return jsonify(item)
    return jsonify({"error": "Item não encontrado"}), 404


@app.route("/api/queue/reorder", methods=["POST"])
def api_reorder_queue():
    data = request.json or {}
    ids = data.get("order", [])
    new_queue = db.reorder_queue(ids)
    return jsonify(new_queue)


@app.route("/api/queue/current", methods=["GET"])
def api_current_processing():
    item = db.get_current_processing()
    return jsonify(item or {})


# ═══════════════════════════════════════════════
#  API — WORKER
# ═══════════════════════════════════════════════

@app.route("/api/worker/status", methods=["GET"])
def api_worker_status():
    return jsonify({
        "running": worker.is_running,
        "paused": worker.is_paused,
    })


@app.route("/api/worker/start", methods=["POST"])
def api_worker_start():
    worker.start()
    return jsonify({"running": True})


@app.route("/api/worker/stop", methods=["POST"])
def api_worker_stop():
    worker.stop()
    return jsonify({"running": False})


@app.route("/api/worker/pause", methods=["POST"])
def api_worker_pause():
    worker.pause()
    return jsonify({"paused": True})


@app.route("/api/worker/resume", methods=["POST"])
def api_worker_resume():
    worker.resume()
    return jsonify({"paused": False})


# ═══════════════════════════════════════════════
#  API — CANAIS
# ═══════════════════════════════════════════════

@app.route("/api/channels", methods=["GET"])
def api_get_channels():
    return jsonify(db.get_channels())


@app.route("/api/channels", methods=["POST"])
def api_add_channel():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Nome é obrigatório"}), 400
    channel_url = data.get("channel_url", "").strip()
    ch = db.add_channel(
        name=name,
        channel_url=channel_url,
        credentials_path=data.get("credentials_path", ""),
        description=data.get("description", ""),
    )
    
    # Tenta extrair a thumbnail do canal
    if channel_url:
        thumbnail = _extract_channel_thumbnail(channel_url)
        if thumbnail:
            ch = db.update_channel(ch["id"], channel_thumbnail=thumbnail)
    
    return jsonify(ch), 201


@app.route("/api/channels/<channel_id>", methods=["PATCH"])
def api_update_channel(channel_id):
    data = request.json or {}
    ch = db.update_channel(channel_id, **data)
    if ch:
        return jsonify(ch)
    return jsonify({"error": "Canal não encontrado"}), 404


@app.route("/api/channels/<channel_id>", methods=["DELETE"])
def api_delete_channel(channel_id):
    db.remove_channel(channel_id)
    return jsonify({"ok": True})


@app.route("/api/channels/<channel_id>/test-publish", methods=["POST"])
def api_test_channel_publish(channel_id):
    """Testa se é possível publicar vídeos no canal."""
    channel = None
    for ch in db.get_channels():
        if ch["id"] == channel_id:
            channel = ch
            break
    
    if not channel:
        return jsonify({"error": "Canal não encontrado"}), 404
    
    # Verifica se temcredenciais
    creds_path = channel.get("credentials_path", "").strip()
    if not creds_path:
        return jsonify({
            "success": False,
            "error": "Canal não tem credenciais configuradas",
            "message": "Configura o caminho para client_secrets.json"
        }), 400
    
    # Verifica se o ficheiro de credenciais existe
    if not os.path.exists(creds_path):
        return jsonify({
            "success": False,
            "error": "Ficheiro de credenciais não encontrado",
            "message": f"Verifica o caminho: {creds_path}"
        }), 400
    
    try:
        # Tenta fazer um teste simples de autenticação
        # (sem tentar fazer upload efetivo)
        import json
        with open(creds_path, 'r') as f:
            creds_data = json.load(f)
        
        if not creds_data or 'client_id' not in creds_data:
            return jsonify({
                "success": False,
                "error": "Ficheiro de credenciais inválido ou corrompido"
            }), 400
        
        # Se conseguiu ler as credenciais, o teste passou
        return jsonify({
            "success": True,
            "message": f"Canal '{channel['name']}' pronto para publicação!",
            "client_id": creds_data.get('client_id', '')[:20] + '...'
        }), 200
    except json.JSONDecodeError:
        return jsonify({
            "success": False,
            "error": "Ficheiro JSON inválido",
            "message": "Verifica o formato do ficheiro client_secrets.json"
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Erro no teste: {str(e)}"
        }), 500


# ═══════════════════════════════════════════════
#  API — CANAIS A SEGUIR (FONTE)
# ═══════════════════════════════════════════════

@app.route("/api/followed-channels", methods=["GET"])
def api_get_followed_channels():
    return jsonify(db.get_followed_channels())


@app.route("/api/followed-channels", methods=["POST"])
def api_add_followed_channel():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    source_url = (data.get("source_url") or "").strip()
    if not name or not source_url:
        return jsonify({"error": "Nome e URL do canal fonte são obrigatórios"}), 400
    item = db.add_followed_channel(
        name=name,
        source_url=source_url,
        max_age_days=int(data.get("max_age_days", 7)),
        target_channel_id=data.get("target_channel_id"),
        active=bool(data.get("active", True)),
    )
    return jsonify(item), 201


@app.route("/api/followed-channels/<follow_id>", methods=["PATCH"])
def api_update_followed_channel(follow_id):
    data = request.json or {}
    item = db.update_followed_channel(follow_id, **data)
    if item:
        return jsonify(item)
    return jsonify({"error": "Canal a seguir não encontrado"}), 404


@app.route("/api/followed-channels/<follow_id>", methods=["DELETE"])
def api_delete_followed_channel(follow_id):
    db.remove_followed_channel(follow_id)
    return jsonify({"ok": True})


@app.route("/api/followed-channels/<follow_id>/scan", methods=["POST"])
def api_scan_followed_channel(follow_id):
    item = None
    for f in db.get_followed_channels():
        if f.get("id") == follow_id:
            item = f
            break
    if not item:
        return jsonify({"error": "Canal a seguir não encontrado"}), 404
    result = _scan_followed_channel(item)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@app.route("/api/followed-channels/scan-all", methods=["POST"])
def api_scan_all_followed_channels():
    results = []
    for item in db.get_followed_channels():
        if not item.get("active", True):
            continue
        results.append({"follow_id": item.get("id"), **_scan_followed_channel(item)})
    return jsonify(results)


@app.route("/api/followed-channels/<follow_id>/videos", methods=["GET"])
def api_get_followed_channel_videos(follow_id):
    videos = db.get_recent_source_videos(follow_id)
    videos = sorted(videos, key=lambda x: x.get("published_at") or "", reverse=True)
    return jsonify(videos)


# ═══════════════════════════════════════════════
#  API — VÍDEOS PUBLICADOS
# ═══════════════════════════════════════════════

@app.route("/api/posted", methods=["GET"])
def api_get_posted():
    return jsonify(db.get_posted_videos())


@app.route("/api/posted", methods=["POST"])
def api_add_posted():
    data = request.json or {}
    v = db.add_posted_video(
        clip_path=data.get("clip_path", ""),
        title=data.get("title", ""),
        channel_id=data.get("channel_id", ""),
        youtube_url=data.get("youtube_url", ""),
        thumbnail=data.get("thumbnail", ""),
    )
    return jsonify(v), 201


@app.route("/api/posted/<video_id>", methods=["DELETE"])
def api_delete_posted(video_id):
    ok = db.remove_posted_video(video_id)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"error": "Vídeo não encontrado"}), 404


@app.route("/api/posted/<video_id>", methods=["PATCH"])
def api_update_posted(video_id):
    data = request.json or {}
    v = db.update_posted_video(video_id, **data)
    if v:
        return jsonify(v)
    return jsonify({"error": "Vídeo não encontrado"}), 404


# ═══════════════════════════════════════════════
#  API — CLIPS PARA REVISÃO
# ═══════════════════════════════════════════════

@app.route("/api/review", methods=["GET"])
def api_get_review_clips():
    clips = db.get_review_clips()
    # Enrich with source video info from queue
    queue_map = {q["id"]: q for q in db.get_queue()}
    for clip in clips:
        q = queue_map.get(clip.get("queue_id"))
        if q:
            clip["source_url"]          = q.get("url", "")
            clip["source_title"]        = q.get("title", "")
            clip["source_channel_name"] = q.get("source_channel_name", "")
        else:
            clip["source_url"]          = ""
            clip["source_title"]        = ""
            clip["source_channel_name"] = ""
    return jsonify(clips)


@app.route("/api/review/<clip_id>", methods=["PATCH"])
def api_update_review_clip(clip_id):
    data = request.json or {}
    clip = db.update_review_clip(clip_id, **data)
    if clip:
        return jsonify(clip)
    return jsonify({"error": "Clip não encontrado"}), 404


@app.route("/api/review/<clip_id>/publish", methods=["POST"])
def api_publish_review_clip(clip_id):
    data = request.json or {}
    result = db.publish_review_clip(clip_id, data.get("channel_id"))
    if result:
        return jsonify(result)
    return jsonify({"error": "Não foi possível publicar (falta canal?)"}), 400


@app.route("/api/review/<clip_id>", methods=["DELETE"])
def api_reject_review_clip(clip_id):
    clip = db.reject_review_clip(clip_id)
    if clip:
        return jsonify(clip)
    return jsonify({"error": "Clip não encontrado"}), 404


# ═══════════════════════════════════════════════
#  API — DEFINIÇÕES
# ═══════════════════════════════════════════════

@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    return jsonify(db.get_settings())


@app.route("/api/settings", methods=["PATCH"])
def api_update_settings():
    data = request.json or {}
    s = db.update_settings(**data)
    return jsonify(s)


# ═══════════════════════════════════════════════
#  API — VERIFICAÇÕES DO SISTEMA
# ═══════════════════════════════════════════════

@app.route("/api/system/check", methods=["GET"])
def api_system_check():
    """Verifica todos os requisitos do sistema."""
    checks = {}

    # 1. FFmpeg
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
        version_line = r.stdout.split("\n")[0] if r.stdout else "Instalado"
        checks["ffmpeg"] = {"ok": True, "detail": version_line}
    except Exception:
        checks["ffmpeg"] = {"ok": False, "detail": "FFmpeg não encontrado. Instale em https://ffmpeg.org"}

    # 2. FFprobe
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=10)
        checks["ffprobe"] = {"ok": True, "detail": "Instalado"}
    except Exception:
        checks["ffprobe"] = {"ok": False, "detail": "FFprobe não encontrado"}

    # 3. Ollama
    try:
        import ollama as _ol
        models = _ol.list()
        model_names = []
        # ollama.list() returns an object with a 'models' attribute
        if hasattr(models, 'models'):
            model_names = [m.model for m in models.models]
        elif isinstance(models, dict):
            model_names = [m.get("name", "") for m in models.get("models", [])]
        checks["ollama"] = {"ok": True, "detail": f"A correr. Modelos: {', '.join(model_names) or 'nenhum'}"}
    except Exception as e:
        checks["ollama"] = {"ok": False, "detail": f"Ollama não está a correr: {e}"}

    # 4. GPU / CUDA
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            checks["gpu"] = {"ok": True, "detail": f"{gpu_name} ({vram:.1f} GB VRAM)"}
        else:
            checks["gpu"] = {"ok": False, "detail": "GPU CUDA não detectada. Vai usar CPU (mais lento)"}
    except ImportError:
        # Fallback: perguntar ao venv Python diretamente
        try:
            r = subprocess.run(
                [VENV_PYTHON, "-c",
                 "import torch; print(torch.cuda.is_available()); "
                 "print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"],
                capture_output=True, text=True, timeout=30
            )
            lines = r.stdout.strip().split("\n")
            if lines and lines[0].strip() == "True":
                gpu_name = lines[1].strip() if len(lines) > 1 else "GPU"
                checks["gpu"] = {"ok": True, "detail": f"{gpu_name} (via venv)"}
            else:
                checks["gpu"] = {"ok": False, "detail": "GPU CUDA não detectada no venv"}
        except Exception:
            checks["gpu"] = {"ok": False, "detail": "PyTorch não instalado ou sem suporte CUDA"}
    except Exception as e:
        checks["gpu"] = {"ok": False, "detail": f"Erro ao verificar GPU: {e}"}

    # 5. faster-whisper
    try:
        import faster_whisper
        checks["whisper"] = {"ok": True, "detail": "faster-whisper instalado"}
    except ImportError:
        checks["whisper"] = {"ok": False, "detail": "faster-whisper não instalado: pip install faster-whisper"}

    # 6. yt-dlp
    try:
        import yt_dlp
        checks["ytdlp"] = {"ok": True, "detail": f"yt-dlp v{yt_dlp.version.__version__}"}
    except ImportError:
        checks["ytdlp"] = {"ok": False, "detail": "yt-dlp não instalado: pip install yt-dlp"}

    # 7. Espaço em disco
    try:
        usage = shutil.disk_usage(".")
        free_gb = usage.free / 1024**3
        checks["disk"] = {"ok": free_gb > 5, "detail": f"{free_gb:.1f} GB livres"}
    except Exception:
        checks["disk"] = {"ok": True, "detail": "Não foi possível verificar"}

    return jsonify(checks)


@app.route("/api/system/ollama-models", methods=["GET"])
def api_ollama_models():
    """Lista modelos disponíveis no Ollama."""
    try:
        import ollama as _ol
        models = _ol.list()
        model_names = []
        if hasattr(models, 'models'):
            model_names = [m.model for m in models.models]
        elif isinstance(models, dict):
            model_names = [m.get("name", "") for m in models.get("models", [])]
        return jsonify({"ok": True, "models": model_names})
    except Exception as e:
        return jsonify({"ok": False, "models": [], "error": str(e)})


# ═══════════════════════════════════════════════
#  SERVIR CLIPS EDITADOS
# ═══════════════════════════════════════════════

@app.route("/clips/<path:filename>")
def serve_clip(filename):
    return send_from_directory("downloads/clips_editados", filename)


# ═══════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    os.makedirs("downloads/clips_editados", exist_ok=True)
    _silenciar_logs_http()
    print("\n🚀 ClipAI Interface em http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
