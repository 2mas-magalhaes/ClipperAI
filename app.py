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

# Configurar logging para aparecer no terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

import json
import subprocess
import shutil
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import uuid
import shutil as shell_utils

import database as db
from worker import worker

try:
    import proxy_rotator
    _HAS_PROXY = True
except ImportError:
    _HAS_PROXY = False

try:
    import credentials_rotation
    _HAS_CREDENTIALS_ROTATION = True
except ImportError:
    _HAS_CREDENTIALS_ROTATION = False

app = Flask(__name__, static_folder="static", template_folder="templates")

# Cache buster para forçar reload de JS/CSS em desenvolvimento
import time
CACHE_BUST = str(int(time.time()))


def _silenciar_logs_http():
    """Silencia logs de acesso HTTP do servidor de desenvolvimento Flask/Werkzeug."""
    werkzeug_log = logging.getLogger("werkzeug")
    werkzeug_log.setLevel(logging.ERROR)
    werkzeug_log.disabled = True
    app.logger.setLevel(logging.INFO)


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


def _extract_info_with_retries(ydl_opts, url, **kwargs):
    """
    Extrai info do YouTube com retry automático (máximo 3 tentativas).
    Se a URL está throttled/bloqueada, para após 3 tentativas em vez de ficar preso.
    Args:
        ydl_opts (dict): Opções do yt-dlp
        url (str): URL a extrair
        **kwargs: argumentos adicionais para extract_info
    Returns:
        dict ou None: informações extraídas, ou None se falhar em todas as tentativas
    """
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False, **kwargs) or {}
                return info
        except Exception as e:
            err_str = str(e).lower()
            # Se for erro de throttle/bot check, não vale a pena tentar novamente
            if "sign in" in err_str or "bot" in err_str or "429" in err_str or "403" in err_str:
                logging.warning(f"   ⚠️ YouTube throttle/bot check na tentativa {attempt}/{max_retries}: {str(e)[:100]}")
                if attempt >= max_retries:
                    logging.error(f"   ❌ Falha após {max_retries} tentativas - YouTube bloqueou acesso (bot check)")
                    return None
                time.sleep(2 ** attempt)  # exponential backoff: 2s, 4s, 8s
            else:
                # Outro erro, desistir logo
                logging.error(f"   ❌ Erro ao extrair {url}: {e}")
                return None
    return None


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
    """Extrai a foto do canal via yt-dlp (avatar real do YouTube)."""
    if not channel_url:
        return ""
    try:
        import yt_dlp
        clean_url = re.split(r'[?&]', channel_url)[0].rstrip('/')
        clean_url = re.sub(r'/(videos|shorts|streams|featured|playlists|community|about)$', '', clean_url)
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "playlistend": 1,
            "ignoreerrors": True,
            "no_warnings": True,
        }
        # Tenta sem /videos primeiro (funciona mesmo para canais sem vídeos)
        info = _extract_info_with_retries(ydl_opts, clean_url) or {}
        # yt-dlp devolve os thumbnails do canal no campo 'thumbnails'
        for t in reversed(info.get("thumbnails") or []):
            url = t.get("url", "")
            if url and ("yt3.ggpht" in url or "yt3.googleusercontent" in url or "yt4.ggpht" in url):
                return url
        # Fallback: channel avatar no campo uploader_url etc.
        for key in ("channel_thumbnail", "avatar", "thumbnail"):
            val = info.get(key)
            if val:
                return val
        return ""
    except Exception:
        return ""


def _resolve_local_channel_for_uploaded_video(expected_channel_id, youtube_channel_id="", youtube_channel_title=""):
    """Resolve o canal local (DB) a partir do canal real do vídeo no YouTube.

    Retorna (resolved_channel_id, reason). Se não conseguir mapear, devolve o canal esperado.
    """
    channels = db.get_channels() or []

    yt_id = (youtube_channel_id or "").strip()
    yt_title = (youtube_channel_title or "").strip().lower()

    if yt_id:
        for ch in channels:
            if (ch.get("youtube_channel_id") or "").strip() == yt_id:
                return ch.get("id") or expected_channel_id, "youtube_channel_id"

    if yt_title:
        for ch in channels:
            local_yt_name = (ch.get("youtube_channel_name") or "").strip().lower()
            local_name = (ch.get("name") or "").strip().lower()
            if yt_title and (yt_title == local_yt_name or yt_title == local_name):
                return ch.get("id") or expected_channel_id, "channel_name"

    return expected_channel_id, "expected"


def _get_youtube_service(credentials_path, token_path=None):
    """Cria um serviço YouTube autenticado via OAuth2.
    Retorna (service, logs) onde logs é uma lista de strings."""
    import google_auth_oauthlib.flow
    import google.oauth2.credentials
    from googleapiclient.discovery import build

    logs = []
    if not token_path:
        token_path = credentials_path.replace(".json", "_token.json")

    creds = None

    # Tenta carregar token existente
    if os.path.exists(token_path):
        try:
            creds = google.oauth2.credentials.Credentials.from_authorized_user_file(
                token_path,
                scopes=["https://www.googleapis.com/auth/youtube",
                         "https://www.googleapis.com/auth/youtube.upload"]
            )
            logs.append("Token OAuth existente encontrado")
        except Exception as e:
            logs.append(f"Token existente inválido: {e}")
            creds = None

    # Se o token expirou, tenta fazer refresh
    if creds and creds.expired and creds.refresh_token:
        try:
            import google.auth.transport.requests
            creds.refresh(google.auth.transport.requests.Request())
            logs.append("Token renovado com sucesso")
            with open(token_path, 'w') as f:
                f.write(creds.to_json())
        except Exception as e:
            logs.append(f"Falha ao renovar token: {e}")
            creds = None

    # Se não há creds válidas, precisa de fluxo OAuth
    if not creds or not creds.valid:
        logs.append("A iniciar fluxo de autenticação OAuth...")
        logs.append("AVISO: Se a app estiver em modo 'Testing' no Google Cloud,")
        logs.append("  adiciona o teu email como utilizador de teste primeiro!")
        try:
            # Permitir HTTP para localhost (necessário quando não há HTTPS)
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/youtube",
                         "https://www.googleapis.com/auth/youtube.upload"]
            )
            creds = flow.run_local_server(
                port=8090,
                prompt="consent",
                success_message="Autenticação concluída! Pode fechar esta janela.",
                open_browser=True,
            )
            logs.append("Autenticação OAuth concluída com sucesso!")
            # Guarda o token para futura utilização
            with open(token_path, 'w') as f:
                f.write(creds.to_json())
            logs.append(f"Token guardado em: {token_path}")
        except Exception as e:
            error_str = str(e)
            if "access_denied" in error_str.lower():
                logs.append("FALHOU: Acesso negado pelo Google (403: access_denied)")
                logs.append("")
                logs.append("→ A tua app Google Cloud está em modo 'Testing'.")
                logs.append("→ Precisas de adicionar o teu email como utilizador de teste:")
                logs.append("  1. Vai a https://console.cloud.google.com")
                logs.append("  2. Seleciona o projeto 'ClipAI'")
                logs.append("  3. Vai a 'APIs & Services' → 'OAuth consent screen'")
                logs.append("  4. Na secção 'Test users', clica em '+ Add Users'")
                logs.append("  5. Adiciona o teu email (ex: tomasmaga115@gmail.com)")
                logs.append("  6. Guarda e tenta novamente")
                logs.append("")
                logs.append("→ Alternativa: publica a app (muda de 'Testing' para 'In Production')")
            else:
                logs.append(f"FALHOU: Erro na autenticação OAuth: {e}")
            return None, logs

    # Cria o serviço YouTube
    try:
        service = build("youtube", "v3", credentials=creds)
        logs.append("Serviço YouTube API v3 criado com sucesso")
        return service, logs
    except Exception as e:
        logs.append(f"ERRO ao criar serviço YouTube: {e}")
        return None, logs


def _is_quota_exceeded_error(error):
    err_str = str(error or "")
    err_lower = err_str.lower()
    return (
        "quotaexceeded" in err_lower
        or "youtube.quota" in err_lower
        or "exceeded your" in err_lower and "quota" in err_lower
    )


def _upload_with_credential_rotation(
    fallback_credentials_path,
    video_path,
    title,
    description="",
    tags=None,
    category="22",
    privacy="private",
    publish_at=None,
):
    """Faz upload com rotação automática de credenciais quando quota esgota.
    PRIORIDADE: Usa sempre as credenciais do canal (fallback_credentials_path) primeiro.
    Só recorre à rotação de credenciais se as do canal falharem por quota.
    Retorna (video_id, url, service, logs, error_message, used_credentials_path)."""
    logs = []
    service = None
    attempted_credentials = set()
    last_error = None
    used_creds_path = None  # Rastreia qual credencial foi efetivamente usada

    # Construir lista ordenada de credenciais a tentar:
    # 1º — Credenciais do canal específico (prioridade absoluta)
    # 2º — Credenciais da rotação (fallback para quota), TODAS elas
    creds_queue = []

    # Canal primeiro
    if fallback_credentials_path and os.path.exists(fallback_credentials_path):
        creds_queue.append(fallback_credentials_path)

    # Depois credenciais da rotação (excluindo a do canal para não repetir, usar TODAS)
    if _HAS_CREDENTIALS_ROTATION:
        try:
            rotation_list = getattr(credentials_rotation, "CREDENTIALS_LIST", []) or []
            for rot_cred in rotation_list:
                if rot_cred and os.path.exists(rot_cred) and os.path.abspath(rot_cred) != os.path.abspath(fallback_credentials_path or ""):
                    creds_queue.append(rot_cred)
        except Exception:
            pass

    if not creds_queue:
        last_error = "Credenciais OAuth não encontradas"
        logs.append(f"FALHOU: {last_error}")
        return None, None, service, logs, last_error, None

    total_attempts = len(creds_queue)

    for attempt, creds_path in enumerate(creds_queue):
        if creds_path in attempted_credentials:
            continue
        attempted_credentials.add(creds_path)

        logs.append(f"Tentativa {attempt + 1}/{total_attempts} com: {os.path.basename(creds_path)}")
        service, auth_logs = _get_youtube_service(creds_path)
        logs.extend(auth_logs)
        if not service:
            last_error = "Falha na autenticação"
            continue

        try:
            video_id, url, upload_logs = _upload_video_to_youtube(
                service,
                video_path,
                title,
                description,
                tags,
                category=category,
                privacy=privacy,
                raise_on_quota=True,
                publish_at=publish_at,
            )
            logs.extend(upload_logs)
            if video_id:
                used_creds_path = creds_path  # Registar credencial que funcionou
                return video_id, url, service, logs, None, used_creds_path
            last_error = "Falha no upload"
            break
        except Exception as e:
            last_error = str(e)
            if _is_quota_exceeded_error(e):
                logs.append("Quota excedida nesta credencial")
                continue  # Tentar próxima credencial
            logs.append(f"FALHOU: {e}")
            break

    return None, None, service, logs, (last_error or "Falha no upload"), None


def _upload_video_to_youtube(service, video_path, title, description="", tags=None, category="22", privacy="private", raise_on_quota=False, publish_at=None):
    """Faz upload de um vídeo para o YouTube com retry automático em timeouts.
    
    Args:
        publish_at (datetime, optional): Quando fornecido, agenda o vídeocomo privado e define publishAt (ISO 8601 format).
    
    Retorna (video_id, url, logs)."""
    from googleapiclient.http import MediaFileUpload
    import logging
    import time
    
    logs = []

    if not os.path.exists(video_path):
        logs.append(f"ERRO: Ficheiro não encontrado: {video_path}")
        return None, None, logs

    file_size = os.path.getsize(video_path)
    logs.append(f"Ficheiro: {os.path.basename(video_path)} ({file_size / 1024 / 1024:.1f} MB)")

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags or [],
            "categoryId": category,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    
    # Adicionar agendamento se fornecido
    if publish_at:
        from datetime import datetime, timezone as _tz
        # Converter para ISO 8601 format em UTC
        if isinstance(publish_at, datetime):
            # YouTube API requer formato ISO 8601 em UTC
            if publish_at.tzinfo is None:
                # Naive datetime (hora local) → converter para UTC
                local_dt = publish_at.astimezone()  # attach local tz
                utc_dt = local_dt.astimezone(_tz.utc)
            else:
                utc_dt = publish_at.astimezone(_tz.utc)
            publish_at_str = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        else:
            publish_at_str = publish_at
        
        body["status"]["publishAt"] = publish_at_str
        logs.append(f"Agendado para: {publish_at_str}")

    logs.append(f"Título: {title[:100]}")
    logs.append(f"Privacidade: {privacy}")
    logs.append("A iniciar upload...")
    
    logging.info(f"📤 INICIANDO UPLOAD PARA YOUTUBE")
    logging.info(f"   Título: {title[:100]}")
    logging.info(f"   Tamanho: {file_size / 1024 / 1024:.1f} MB")
    logging.info(f"   Privacidade: {privacy}")
    if publish_at:
        logging.info(f"   📅 Agendamento: {body['status'].get('publishAt', 'N/A')}")

    try:
        media = MediaFileUpload(video_path, chunksize=1024 * 1024, resumable=True)
        req = service.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        last_logged_pct = 0
        chunk_retry_count = 0
        max_chunk_retries = 3
        
        while response is None:
            try:
                status, response = req.next_chunk()
                chunk_retry_count = 0  # Reset retry counter on success
                
                if status:
                    pct = int(status.progress() * 100)
                    # Log detalhado no terminal a cada 10%
                    if pct >= last_logged_pct + 10:
                        logging.info(f"   📤 Upload: {pct}% ({status.resumable_progress / 1024 / 1024:.1f} MB)")
                        last_logged_pct = pct
                    # Log simplificado para interface
                    logs.append(f"Upload: {pct}%")
                    
            except (TimeoutError, ConnectionError, OSError) as e:
                # Erros de rede/timeout — tentar novamente com backoff
                if chunk_retry_count < max_chunk_retries:
                    chunk_retry_count += 1
                    wait_time = 2 ** chunk_retry_count  # exponential backoff: 2s, 4s, 8s
                    logging.warning(f"⚠️ Erro temporário (tentativa {chunk_retry_count}/{max_chunk_retries}): {e}")
                    logging.warning(f"   A tentar novamente em {wait_time}s...")
                    logs.append(f"Erro temporário, retentando em {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Após 3 tentativas, desistir
                    logging.error(f"❌ Falha no upload após {max_chunk_retries} retentativas: {e}")
                    raise  # Re-raise para capturar no bloco externo

        video_id = response.get("id", "")
        url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
        logs.append(f"Upload concluído! ID: {video_id}")
        logs.append(f"URL: {url}")
        logging.info(f"✅ UPLOAD CONCLUÍDO!")
        logging.info(f"   ID: {video_id}")
        logging.info(f"   URL: {url}")
        return video_id, url, logs
    except Exception as e:
        if raise_on_quota and _is_quota_exceeded_error(e):
            raise
        logs.append(f"ERRO no upload: {e}")
        logging.error(f"❌ ERRO NO UPLOAD: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return None, None, logs


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
    return render_template("index.html", cache_bust=CACHE_BUST)


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


@app.route("/api/queue/upload", methods=["POST"])
def api_upload_local_video():
    """Upload de ficheiro de vídeo local para a queue."""
    try:
        # Validar ficheiro
        if 'file' not in request.files:
            return jsonify({"message": "Nenhum ficheiro selecionado"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"message": "Ficheiro vazio"}), 400
        
        # Validar tamanho (máximo 4GB)
        max_size = 4 * 1024 * 1024 * 1024
        file.seek(0, 2)  # Ir para o fim
        size = file.tell()
        file.seek(0)  # Voltar ao início
        
        if size > max_size:
            return jsonify({"message": f"Ficheiro muito grande ({size / (1024**3):.2f}GB, máximo 4GB)"}), 413
        
        # Criar diretório de uploads se não existir
        upload_dir = "downloads/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Gerar nome único para o ficheiro
        ext = os.path.splitext(secure_filename(file.filename))[1]
        unique_filename = f"uploaded_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(upload_dir, unique_filename)
        
        # Guardar ficheiro
        file.save(filepath)
        
        # Obter dados do formulário
        title = request.form.get('title', 'Vídeo Carregado').strip()
        channel_id = request.form.get('channel_id') or None
        auto_publish = request.form.get('auto_publish') == '1'
        
        # Dados originais do YouTube (se disponíveis)
        origin_title = request.form.get('origin_title', '').strip()
        origin_url = request.form.get('origin_url', '').strip()
        origin_channel_name = request.form.get('origin_channel_name', '').strip()
        origin_channel_url = request.form.get('origin_channel_url', '').strip()
        
        # Obter tamanho real do ficheiro guardado
        file_size = os.path.getsize(filepath)
        
        # Adicionar à queue como URL local (com prefixo especial)
        item = db.add_to_queue(
            url=f"local://{filepath}",
            title=title or os.path.splitext(file.filename)[0],
            channel_id=channel_id,
            auto_publish=auto_publish,
        )
        
        # Guardar dados originais no item (para usar na descrição depois)
        if origin_title or origin_url:
            # Atualizar o item com metadados originais
            item['origin_title'] = origin_title
            item['origin_url'] = origin_url
            item['origin_channel_name'] = origin_channel_name
            item['origin_channel_url'] = origin_channel_url
            db.update_queue_item(item['id'], 
                origin_title=origin_title,
                origin_url=origin_url,
                origin_channel_name=origin_channel_name,
                origin_channel_url=origin_channel_url
            )
        
        # Log
        logging.info(f"✅ Upload de vídeo: {unique_filename} ({file_size / (1024**2):.2f}MB) → {title}")
        if origin_title:
            logging.info(f"   Origem: {origin_title} ({origin_channel_name})")
        
        return jsonify({
            "message": "Vídeo enviado com sucesso",
            "item": item,
            "size": file_size,
        }), 201
        
    except Exception as e:
        logging.error(f"❌ Erro no upload: {e}")
        return jsonify({"message": f"Erro: {str(e)}"}), 500


@app.route("/api/queue/clear", methods=["DELETE"])
def api_clear_queue():
    """Remove todos os vídeos da queue."""
    queue = db.get_queue()
    for item in queue:
        db.remove_from_queue(item["id"])
    return jsonify({"ok": True, "cleared": len(queue)})


@app.route("/api/queue/bulk", methods=["POST"])
def api_bulk_queue():
    """Operações em massa na queue: alterar canal, visibilidade, auto-publish, apagar."""
    data = request.json or {}
    ids = data.get("ids", [])
    action = data.get("action", "")

    if not ids:
        return jsonify({"error": "Nenhum item selecionado"}), 400

    results = {"updated": 0, "deleted": 0, "errors": []}

    if action == "delete":
        for item_id in ids:
            try:
                db.remove_from_queue(item_id)
                results["deleted"] += 1
            except Exception as e:
                results["errors"].append(str(e))

    elif action == "set_channel":
        channel_id = data.get("channel_id")
        for item_id in ids:
            r = db.update_queue_item(item_id, channel_id=channel_id or None)
            if r:
                results["updated"] += 1

    elif action == "set_auto_publish":
        value = bool(data.get("auto_publish", data.get("value", False)))
        for item_id in ids:
            r = db.update_queue_item(item_id, auto_publish=value)
            if r:
                results["updated"] += 1

    elif action == "set_privacy":
        privacy = data.get("default_privacy", data.get("privacy", "private"))
        for item_id in ids:
            r = db.update_queue_item(item_id, default_privacy=privacy)
            if r:
                results["updated"] += 1

    elif action == "retry":
        for item_id in ids:
            r = db.update_queue_item(item_id, status="queued", progress=0, error_msg="", status_detail="")
            if r:
                results["updated"] += 1

    elif action == "interlace_channels":
        # Distribui os vídeos alternadamente entre os canais disponíveis
        channels = db.get_channels()
        if not channels:
            return jsonify({"error": "Nenhum canal disponível"}), 400
        
        # Intercala os canais: vídeo[0] -> canal[0], vídeo[1] -> canal[1], etc.
        for idx, item_id in enumerate(ids):
            channel_idx = idx % len(channels)
            channel_id = channels[channel_idx]["id"]
            r = db.update_queue_item(item_id, channel_id=channel_id)
            if r:
                results["updated"] += 1

    else:
        return jsonify({"error": f"Ação desconhecida: {action}"}), 400

    total = results["updated"] + results["deleted"]
    return jsonify({"ok": True, "message": f"{total} item(s) atualizados", **results})


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


@app.route("/api/queue/<item_id>/cancel", methods=["POST"])
def api_cancel_queue_item(item_id):
    """Cancela um vídeo que está sendo processado."""
    item = db.get_queue()
    found_item = None
    for q in item:
        if q["id"] == item_id:
            found_item = q
            break
    
    if not found_item:
        return jsonify({"error": "Item não encontrado"}), 404
    
    # Verifica se está em processamento
    status = found_item.get("status")
    if status not in ("downloading", "analyzing", "editing"):
        return jsonify({"error": f"Não é possível cancelar vídeo com status: {status}"}), 400
    
    # Marca para cancelamento
    worker.cancel(item_id)
    
    return jsonify({"ok": True, "message": "Cancelamento iniciado..."})


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
    
    # Extrai thumbnail e info do canal via yt-dlp (síncrono para devolver já)
    if channel_url:
        try:
            import yt_dlp
            clean_url = re.split(r'[?&]', channel_url)[0].rstrip('/')
            clean_url = re.sub(r'/(videos|shorts|streams|featured|playlists|community|about)$', '', clean_url)
            ydl_opts = {
                "quiet": True, "skip_download": True, "extract_flat": True,
                "playlistend": 1, "ignoreerrors": True, "no_warnings": True,
            }
            info = _extract_info_with_retries(ydl_opts, clean_url) or {}
            update_data = {}
            if info:
                for t in reversed(info.get("thumbnails") or []):
                    url = t.get("url", "")
                    if url and ("yt3.ggpht" in url or "yt3.googleusercontent" in url):
                        update_data["channel_thumbnail"] = url
                        break
                if info.get("channel"):
                    update_data["youtube_channel_name"] = info["channel"]
                if info.get("channel_id"):
                    update_data["youtube_channel_id"] = info["channel_id"]
                if info.get("channel_follower_count"):
                    update_data["youtube_subscribers"] = str(info["channel_follower_count"])
                if update_data:
                    ch = db.update_channel(ch["id"], **update_data)
        except Exception:
            pass

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
    """Testa se é possível publicar vídeos no canal — teste completo com logs."""
    channel = None
    for ch in db.get_channels():
        if ch["id"] == channel_id:
            channel = ch
            break

    if not channel:
        return jsonify({"success": False, "logs": ["ERRO: Canal não encontrado"]}), 404

    logs = []
    logs.append(f"=== Teste de publicação: {channel['name']} ===")
    logs.append("")

    # ── Passo 1: Verificar credenciais ──
    logs.append("[1/5] A verificar ficheiro de credenciais...")
    creds_path = channel.get("credentials_path", "").strip()
    if not creds_path:
        logs.append("FALHOU: Canal não tem credenciais configuradas")
        logs.append("→ Vai às definições do canal e adiciona o caminho para client_secrets.json")
        return jsonify({"success": False, "logs": logs})

    if not os.path.exists(creds_path):
        logs.append(f"FALHOU: Ficheiro não encontrado: {creds_path}")
        logs.append("→ Verifica se o caminho está correto")
        return jsonify({"success": False, "logs": logs})

    logs.append(f"OK — Ficheiro encontrado: {os.path.basename(creds_path)}")

    # ── Passo 2: Validar formato JSON ──
    logs.append("")
    logs.append("[2/5] A validar formato do ficheiro...")
    try:
        with open(creds_path, 'r') as f:
            creds_data = json.load(f)
        # Pode ser formato "installed" ou "web"
        inner = creds_data.get("installed") or creds_data.get("web") or creds_data
        client_id = inner.get("client_id", "")
        client_secret = inner.get("client_secret", "")
        if not client_id or not client_secret:
            logs.append("FALHOU: client_id ou client_secret em falta")
            return jsonify({"success": False, "logs": logs})
        logs.append(f"OK — client_id: {client_id[:25]}...")
        logs.append(f"OK — project_id: {inner.get('project_id', 'N/A')}")
    except json.JSONDecodeError:
        logs.append("FALHOU: Ficheiro JSON inválido ou corrompido")
        return jsonify({"success": False, "logs": logs})
    except Exception as e:
        logs.append(f"FALHOU: {e}")
        return jsonify({"success": False, "logs": logs})

    # ── Passo 3: Autenticação OAuth ──
    logs.append("")
    logs.append("[3/5] A autenticar com Google OAuth 2.0...")
    try:
        service, auth_logs = _get_youtube_service(creds_path)
        logs.extend(auth_logs)
        if not service:
            logs.append("FALHOU: Não foi possível autenticar")
            return jsonify({"success": False, "logs": logs})
        logs.append("OK — Autenticação bem-sucedida!")
    except Exception as e:
        logs.append(f"FALHOU: Erro na autenticação: {e}")
        return jsonify({"success": False, "logs": logs})

    # ── Passo 4: Obter informações do canal ──
    logs.append("")
    logs.append("[4/5] A obter informações do canal YouTube...")
    try:
        resp = service.channels().list(part="snippet,statistics,brandingSettings", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            logs.append("AVISO: Nenhum canal encontrado para esta conta")
            logs.append("→ A conta pode não ter um canal YouTube associado")
            return jsonify({"success": False, "logs": logs})

        yt_channel = items[0]
        snippet = yt_channel.get("snippet", {})
        stats = yt_channel.get("statistics", {})
        yt_name = snippet.get("title", "N/A")
        yt_subs = stats.get("subscriberCount", "N/A")
        yt_videos = stats.get("videoCount", "N/A")
        yt_views = stats.get("viewCount", "N/A")
        yt_thumbnail = ""
        thumbs = snippet.get("thumbnails", {})
        for size in ("high", "medium", "default"):
            if size in thumbs:
                yt_thumbnail = thumbs[size].get("url", "")
                break
        yt_channel_id = yt_channel.get("id", "")

        logs.append(f"OK — Canal: {yt_name}")
        logs.append(f"OK — ID: {yt_channel_id}")
        logs.append(f"OK — Subscritores: {yt_subs}")
        logs.append(f"OK — Vídeos: {yt_videos}")
        logs.append(f"OK — Views totais: {yt_views}")

        # Atualiza a thumbnail e nome do canal na BD
        update_data = {}
        if yt_thumbnail:
            update_data["channel_thumbnail"] = yt_thumbnail
        if yt_channel_id:
            update_data["youtube_channel_id"] = yt_channel_id
        if yt_name:
            update_data["youtube_channel_name"] = yt_name
        if yt_subs and yt_subs != "N/A":
            update_data["youtube_subscribers"] = yt_subs
        if yt_videos and yt_videos != "N/A":
            update_data["youtube_video_count"] = yt_videos
        if yt_views and yt_views != "N/A":
            update_data["youtube_view_count"] = yt_views
        if update_data:
            db.update_channel(channel_id, **update_data)

    except Exception as e:
        logs.append(f"AVISO: Não foi possível obter info do canal: {e}")
        logs.append("→ O upload pode funcionar mesmo assim")

    # ── Passo 5: Verificar permissões de upload ──
    logs.append("")
    logs.append("[5/5] A verificar permissões de upload...")
    try:
        # Testa listando categorias de vídeo (operação read-only segura)
        cats = service.videoCategories().list(part="snippet", regionCode="PT").execute()
        if cats.get("items"):
            logs.append(f"OK — API YouTube acessível ({len(cats['items'])} categorias)")
        else:
            logs.append("OK — API YouTube acessível")
        logs.append("")
        logs.append("=== TESTE CONCLUÍDO COM SUCESSO ===")
        logs.append(f"O canal '{channel['name']}' está pronto para publicar vídeos!")
        return jsonify({
            "success": True,
            "logs": logs,
            "channel_info": {
                "name": yt_name if 'yt_name' in dir() else channel["name"],
                "thumbnail": yt_thumbnail if 'yt_thumbnail' in dir() else "",
                "subscribers": yt_subs if 'yt_subs' in dir() else "0",
            }
        })
    except Exception as e:
        logs.append(f"AVISO: Erro ao verificar permissões: {e}")
        logs.append("")
        logs.append("=== TESTE CONCLUÍDO COM AVISOS ===")
        logs.append("A autenticação funcionou mas podem existir limitações na API")
        return jsonify({"success": True, "logs": logs, "warnings": True})


@app.route("/api/channels/<channel_id>/reauth", methods=["POST"])
def api_reauth_channel(channel_id):
    """Remove token existente e força nova autenticação OAuth (para trocar de conta Google)."""
    channel = None
    for ch in db.get_channels():
        if ch["id"] == channel_id:
            channel = ch
            break

    if not channel:
        return jsonify({"ok": False, "error": "Canal não encontrado"}), 404

    creds_path = channel.get("credentials_path", "").strip()
    if not creds_path or not os.path.exists(creds_path):
        return jsonify({"ok": False, "error": "Canal sem credenciais OAuth configuradas"}), 400

    # Remover tokens existentes para forçar novo login
    token_path = creds_path.replace(".json", "_token.json")
    pickle_path = creds_path.replace(".json", "_token.pickle")
    removed = []
    for tp in [token_path, pickle_path]:
        if os.path.exists(tp):
            try:
                os.remove(tp)
                removed.append(os.path.basename(tp))
            except Exception as e:
                logging.error(f"Erro ao remover token {tp}: {e}")

    if removed:
        logging.info(f"🗑️ Tokens removidos para reauth: {', '.join(removed)}")

    # Iniciar novo fluxo OAuth (abre browser para login com outra conta)
    try:
        service, auth_logs = _get_youtube_service(creds_path)
        if not service:
            return jsonify({"ok": False, "error": "Autenticação falhou. Verifica os logs.", "logs": auth_logs}), 400

        # Obter info do novo canal
        resp = service.channels().list(part="snippet,statistics", mine=True).execute()
        items = resp.get("items", [])
        if items:
            snippet = items[0].get("snippet", {})
            stats = items[0].get("statistics", {})
            yt_name = snippet.get("title", "")
            yt_channel_id = items[0].get("id", "")
            yt_subs = stats.get("subscriberCount", "")
            yt_videos = stats.get("videoCount", "")
            yt_views = stats.get("viewCount", "")
            yt_thumbnail = ""
            for size in ("high", "medium", "default"):
                if size in snippet.get("thumbnails", {}):
                    yt_thumbnail = snippet["thumbnails"][size].get("url", "")
                    break

            update_data = {}
            if yt_thumbnail:
                update_data["channel_thumbnail"] = yt_thumbnail
            if yt_channel_id:
                update_data["youtube_channel_id"] = yt_channel_id
            if yt_name:
                update_data["youtube_channel_name"] = yt_name
            if yt_subs:
                update_data["youtube_subscribers"] = yt_subs
            if yt_videos:
                update_data["youtube_video_count"] = yt_videos
            if yt_views:
                update_data["youtube_view_count"] = yt_views
            if update_data:
                db.update_channel(channel_id, **update_data)

            return jsonify({"ok": True, "message": f"Conta trocada para: {yt_name}", "channel_name": yt_name})

        return jsonify({"ok": True, "message": "Autenticado com sucesso"})

    except Exception as e:
        logging.exception("Erro no reauth")
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


@app.route("/api/channels/<channel_id>/refresh-info", methods=["POST"])
def api_refresh_channel_info(channel_id):
    """Atualiza thumbnail e info do canal via yt-dlp (sem precisar de OAuth)."""
    channel = None
    for ch in db.get_channels():
        if ch["id"] == channel_id:
            channel = ch
            break
    if not channel:
        return jsonify({"error": "Canal não encontrado"}), 404

    channel_url = channel.get("channel_url", "").strip()
    if not channel_url:
        return jsonify({"error": "Canal sem URL configurado"}), 400

    update_data = {}
    try:
        import yt_dlp
        clean_url = re.split(r'[?&]', channel_url)[0].rstrip('/')
        clean_url = re.sub(r'/(videos|shorts|streams|featured|playlists|community|about)$', '', clean_url)
        ydl_opts = {
            "quiet": True, "skip_download": True, "extract_flat": True,
            "playlistend": 1, "ignoreerrors": True, "no_warnings": True,
        }
        info = _extract_info_with_retries(ydl_opts, clean_url) or {}

        # Thumbnail
        for t in reversed(info.get("thumbnails") or []):
            url = t.get("url", "")
            if url and ("yt3.ggpht" in url or "yt3.googleusercontent" in url):
                update_data["channel_thumbnail"] = url
                break

        # Outros dados
        if info.get("channel"):
            update_data["youtube_channel_name"] = info["channel"]
        if info.get("channel_id"):
            update_data["youtube_channel_id"] = info["channel_id"]
        if info.get("channel_follower_count"):
            update_data["youtube_subscribers"] = str(info["channel_follower_count"])
        if info.get("description"):
            if not channel.get("description"):
                update_data["description"] = info["description"][:500]
    except Exception as e:
        return jsonify({"error": f"Erro ao extrair info: {e}"}), 500

    if update_data:
        ch = db.update_channel(channel_id, **update_data)
        return jsonify({"ok": True, "channel": ch})
    return jsonify({"ok": True, "message": "Nenhuma informação nova encontrada"})


@app.route("/api/channels/<channel_id>/videos", methods=["GET"])
def api_get_channel_videos(channel_id):
    """Obtém os últimos vídeos do canal via yt-dlp."""
    channel = None
    for ch in db.get_channels():
        if ch["id"] == channel_id:
            channel = ch
            break
    if not channel:
        return jsonify({"error": "Canal não encontrado"}), 404

    channel_url = channel.get("channel_url", "").strip()
    if not channel_url:
        return jsonify({"error": "Canal sem URL configurado", "videos": []}), 400

    try:
        import yt_dlp
        # Normaliza para /videos
        videos_url = _normalize_channel_url(channel_url)
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "playlistend": 12,
            "ignoreerrors": True,
            "no_warnings": True,
        }
        info = _extract_info_with_retries(ydl_opts, videos_url) or {}

        entries = info.get("entries") or []
        videos = []
        for entry in entries:
            if not entry:
                continue
            vid_id = entry.get("id", "")
            if len(vid_id) != 11:
                continue
            # Melhor thumbnail
            thumb = ""
            for t in reversed(entry.get("thumbnails") or []):
                if t.get("url"):
                    thumb = t["url"]
                    break
            if not thumb:
                thumb = f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"

            duration = entry.get("duration")
            if duration:
                mins, secs = divmod(int(duration), 60)
                hrs, mins = divmod(mins, 60)
                dur_str = f"{hrs}:{mins:02d}:{secs:02d}" if hrs else f"{mins}:{secs:02d}"
            else:
                dur_str = ""

            view_count = entry.get("view_count")
            upload_date = entry.get("upload_date") or ""
            # Formatar data
            date_str = ""
            if upload_date and len(upload_date) == 8:
                date_str = f"{upload_date[6:8]}/{upload_date[4:6]}/{upload_date[:4]}"

            videos.append({
                "id": vid_id,
                "title": (entry.get("title") or f"Vídeo {vid_id}").strip(),
                "thumbnail": thumb,
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "views": view_count,
                "duration": dur_str,
                "date": date_str,
                "upload_date": upload_date,
            })

        # Também atualiza estatísticas do canal com info do yt-dlp
        update_data = {}
        if info.get("channel_follower_count"):
            update_data["youtube_subscribers"] = str(info["channel_follower_count"])
        # Conta de vídeos: contamos os entries mas pode haver mais
        for t in reversed(info.get("thumbnails") or []):
            url = t.get("url", "")
            if url and ("yt3.ggpht" in url or "yt3.googleusercontent" in url):
                update_data["channel_thumbnail"] = url
                break
        if update_data:
            db.update_channel(channel_id, **update_data)

        return jsonify({"videos": videos})

    except Exception as e:
        return jsonify({"error": f"Erro ao buscar vídeos: {e}", "videos": []}), 500


@app.route("/api/channels/<channel_id>/upload", methods=["POST"])
def api_upload_video(channel_id):
    """Faz upload de um vídeo para o YouTube."""
    channel = None
    for ch in db.get_channels():
        if ch["id"] == channel_id:
            channel = ch
            break
    if not channel:
        return jsonify({"error": "Canal não encontrado"}), 404

    data = request.json or {}
    video_path = data.get("video_path", "").strip()
    title = data.get("title", "Clip").strip()
    description = data.get("description", "").strip()
    tags = data.get("tags", [])
    privacy = data.get("privacy", "private")

    if not video_path or not os.path.exists(video_path):
        return jsonify({"error": "Caminho do vídeo inválido"}), 400

    creds_path = channel.get("credentials_path", "").strip()
    video_id, url, _service, rotation_logs, error_message, _actual_creds = _upload_with_credential_rotation(
        creds_path,
        video_path,
        title,
        description,
        tags,
        privacy=privacy,
    )

    if video_id:
        return jsonify({
            "success": True,
            "video_id": video_id,
            "url": url,
            "logs": rotation_logs
        })
    return jsonify({
        "success": False,
        "error": error_message or "Falha no upload",
        "logs": rotation_logs
    }), 400


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


@app.route("/api/posted/sync", methods=["POST"])
def api_sync_posted_videos():
    """Sincroniza dados dos vídeos publicados com o YouTube Studio (Content tab).
    Busca views, likes, comments, privacidade, estado de processamento, etc."""
    posted = db.get_posted_videos()
    if not posted:
        return jsonify({"ok": True, "synced": 0, "message": "Sem vídeos publicados"})

    # Agrupa vídeos por canal para minimizar autenticações
    by_channel = {}
    for v in posted:
        yt_vid_id = v.get("youtube_video_id", "")
        ch_id = v.get("channel_id", "")
        if yt_vid_id and ch_id:
            if ch_id not in by_channel:
                by_channel[ch_id] = []
            by_channel[ch_id].append(v)

    synced = 0
    errors = []
    channels = db.get_channels()
    ch_map = {ch["id"]: ch for ch in channels}

    for ch_id, videos in by_channel.items():
        channel = ch_map.get(ch_id)
        if not channel:
            continue
        creds_path = channel.get("credentials_path", "").strip()
        if not creds_path or not os.path.exists(creds_path):
            continue

        try:
            service, _ = _get_youtube_service(creds_path)
            if not service:
                continue
        except Exception:
            continue

        # Buscar em blocos de 50 (limite da API)
        video_ids = [v["youtube_video_id"] for v in videos]
        for i in range(0, len(video_ids), 50):
            batch_ids = video_ids[i:i+50]
            try:
                resp = service.videos().list(
                    part="snippet,status,statistics,contentDetails",
                    id=",".join(batch_ids)
                ).execute()

                yt_map = {}
                for item in resp.get("items", []):
                    yt_map[item["id"]] = item

                for v in videos:
                    vid_id = v["youtube_video_id"]
                    if vid_id not in yt_map:
                        continue

                    yt = yt_map[vid_id]
                    snippet = yt.get("snippet", {})
                    status_info = yt.get("status", {})
                    stats = yt.get("statistics", {})
                    content = yt.get("contentDetails", {})

                    thumbs = snippet.get("thumbnails", {})
                    thumb_url = ""
                    for sz in ("maxres", "high", "medium", "default"):
                        if sz in thumbs:
                            thumb_url = thumbs[sz].get("url", "")
                            if thumb_url:
                                break

                    update_data = {
                        "youtube_title": snippet.get("title", ""),
                        "youtube_description": snippet.get("description", ""),
                        "youtube_thumbnail": thumb_url,
                        "youtube_privacy": status_info.get("privacyStatus", ""),
                        "youtube_upload_status": status_info.get("uploadStatus", ""),
                        "youtube_publish_at": status_info.get("publishAt", ""),
                        "youtube_license": status_info.get("license", ""),
                        "youtube_embeddable": status_info.get("embeddable", True),
                        "youtube_made_for_kids": status_info.get("madeForKids", False),
                        "youtube_views": int(stats.get("viewCount", 0)),
                        "youtube_likes": int(stats.get("likeCount", 0)),
                        "youtube_comments": int(stats.get("commentCount", 0)),
                        "youtube_duration": content.get("duration", ""),
                        "youtube_definition": content.get("definition", ""),
                        "youtube_tags": snippet.get("tags", []),
                        "youtube_category_id": snippet.get("categoryId", ""),
                        "youtube_channel_title": snippet.get("channelTitle", ""),
                        "youtube_published_at": snippet.get("publishedAt", ""),
                        "views": int(stats.get("viewCount", 0)),
                        "likes": int(stats.get("likeCount", 0)),
                        "comments": int(stats.get("commentCount", 0)),
                    }
                    db.update_posted_video(v["id"], **update_data)
                    synced += 1

            except Exception as e:
                errors.append(f"Erro ao sincronizar batch para canal {channel.get('name', ch_id)}: {e}")

    return jsonify({"ok": True, "synced": synced, "errors": errors if errors else None})


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
    """Publica um clip de revisão — faz upload real para o YouTube com logs detalhados."""
    data = request.json or {}
    channel_id = data.get("channel_id")

    # Busca o clip
    clip = None
    for c in db.get_review_clips():
        if c["id"] == clip_id:
            clip = c
            break
    if not clip:
        return jsonify({"error": "Clip não encontrado"}), 404

    # Determina canal
    settings = db.get_settings()
    publish_channel_id = channel_id or clip.get("channel_id") or settings.get("default_channel_id")

    logs = []
    logs.append("=== Publicação de Clip ===")
    logs.append("")

    youtube_meta = clip.get("youtube", {})
    title = youtube_meta.get("titulo") or clip.get("title") or "Clip"
    description = youtube_meta.get("descricao", "")
    clip_path = clip.get("clip_path", "")

    logs.append(f"[1/6] A preparar publicação...")
    logs.append(f"OK — Título: {title}")
    logs.append(f"OK — Ficheiro: {os.path.basename(clip_path)}")

    # Verificar ficheiro existe
    logs.append("")
    logs.append("[2/6] A verificar ficheiro de vídeo...")
    if not clip_path or not os.path.exists(clip_path):
        logs.append(f"FALHOU: Ficheiro não encontrado: {clip_path}")
        logs.append("→ O clip pode ter sido movido ou apagado")
        # Marca como erro
        db.update_review_clip(clip_id, status="error", error_detail="Ficheiro não encontrado")
        return jsonify({"success": False, "logs": logs, "error": "Ficheiro não encontrado"})

    file_size = os.path.getsize(clip_path)
    logs.append(f"OK — Tamanho: {file_size / 1024 / 1024:.1f} MB")

    # Verificar canal
    logs.append("")
    logs.append("[3/6] A verificar canal de destino...")
    if not publish_channel_id:
        logs.append("AVISO: Nenhum canal selecionado — a publicar apenas localmente")
        logs.append("")
        # Publicar localmente sem upload YouTube
        result = db.publish_review_clip(clip_id, publish_channel_id)
        if result:
            logs.append("=== PUBLICADO LOCALMENTE ===")
            logs.append("O clip foi publicado mas não foi enviado para o YouTube.")
            logs.append("→ Seleciona um canal com OAuth configurado para fazer upload")
            return jsonify({"success": True, "logs": logs, "local_only": True, "video": result.get("video")})
        return jsonify({"success": False, "logs": logs, "error": "Erro ao publicar"})

    channel = None
    for ch in db.get_channels():
        if ch["id"] == publish_channel_id:
            channel = ch
            break

    if not channel:
        logs.append(f"FALHOU: Canal não encontrado (ID: {publish_channel_id})")
        return jsonify({"success": False, "logs": logs, "error": "Canal não encontrado"})

    logs.append(f"OK — Canal: {channel.get('name', '?')}")

    # Verificar credenciais
    creds_path = channel.get("credentials_path", "").strip()
    has_rotation_credentials = False
    if _HAS_CREDENTIALS_ROTATION:
        try:
            current_rot = credentials_rotation.get_current_credentials()
            has_rotation_credentials = bool(current_rot and os.path.exists(current_rot))
        except Exception:
            has_rotation_credentials = False

    if (not creds_path or not os.path.exists(creds_path)) and not has_rotation_credentials:
        logs.append("AVISO: Canal sem credenciais OAuth — a publicar apenas localmente")
        result = db.publish_review_clip(clip_id, publish_channel_id)
        if result:
            logs.append("")
            logs.append("=== PUBLICADO LOCALMENTE ===")
            logs.append("→ Configura credenciais OAuth no canal para uploadar ao YouTube")
            return jsonify({"success": True, "logs": logs, "local_only": True, "video": result.get("video")})
        return jsonify({"success": False, "logs": logs, "error": "Erro ao publicar"})

    if creds_path and os.path.exists(creds_path):
        logs.append(f"OK — Credenciais fallback: {os.path.basename(creds_path)}")
    if has_rotation_credentials:
        logs.append("OK — Rotação automática de credenciais ativa")

    # Marcar clip como "uploading"
    db.update_review_clip(clip_id, status="uploading")

    # Upload com autenticação OAuth + rotação automática por quota
    logs.append("")
    logs.append("[4/6] A autenticar + upload com rotação de credenciais...")

    # Configurações de publicação do canal
    privacy = channel.get("default_privacy", "private")
    category = channel.get("default_category", "22")
    default_tags = channel.get("default_tags", "")

    # Descrição completa: template + descrição IA
    if channel.get("default_video_description"):
        template = channel["default_video_description"]
        description = template.replace("{titulo}", title).replace("{canal_fonte}",
            clip.get("source_channel_name", "")) + "\n\n" + description
    
    # Adiciona URLs do vídeo e canal originais (antes das hashtags)
    video_url = clip.get("source_url") or ""
    source_channel_name = clip.get("source_channel_name", "")

    # Separa a descrição e as hashtags
    desc_lines = (description or "").strip().split("\n")
    desc_without_hashtags = []
    desc_hashtags = []

    for line in desc_lines:
        clean_line = (line or "").strip()
        if clean_line.startswith("#"):
            desc_hashtags.append(clean_line)
            continue

        # Remove link cru duplicado do vídeo original (mantemos só a linha "🎬 Vídeo Original")
        if video_url and video_url in clean_line:
            continue

        # Remove linhas já montadas em tentativas anteriores para evitar duplicação
        if clean_line.startswith("🎬 Vídeo Original:") or clean_line.startswith("📺 Canal Original:"):
            continue

        desc_without_hashtags.append(line)

    # Hashtags vindas de "Tags padrão" (separadas por vírgula)
    default_tags_list = [t.strip() for t in (default_tags or "").split(",") if t.strip()]
    default_tags_hashtags = []
    for tag in default_tags_list:
        raw = tag.lstrip("#").strip().replace(" ", "")
        normalized = "".join(ch for ch in raw if ch.isalnum() or ch == "_")
        if normalized:
            default_tags_hashtags.append(f"#{normalized}")

    # Reconstrói a descrição final: descrição + URLs + hashtags
    final_desc = "\n".join(desc_without_hashtags).strip()

    if video_url:
        final_desc += f"\n\n🎬 Vídeo Original: {video_url}"

    if source_channel_name:
        channel_url = f"https://www.youtube.com/@{source_channel_name.replace(' ', '')}"
        final_desc += f"\n📺 Canal Original: {channel_url}"

    # Adiciona hashtags existentes + hashtags das tags padrão (sem duplicatas)
    all_desc_hashtags = list(dict.fromkeys(desc_hashtags + default_tags_hashtags))
    if all_desc_hashtags:
        final_desc += "\n\n" + " ".join(all_desc_hashtags)

    description = final_desc
    
    # Extrai hashtags para tags do YouTube (combine com default_tags)
    import re as regex
    hashtags_from_desc = regex.findall(r'#\w+', description or "")
    tags = [t.strip() for t in (default_tags).split(",") if t.strip()]
    tags = list(dict.fromkeys(tags + hashtags_from_desc))  # Remove duplicatas

    # AGENDAMENTO AUTOMÁTICO
    # Se agendamento está ativo, calcula próximo slot e faz upload como "private" com publishAt
    publish_at = None
    schedule_enabled = settings.get("schedule_enabled", True)
    
    if schedule_enabled:
        from datetime import datetime
        publish_at = db.get_next_scheduled_slot(channel.get("id"))
        if publish_at:
            privacy = "private"  # Sempre privado com agendamento
            logs.append("")
            logs.append(f"📅 Agendamento automático ativo")
            logs.append(f"→ Publicação agendada para: {publish_at.strftime('%Y-%m-%d %H:%M')}")
    
    logs.append("")
    logs.append("[5/6] A fazer upload para o YouTube...")
    logs.append(f"→ Privacidade: {privacy}")
    logs.append(f"→ Categoria: {category}")
    if tags:
        logs.append(f"→ Tags: {', '.join(tags[:5])}")

    video_id, yt_url, service, upload_logs, upload_error, actual_creds_path = _upload_with_credential_rotation(
        creds_path,
        clip_path,
        title,
        description,
        tags,
        category=category,
        privacy=privacy,
        publish_at=publish_at,
    )
    logs.extend(upload_logs)

    if upload_error and not video_id:
        logs.append(f"FALHOU: Erro no upload: {upload_error}")
        db.update_review_clip(clip_id, status="pending")
        return jsonify({"success": False, "logs": logs, "error": upload_error})

    if not video_id:
        logs.append("FALHOU: Upload não retornou video ID")
        db.update_review_clip(clip_id, status="pending")
        return jsonify({"success": False, "logs": logs, "error": "Upload falhou"})

    # Detetar o canal REAL onde foi publicado (baseado na credencial que funcionou)
    actual_channel_id = publish_channel_id
    if actual_creds_path:
        channels = db.get_channels()
        for ch in channels:
            ch_creds = ch.get("credentials_path", "").strip()
            if ch_creds and os.path.abspath(ch_creds) == os.path.abspath(actual_creds_path):
                actual_channel_id = ch["id"]
                if actual_channel_id != publish_channel_id:
                    logs.append(f"ℹ️ Canal REAL: {ch.get('name', actual_channel_id)} (credenciais {os.path.basename(actual_creds_path)})")
                break

    # Verificar vídeo no YouTube
    logs.append("")
    logs.append("[6/6] A verificar vídeo no YouTube Studio...")
    yt_video_info = {}
    youtube_channel_id = ""
    youtube_channel_title = ""
    try:
        resp = service.videos().list(
            part="snippet,status,statistics,contentDetails",
            id=video_id
        ).execute()
        items = resp.get("items", [])
        if items:
            v = items[0]
            snippet = v.get("snippet", {})
            status_info = v.get("status", {})
            stats = v.get("statistics", {})
            content = v.get("contentDetails", {})
            youtube_channel_id = snippet.get("channelId", "")
            youtube_channel_title = snippet.get("channelTitle", "")

            yt_video_info = {
                "youtube_video_id": video_id,
                "youtube_url": yt_url,
                "youtube_channel_id": youtube_channel_id,
                "youtube_channel_title": youtube_channel_title,
                "youtube_title": snippet.get("title", title),
                "youtube_description": snippet.get("description", ""),
                "youtube_thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", "")
                    or snippet.get("thumbnails", {}).get("medium", {}).get("url", "")
                    or snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "youtube_privacy": status_info.get("privacyStatus", privacy),
                "youtube_upload_status": status_info.get("uploadStatus", ""),
                "youtube_publish_at": status_info.get("publishAt", ""),
                "youtube_license": status_info.get("license", ""),
                "youtube_embeddable": status_info.get("embeddable", True),
                "youtube_made_for_kids": status_info.get("madeForKids", False),
                "youtube_views": int(stats.get("viewCount", 0)),
                "youtube_likes": int(stats.get("likeCount", 0)),
                "youtube_comments": int(stats.get("commentCount", 0)),
                "youtube_duration": content.get("duration", ""),
                "youtube_definition": content.get("definition", ""),
                "youtube_tags": snippet.get("tags", []),
                "youtube_category_id": snippet.get("categoryId", ""),
            }
            logs.append(f"OK — Vídeo encontrado no YouTube!")
            logs.append(f"OK — Estado: {status_info.get('uploadStatus', '?')}")
            logs.append(f"OK — Privacidade: {status_info.get('privacyStatus', '?')}")
            logs.append(f"OK — Definição: {content.get('definition', '?')}")
        else:
            logs.append("AVISO: Vídeo ainda não visível na API (pode levar alguns segundos)")
    except Exception as e:
        logs.append(f"AVISO: Não foi possível verificar: {e}")

    # Determina o canal local real do upload (importantíssimo quando há rotação de credenciais)
    resolved_channel_id, resolve_reason = _resolve_local_channel_for_uploaded_video(
        expected_channel_id=publish_channel_id,
        youtube_channel_id=youtube_channel_id,
        youtube_channel_title=youtube_channel_title,
    )

    if resolved_channel_id != publish_channel_id:
        logs.append("")
        logs.append("AVISO: Canal real do upload difere do canal selecionado")
        logs.append(f"→ Canal selecionado: {publish_channel_id}")
        logs.append(f"→ Canal real (mapeado): {resolved_channel_id} [{resolve_reason}]")

    # Publicar na BD com dados reais do YouTube
    result = db.publish_review_clip(clip_id, resolved_channel_id)
    if result and result.get("video"):
        # Atualizar o vídeo publicado com dados reais do YouTube
        posted_id = result["video"]["id"]
        update_data = {
            "youtube_url": yt_url,
            "youtube_video_id": video_id,
            "channel_id": resolved_channel_id,
            "status": "published",
            **yt_video_info,
        }
        db.update_posted_video(posted_id, **update_data)

    # Se agendou no canal A mas publicou no canal B, mover slot reservado.
    if publish_at and resolved_channel_id and resolved_channel_id != publish_channel_id:
        try:
            db.reassign_scheduled_upload_channel(publish_at, publish_channel_id, resolved_channel_id)
        except Exception as e:
            logs.append(f"AVISO: Falha ao mover slot de agendamento entre canais: {e}")

    # Garantir que o clip também reflete o canal real.
    if resolved_channel_id:
        db.update_review_clip(clip_id, channel_id=resolved_channel_id)

    logs.append("")
    logs.append("=== PUBLICAÇÃO CONCLUÍDA COM SUCESSO! ===")
    logs.append(f"Vídeo disponível em: {yt_url}")

    return jsonify({
        "success": True,
        "logs": logs,
        "video_id": video_id,
        "youtube_url": yt_url,
        "video": result.get("video") if result else None,
    })


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
#  API — AGENDAMENTOS
# ═══════════════════════════════════════════════

@app.route("/api/schedules", methods=["GET"])
def api_get_schedules():
    """Retorna todos os vídeos agendados e slots reservados."""
    return jsonify(db.get_all_scheduled_videos())


@app.route("/api/schedules/rearrange", methods=["POST"])
def api_rearrange_schedules():
    """Reagenda todos os slots futuros com os parâmetros fornecidos."""
    data = request.json or {}
    channel_id = data.get("channel_id") or None
    interval_hours = float(data.get("interval_hours", 2))
    videos_per_day = int(data.get("videos_per_day", 12))
    start_time = data.get("start_time", "08:00")
    end_time = data.get("end_time", "22:00")
    
    # Validar parâmetros
    interval_hours = max(0.5, min(24, interval_hours))
    videos_per_day = max(1, min(50, videos_per_day))
    
    # Guardar config nas settings
    db.update_settings(
        schedule_interval_hours=interval_hours,
        schedule_videos_per_day=videos_per_day,
        schedule_start_time=start_time,
        schedule_end_time=end_time,
    )
    
    rescheduled = db.rearrange_scheduled_slots(
        channel_id=channel_id,
        interval_hours=interval_hours,
        videos_per_day=videos_per_day,
        start_time=start_time,
        end_time=end_time,
    )
    
    # Atualizar publishAt no YouTube para vídeos já publicados
    yt_updated = 0
    yt_errors = []
    if rescheduled:
        channels = db.get_channels()
        ch_map = {ch["id"]: ch for ch in channels}
        by_channel = {}
        for rv in rescheduled:
            ch = rv.get("channel_id", "")
            if ch not in by_channel:
                by_channel[ch] = []
            by_channel[ch].append(rv)
        
        try:
            import credentials_rotation
            rotation_list = getattr(credentials_rotation, "CREDENTIALS_LIST", []) or []
        except Exception:
            rotation_list = []
        
        for ch_id, videos in by_channel.items():
            channel = ch_map.get(ch_id)
            if not channel:
                continue
            creds_path = channel.get("credentials_path", "").strip()
            
            creds_queue = []
            if creds_path and os.path.exists(creds_path):
                creds_queue.append(creds_path)
            for rot_cred in rotation_list:
                if rot_cred and os.path.exists(rot_cred) and os.path.abspath(rot_cred) != os.path.abspath(creds_path or ""):
                    creds_queue.append(rot_cred)
            
            if not creds_queue:
                continue
            
            service = None
            current_creds_idx = 0
            
            def _get_svc():
                nonlocal service, current_creds_idx
                while current_creds_idx < len(creds_queue):
                    try:
                        svc, _ = _get_youtube_service(creds_queue[current_creds_idx])
                        if svc:
                            service = svc
                            return True
                    except Exception:
                        pass
                    current_creds_idx += 1
                return False
            
            if not _get_svc():
                yt_errors.append(f"Auth failed for channel {ch_id}")
                continue
            
            for rv in videos:
                updated = False
                while not updated:
                    try:
                        service.videos().update(
                            part="status",
                            body={
                                "id": rv["youtube_video_id"],
                                "status": {
                                    "privacyStatus": "private",
                                    "publishAt": rv["youtube_publish_at"],
                                },
                            },
                        ).execute()
                        yt_updated += 1
                        updated = True
                    except Exception as e:
                        if "quotaExceeded" in str(e):
                            current_creds_idx += 1
                            if not _get_svc():
                                yt_errors.append(f"{rv['youtube_video_id']}: Quota excedida em todas as credenciais")
                                break
                        else:
                            yt_errors.append(f"Failed to update {rv['youtube_video_id']}: {e}")
                            break
    
    result = db.get_all_scheduled_videos()
    result["youtube_updated"] = yt_updated
    if yt_errors:
        result["youtube_errors"] = yt_errors
    return jsonify(result)


@app.route("/api/schedules/sync-youtube", methods=["POST"])
def api_sync_youtube_schedules():
    """Sincroniza as datas de agendamento da DB com o YouTube.
    Atualiza o publishAt de todos os vídeos futuros no YouTube para corresponder à DB.
    Também lê o estado real de vídeos no YouTube para atualizar a DB."""
    import logging
    from datetime import datetime, timezone
    
    posted = db.get_posted_videos() if hasattr(db, 'get_posted_videos') else db._load().get("posted_videos", [])
    now_utc = datetime.now(timezone.utc)
    
    # Encontrar todos os vídeos com youtube_video_id e publish_at futuro
    future_videos = []
    for v in posted:
        pub = v.get("youtube_publish_at", "")
        yt_id = v.get("youtube_video_id", "")
        if not pub or not yt_id:
            continue
        try:
            # Parse publish_at como UTC (o Z indica UTC)
            pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00").replace(".000+00:00", "+00:00"))
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            if pub_dt > now_utc:
                future_videos.append(v)
        except Exception:
            try:
                pub_dt = datetime.strptime(pub, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc)
                if pub_dt > now_utc:
                    future_videos.append(v)
            except Exception:
                continue
    
    if not future_videos:
        return jsonify({"ok": True, "youtube_updated": 0, "message": "Nenhum vídeo futuro encontrado"})
    
    # Agrupar por canal
    channels = db.get_channels()
    ch_map = {ch["id"]: ch for ch in channels}
    by_channel = {}
    for v in future_videos:
        ch = v.get("channel_id", "")
        if ch not in by_channel:
            by_channel[ch] = []
        by_channel[ch].append(v)
    
    # Construir lista de credenciais (canal + rotação) para lidar com quota
    try:
        import credentials_rotation
        rotation_list = getattr(credentials_rotation, "CREDENTIALS_LIST", []) or []
    except Exception:
        rotation_list = []
    
    yt_updated = 0
    yt_errors = []
    
    for ch_id, videos in by_channel.items():
        channel = ch_map.get(ch_id)
        if not channel:
            yt_errors.append(f"Canal {ch_id} não encontrado na DB")
            continue
        creds_path = channel.get("credentials_path", "").strip()
        
        # Construir fila de credenciais: canal primeiro, depois rotação
        creds_queue = []
        if creds_path and os.path.exists(creds_path):
            creds_queue.append(creds_path)
        for rot_cred in rotation_list:
            if rot_cred and os.path.exists(rot_cred) and os.path.abspath(rot_cred) != os.path.abspath(creds_path or ""):
                creds_queue.append(rot_cred)
        
        if not creds_queue:
            yt_errors.append(f"Credenciais não encontradas para canal {channel.get('name', ch_id)}")
            continue
        
        service = None
        current_creds_idx = 0
        
        def _get_service():
            nonlocal service, current_creds_idx
            while current_creds_idx < len(creds_queue):
                try:
                    svc, _ = _get_youtube_service(creds_queue[current_creds_idx])
                    if svc:
                        service = svc
                        return True
                except Exception:
                    pass
                current_creds_idx += 1
            return False
        
        if not _get_service():
            yt_errors.append(f"Auth falhou para canal {channel.get('name', ch_id)}")
            continue
        
        logging.info(f"📅 Sincronizando {len(videos)} vídeos do canal {channel.get('name', ch_id)} com YouTube")
        
        for v in videos:
            yt_id = v["youtube_video_id"]
            publish_at = v["youtube_publish_at"]
            updated = False
            while not updated:
                try:
                    service.videos().update(
                        part="status",
                        body={
                            "id": yt_id,
                            "status": {
                                "privacyStatus": "private",
                                "publishAt": publish_at,
                            },
                        },
                    ).execute()
                    yt_updated += 1
                    updated = True
                    logging.info(f"  ✅ {yt_id} → {publish_at}")
                except Exception as e:
                    if "quotaExceeded" in str(e):
                        logging.warning(f"  ⚠️ Quota excedida, tentando próximas credenciais...")
                        current_creds_idx += 1
                        if not _get_service():
                            yt_errors.append(f"{yt_id}: Quota excedida em todas as credenciais")
                            break
                    else:
                        yt_errors.append(f"{yt_id}: {e}")
                        logging.error(f"  ❌ {yt_id}: {e}")
                        break
    
    return jsonify({
        "ok": True,
        "total_future": len(future_videos),
        "youtube_updated": yt_updated,
        "youtube_errors": yt_errors,
    })


@app.route("/api/schedules/clear", methods=["POST"])
def api_clear_schedules():
    """Limpa todos os agendamentos futuros."""
    data = request.json or {}
    channel_id = data.get("channel_id") or None
    db.clear_all_scheduled_slots(channel_id=channel_id)
    return jsonify({"ok": True})


@app.route("/api/schedules/config", methods=["PATCH"])
def api_update_schedule_config():
    """Atualiza apenas as configurações de agendamento."""
    data = request.json or {}
    allowed_keys = ["schedule_interval_hours", "schedule_videos_per_day", "schedule_start_time", "schedule_end_time", "schedule_enabled", "schedule_max_per_batch"]
    filtered = {k: v for k, v in data.items() if k in allowed_keys}
    if filtered:
        s = db.update_settings(**filtered)
        return jsonify(s)
    return jsonify({"error": "Nenhum parâmetro válido"}), 400


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


@app.route("/api/video/fetch-info", methods=["POST"])
def api_fetch_video_info():
    """Faz fetch de informações do vídeo YouTube (título, canal, URL)."""
    try:
        import yt_dlp

        data = request.json or {}
        url = data.get("url", "").strip()
        
        if not url:
            return jsonify({"error": "URL é obrigatória"}), 400
        
        logging.info(f"🔍 Fetchando info de: {url}")
        
        # Usar yt-dlp para extrair informações (com retry em caso de throttle)
        ydl_opts = {
            'quiet': False,
            'no_warnings': False,
            'skip_download': True,
            'extract_flat': False,
            'socket_timeout': 30,
        }
        
        try:
            info = _extract_info_with_retries(ydl_opts, url) or {}
            if not info:
                return jsonify({"error": "Não consegui extrair informações (YouTube throttle/bot check)"}), 400
        except Exception as e:
            logging.error(f"❌ Erro ao extrair info: {str(e)[:200]}")
            return jsonify({"error": f"Não consegui extrair informações: {str(e)[:100]}"}), 400
        
        # Extrair dados relevant
        title = info.get('title', '')
        video_url = info.get('webpage_url', url)
        uploader = info.get('uploader', '')
        uploader_url = info.get('uploader_url', '')
        channel_id = info.get('channel_id', '')
        
        # Construir URL do canal se não tiver
        if not uploader_url and channel_id:
            uploader_url = f"https://www.youtube.com/channel/{channel_id}"
        elif not uploader_url and uploader:
            # Try to construct from uploader name
            uploader_url = f"https://www.youtube.com/@{uploader.replace(' ', '')}"
        
        result = {
            "ok": True,
            "title": title,
            "url": video_url,
            "channel_name": uploader,
            "channel_url": uploader_url,
        }
        
        logging.info(f"✅ Info fetched: {title[:50]}")
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"❌ Erro ao fazer fetch de video info: {e}")
        return jsonify({"error": f"Erro: {str(e)[:100]}"}), 500


# ═══════════════════════════════════════════════
#  SERVIR CLIPS EDITADOS
# ═══════════════════════════════════════════════

@app.route("/clips/<path:filename>")
def serve_clip(filename):
    return send_from_directory("downloads/clips_editados", filename)


# ═══════════════════════════════════════════════
#  PROXY ROTATIVO
#  ═══════════════════════════════════════════════

@app.route("/api/proxy/status", methods=["GET"])
def get_proxy_status():
    """Status das proxies rotativas."""
    if not _HAS_PROXY:
        return jsonify({"enabled": False, "total": 0})
    status = proxy_rotator.get_proxy_status()
    return jsonify({"enabled": True, **status})


@app.route("/api/proxy/refresh", methods=["POST"])
def refresh_proxies_api():
    """Força refresh da lista de proxies."""
    if not _HAS_PROXY:
        return jsonify({"ok": False, "error": "Módulo de proxy não disponível"})
    import threading
    def _do_refresh():
        try:
            proxies = proxy_rotator.refresh_proxies(force=True)
            logging.info(f"🌐 Proxies refrescadas: {len(proxies)} funcionais")
        except Exception as e:
            logging.error(f"❌ Erro ao refrescar proxies: {e}")
    threading.Thread(target=_do_refresh, daemon=True).start()
    return jsonify({"ok": True, "message": "Refresh iniciado em background"})


# ═══════════════════════════════════════════════
#  CREDENCIAIS ROTATIVAS
# ═══════════════════════════════════════════════

@app.route("/api/credentials/status", methods=["GET"])
def get_credentials_status():
    """Status da rotação automática de credenciais."""
    try:
        import credentials_rotation
        status = credentials_rotation.get_rotation_status()
        return jsonify({"ok": True, **status})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════

def _start_server():
    """Inicia o servidor Flask com todos os serviços (worker, proxy, auto-manager)."""
    os.makedirs("data", exist_ok=True)
    os.makedirs("downloads/clips_editados", exist_ok=True)
    os.makedirs("downloads/satisfying", exist_ok=True)
    _silenciar_logs_http()

    # ── Worker ──
    worker.start()
    logging.info("⚙️  Worker iniciado")

    # ── Proxies em background ──
    if _HAS_PROXY:
        import threading
        def _init_proxies():
            try:
                proxies = proxy_rotator.refresh_proxies(force=True)
                logging.info(f"🌐 {len(proxies)} proxies prontas")
            except Exception as e:
                logging.warning(f"⚠️ Erro ao iniciar proxies: {e}")
        threading.Thread(target=_init_proxies, daemon=True).start()
        logging.info("🌐 Proxy rotativo a iniciar em background...")

    print("\n🚀 ClipAI Interface em http://localhost:5000\n")
    is_child = os.environ.get("CLIPAI_WATCHDOG") == "1"
    if is_child:
        print("🐕 Watchdog ativo — restart automático em caso de crash\n")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


def _run_as_watchdog():
    """
    Lança app.py como subprocesso e reinicia-o se crashar.
    Delay exponencial: 3s → 6s → 12s → ... max 120s.
    Se correr >60s sem crash, reset do delay.
    """
    import subprocess as _sp
    import time as _time

    MAX_DELAY = 120
    INIT_DELAY = 3
    HEALTHY_UPTIME = 60

    base_dir = os.path.dirname(os.path.abspath(__file__))
    python = os.path.join(base_dir, "venv", "Scripts", "python.exe")
    if not os.path.exists(python):
        python = sys.executable

    delay = INIT_DELAY
    restarts = 0

    print("=" * 60)
    print("🐕 WATCHDOG ClipAI — auto-restart em caso de crash")
    print(f"   Python: {python}")
    print("=" * 60)

    while True:
        t0 = _time.time()
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["CLIPAI_WATCHDOG"] = "1"          # flag para o filho saber

        proc = _sp.Popen(
            [python, os.path.join(base_dir, "app.py")],
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        try:
            exit_code = proc.wait()
        except KeyboardInterrupt:
            print("\n🛑 Ctrl+C — a parar...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except _sp.TimeoutExpired:
                proc.kill()
            print("👋 ClipAI terminado.")
            break

        uptime = _time.time() - t0

        if exit_code == 0:
            print("✅ Servidor terminou normalmente.")
            break

        restarts += 1
        print(f"\n💥 Servidor crashou! (exit {exit_code}, uptime {uptime:.0f}s, restart #{restarts})")

        if uptime > HEALTHY_UPTIME:
            delay = INIT_DELAY
        else:
            delay = min(delay * 2, MAX_DELAY)

        print(f"🔄 A reiniciar em {delay}s...\n")
        _time.sleep(delay)


if __name__ == "__main__":
    if os.environ.get("CLIPAI_WATCHDOG") == "1":
        # Somos o processo filho — arrancar o servidor normalmente
        _start_server()
    else:
        # Somos o processo principal — arrancar como watchdog
        _run_as_watchdog()

