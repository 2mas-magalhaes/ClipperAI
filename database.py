"""
Camada de base de dados JSON para o ClipAI.
Gere queue de vídeos, canais YouTube, vídeos publicados e definições.
"""

import json
import os
import uuid
from datetime import datetime
from threading import Lock

DB_PATH = "data/clipai_db.json"
_lock = Lock()


def _default_db():
    """Estrutura padrão da base de dados."""
    return {
        "queue": [],
        "channels": [],
        "followed_channels": [],
        "recent_source_videos": [],
        "review_clips": [],
        "posted_videos": [],
        "settings": {
            "ollama_model": "llama3.1",
            "whisper_model_gpu": "medium",
            "whisper_model_cpu": "small",
            "default_channel_id": None,
            "auto_publish": False,
            "auto_scan_interval_minutes": 30,
            "max_clips_per_video": 7,
            "clip_duration_min": 30,
            "clip_duration_max": 60,
            "max_video_duration_min": 60,
            "schedule_enabled": True,
            "schedule_interval_hours": 2,
            "schedule_max_per_batch": 5,
            "schedule_videos_per_day": 12,
            "schedule_start_time": "08:00",
            "schedule_end_time": "22:00",
        },
        "scheduled_uploads": {},  # {channel_id: [timestamp1, timestamp2, ...]}
    }


def _load():
    """Carrega a base de dados do disco."""
    if not os.path.exists(DB_PATH):
        return _default_db()
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
            # Migração leve para novas chaves
            defaults = _default_db()
            for key, value in defaults.items():
                if key not in db:
                    db[key] = value
            if "settings" not in db or not isinstance(db["settings"], dict):
                db["settings"] = defaults["settings"]
            for sk, sv in defaults["settings"].items():
                if sk not in db["settings"]:
                    db["settings"][sk] = sv

            # Migração do default antigo: se ainda estiver em llama2 (default legacy), muda para llama3.1
            # Não mexe se o utilizador já escolheu outro modelo.
            try:
                if (db.get("settings") or {}).get("ollama_model") == "llama2":
                    db["settings"]["ollama_model"] = "llama3.1"
            except Exception:
                pass
            
            # Garantir que scheduled_uploads existe
            if "scheduled_uploads" not in db:
                db["scheduled_uploads"] = {}
            
            return db
    except Exception:
        return _default_db()


def _save(db):
    """Guarda a base de dados no disco."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════
#  QUEUE
# ═══════════════════════════════════════════════

def get_queue():
    with _lock:
        db = _load()
        return db.get("queue", [])


def add_to_queue(url, title="", channel_id=None, priority=0, auto_publish=None):
    with _lock:
        db = _load()
        # Se auto_publish não for especificado, usa o default global
        if auto_publish is None:
            auto_publish = bool(db.get("settings", {}).get("auto_publish", False))
        item = {
            "id": str(uuid.uuid4())[:8],
            "url": url,
            "title": title or f"Vídeo {len(db['queue']) + 1}",
            "channel_id": channel_id,
            "source_video_id": None,
            "source_channel_name": "",
            "priority": priority,
            "auto_publish": bool(auto_publish),
            "status": "queued",
            "status_detail": "",
            "progress": 0,
            "clips_total": 0,
            "clips_done": 0,
            "clips": [],
            "error_msg": "",
            "duration_seconds": None,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "finished_at": None,
        }
        db["queue"].append(item)
        _save(db)
        return item


def add_to_queue_with_meta(url, title="", channel_id=None, priority=0, source_video_id=None, source_channel_name="", auto_publish=None):
    with _lock:
        db = _load()
        if auto_publish is None:
            auto_publish = bool(db.get("settings", {}).get("auto_publish", False))
        item = {
            "id": str(uuid.uuid4())[:8],
            "url": url,
            "title": title or f"Vídeo {len(db['queue']) + 1}",
            "channel_id": channel_id,
            "source_video_id": source_video_id,
            "source_channel_name": source_channel_name,
            "priority": priority,
            "auto_publish": bool(auto_publish),
            "status": "queued",
            "status_detail": "",
            "progress": 0,
            "clips_total": 0,
            "clips_done": 0,
            "clips": [],
            "error_msg": "",
            "duration_seconds": None,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "finished_at": None,
        }
        db["queue"].append(item)
        _save(db)
        return item


def update_queue_item(item_id, **kwargs):
    with _lock:
        db = _load()
        for item in db["queue"]:
            if item["id"] == item_id:
                item.update(kwargs)
                _save(db)
                return item
        return None


def remove_from_queue(item_id):
    with _lock:
        db = _load()
        db["queue"] = [q for q in db["queue"] if q["id"] != item_id]
        _save(db)
        return True


def reorder_queue(ordered_ids):
    """Reordena a queue segundo a lista de IDs."""
    with _lock:
        db = _load()
        by_id = {q["id"]: q for q in db["queue"]}
        new_queue = []
        for qid in ordered_ids:
            if qid in by_id:
                new_queue.append(by_id.pop(qid))
        # Adiciona os restantes no final
        new_queue.extend(by_id.values())
        db["queue"] = new_queue
        _save(db)
        return new_queue


def get_current_processing():
    """Retorna o item que está a ser processado."""
    with _lock:
        db = _load()
        for item in db["queue"]:
            if item["status"] in ("downloading", "analyzing", "editing"):
                return item
        return None


# ═══════════════════════════════════════════════
#  CANAIS
# ═══════════════════════════════════════════════

def get_channels():
    with _lock:
        db = _load()
        return db.get("channels", [])


def add_channel(name, channel_url="", credentials_path="", description=""):
    with _lock:
        db = _load()
        channel = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "channel_url": channel_url,
            "credentials_path": credentials_path,
            "description": description,
            "channel_thumbnail": "",  # URL da foto do canal
            "videos_posted": 0,
            "total_views": 0,
            "total_likes": 0,
            "active": True,
            "created_at": datetime.now().isoformat(),
        }
        db["channels"].append(channel)
        # Se é o primeiro canal, define como padrão
        if len(db["channels"]) == 1:
            db["settings"]["default_channel_id"] = channel["id"]
        _save(db)
        return channel


def update_channel(channel_id, **kwargs):
    with _lock:
        db = _load()
        for ch in db["channels"]:
            if ch["id"] == channel_id:
                ch.update(kwargs)
                _save(db)
                return ch
        return None


def remove_channel(channel_id):
    with _lock:
        db = _load()
        db["channels"] = [c for c in db["channels"] if c["id"] != channel_id]
        if db["settings"].get("default_channel_id") == channel_id:
            db["settings"]["default_channel_id"] = db["channels"][0]["id"] if db["channels"] else None
        _save(db)
        return True


# ═══════════════════════════════════════════════
#  CANAIS A SEGUIR (FONTE)
# ═══════════════════════════════════════════════

def get_followed_channels():
    with _lock:
        db = _load()
        return db.get("followed_channels", [])


def add_followed_channel(name, source_url, max_age_days=7, target_channel_id=None, active=True):
    with _lock:
        db = _load()
        item = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "source_url": source_url,
            "max_age_days": int(max_age_days),
            "target_channel_id": target_channel_id,
            "active": bool(active),
            "last_scan_at": None,
            "created_at": datetime.now().isoformat(),
        }
        db["followed_channels"].append(item)
        _save(db)
        return item


def update_followed_channel(follow_id, **kwargs):
    with _lock:
        db = _load()
        for item in db.get("followed_channels", []):
            if item["id"] == follow_id:
                item.update(kwargs)
                _save(db)
                return item
        return None


def remove_followed_channel(follow_id):
    with _lock:
        db = _load()
        db["followed_channels"] = [f for f in db.get("followed_channels", []) if f["id"] != follow_id]
        db["recent_source_videos"] = [v for v in db.get("recent_source_videos", []) if v.get("follow_id") != follow_id]
        _save(db)
        return True


def get_recent_source_videos(follow_id=None):
    with _lock:
        db = _load()
        items = db.get("recent_source_videos", [])
        if follow_id:
            items = [v for v in items if v.get("follow_id") == follow_id]
        return items


def upsert_recent_source_video(video_data):
    with _lock:
        db = _load()
        items = db.get("recent_source_videos", [])
        key = (video_data.get("follow_id"), video_data.get("source_video_id"))
        for item in items:
            if (item.get("follow_id"), item.get("source_video_id")) == key:
                item.update(video_data)
                _save(db)
                return item
        items.append(video_data)
        db["recent_source_videos"] = items
        _save(db)
        return video_data


def set_recent_video_clip_status(source_video_id, status):
    with _lock:
        db = _load()
        changed = 0
        for item in db.get("recent_source_videos", []):
            if item.get("source_video_id") == source_video_id:
                item["clip_status"] = status
                changed += 1
        if changed:
            _save(db)
        return changed


def source_video_already_tracked(source_video_id):
    with _lock:
        db = _load()
        for v in db.get("recent_source_videos", []):
            if v.get("source_video_id") == source_video_id:
                return True
        for q in db.get("queue", []):
            if q.get("source_video_id") == source_video_id:
                return True
        return False


# ═══════════════════════════════════════════════
#  VÍDEOS PUBLICADOS
# ═══════════════════════════════════════════════

def get_posted_videos():
    with _lock:
        db = _load()
        return db.get("posted_videos", [])


def add_posted_video(clip_path, title, channel_id, youtube_url="", thumbnail=""):
    with _lock:
        db = _load()
        video = {
            "id": str(uuid.uuid4())[:8],
            "clip_path": clip_path,
            "title": title,
            "channel_id": channel_id,
            "youtube_url": youtube_url,
            "thumbnail": thumbnail,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "status": "published",       # published, scheduled, failed
            "published_at": datetime.now().isoformat(),
        }
        db["posted_videos"].append(video)
        # Atualiza stats do canal
        for ch in db["channels"]:
            if ch["id"] == channel_id:
                ch["videos_posted"] = ch.get("videos_posted", 0) + 1
                break
        _save(db)
        return video


def remove_posted_video(video_id):
    with _lock:
        db = _load()
        before = len(db.get("posted_videos", []))
        db["posted_videos"] = [v for v in db.get("posted_videos", []) if v["id"] != video_id]
        if len(db["posted_videos"]) < before:
            _save(db)
            return True
        return False


def update_posted_video(video_id, **kwargs):
    with _lock:
        db = _load()
        for v in db["posted_videos"]:
            if v["id"] == video_id:
                v.update(kwargs)
                _save(db)
                return v
        return None


# ═══════════════════════════════════════════════
#  CLIPS PARA REVISÃO
# ═══════════════════════════════════════════════

def get_review_clips():
    with _lock:
        db = _load()
        return db.get("review_clips", [])


def add_review_clip(
    queue_id,
    clip_path,
    title,
    channel_id=None,
    reason="",
    youtube_meta=None,
    source_channel_name="",
    source_url="",
):
    with _lock:
        db = _load()
        clip = {
            "id": str(uuid.uuid4())[:8],
            "queue_id": queue_id,
            "clip_path": clip_path,
            "title": title or "Clip sem título",
            "channel_id": channel_id,
            "reason": reason,
            "youtube": youtube_meta or {},
            "source_channel_name": source_channel_name,
            "source_url": source_url,
            "status": "pending",  # pending, published, rejected
            "created_at": datetime.now().isoformat(),
            "published_at": None,
            "rejected_at": None,
        }
        db["review_clips"].append(clip)
        _save(db)
        return clip


def update_review_clip(clip_id, **kwargs):
    with _lock:
        db = _load()
        for clip in db.get("review_clips", []):
            if clip["id"] == clip_id:
                clip.update(kwargs)
                _save(db)
                return clip
        return None


def reject_review_clip(clip_id):
    with _lock:
        db = _load()
        for clip in db.get("review_clips", []):
            if clip["id"] == clip_id:
                clip["status"] = "rejected"
                clip["rejected_at"] = datetime.now().isoformat()
                _save(db)
                return clip
        return None


def publish_review_clip(clip_id, channel_id=None):
    with _lock:
        db = _load()
        for clip in db.get("review_clips", []):
            if clip["id"] != clip_id:
                continue

            publish_channel_id = channel_id or clip.get("channel_id") or db["settings"].get("default_channel_id")
            # Permite publicar mesmo sem canal configurado

            youtube = clip.get("youtube", {})
            video = {
                "id": str(uuid.uuid4())[:8],
                "clip_path": clip.get("clip_path", ""),
                "title": youtube.get("titulo") or clip.get("title") or "Clip",
                "channel_id": publish_channel_id,
                "youtube_url": youtube.get("url", ""),
                "thumbnail": youtube.get("thumbnail", ""),
                "views": 0,
                "likes": 0,
                "comments": 0,
                "status": "published",
                "published_at": datetime.now().isoformat(),
                "description": youtube.get("descricao", ""),
                "hashtags": youtube.get("hashtags", ""),
                "trigger": youtube.get("trigger", ""),
            }
            db["posted_videos"].append(video)

            # Atualiza stats do canal
            for ch in db["channels"]:
                if ch["id"] == publish_channel_id:
                    ch["videos_posted"] = ch.get("videos_posted", 0) + 1
                    break

            clip["status"] = "published"
            clip["channel_id"] = publish_channel_id
            clip["published_at"] = datetime.now().isoformat()

            _save(db)
            return {"clip": clip, "video": video}

        return None


# ═══════════════════════════════════════════════
#  DEFINIÇÕES
# ═══════════════════════════════════════════════

def get_settings():
    with _lock:
        db = _load()
        return db.get("settings", _default_db()["settings"])


def save_settings(settings):
    """Salva um dicionário completo de definições."""
    with _lock:
        db = _load()
        db["settings"] = settings
        _save(db)
        return db["settings"]


def update_settings(**kwargs):
    with _lock:
        db = _load()
        db["settings"].update(kwargs)
        _save(db)
        return db["settings"]


# ═══════════════════════════════════════════════
#  AGENDAMENTO DE UPLOADS
# ═══════════════════════════════════════════════

def get_next_scheduled_slot(channel_id):
    """Calcula e RESERVA atomicamente o próximo slot disponível para agendamento neste canal.
    IMPORTANTE: Esta função já registra o slot automaticamente (operação atômica).
    
    Returns:
        datetime: Timestamp do próximo slot (mínimo: agora + 2 minutos), já registrado
    """
    with _lock:
        db = _load()
        settings = db.get("settings", {})

        if not settings.get("schedule_enabled", True):
            return None

        # Garantir estrutura base
        if "scheduled_uploads" not in db:
            db["scheduled_uploads"] = {}
        if channel_id not in db["scheduled_uploads"]:
            db["scheduled_uploads"][channel_id] = []

        from datetime import datetime, timedelta, timezone

        def _parse_channel_slot_local(ts):
            try:
                return datetime.fromisoformat(ts)
            except Exception:
                return None

        def _parse_publish_utc_to_local(ts):
            if not ts:
                return None
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00").replace(".000+00:00", "+00:00"))
                if dt.tzinfo is not None:
                    return dt.astimezone().replace(tzinfo=None)
                return dt
            except Exception:
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc)
                    return dt.astimezone().replace(tzinfo=None)
                except Exception:
                    return None

        def _build_candidate_slots(start_dt, interval_h, max_per_day, start_time, end_time, days_ahead=60):
            # Constrói uma grelha estável de horários (x em x horas) por janela diária.
            try:
                start_h, start_m = map(int, str(start_time or "08:00").split(":"))
                end_h, end_m = map(int, str(end_time or "22:00").split(":"))
            except Exception:
                start_h, start_m = 8, 0
                end_h, end_m = 22, 0

            interval_h = max(0.5, float(interval_h or 2))
            max_per_day = max(1, int(max_per_day or 12))

            out = []
            day0 = start_dt.date()
            for d in range(days_ahead):
                day = day0 + timedelta(days=d)
                slot = datetime(day.year, day.month, day.day, start_h, start_m, 0, 0)
                produced = 0
                while produced < max_per_day:
                    if slot.hour > end_h or (slot.hour == end_h and slot.minute > end_m):
                        break
                    if slot >= start_dt:
                        out.append(slot)
                    produced += 1
                    next_slot = slot + timedelta(hours=interval_h)
                    if next_slot.date() != day:
                        break
                    slot = next_slot
            return out

        def _is_occupied(candidate, occupied_list, tolerance_seconds=90):
            for occ in occupied_list:
                if abs((candidate - occ).total_seconds()) <= tolerance_seconds:
                    return True
            return False

        now = datetime.now()
        min_slot = now + timedelta(minutes=2)

        # Ocupados = slots reservados + vídeos já agendados no YouTube para este canal.
        occupied = []
        for ts in db.get("scheduled_uploads", {}).get(channel_id, []):
            dt = _parse_channel_slot_local(ts)
            if dt and dt > now:
                occupied.append(dt)

        for video in db.get("posted_videos", []):
            if video.get("channel_id") != channel_id:
                continue
            dt = _parse_publish_utc_to_local(video.get("youtube_publish_at", ""))
            if dt and dt > now:
                occupied.append(dt)

        interval_hours = settings.get("schedule_interval_hours", 2)
        videos_per_day = settings.get("schedule_videos_per_day", 12)
        start_time = settings.get("schedule_start_time", "08:00")
        end_time = settings.get("schedule_end_time", "22:00")

        candidates = _build_candidate_slots(
            start_dt=min_slot,
            interval_h=interval_hours,
            max_per_day=videos_per_day,
            start_time=start_time,
            end_time=end_time,
            days_ahead=120,
        )

        next_slot = None
        for c in candidates:
            if not _is_occupied(c, occupied):
                next_slot = c
                break

        if next_slot is None:
            # Fallback defensivo: se não houver candidatos, usa now + 2 min.
            next_slot = min_slot

        db["scheduled_uploads"][channel_id].append(next_slot.isoformat())

        # Limpeza de lixo antigo
        cutoff = now - timedelta(days=7)
        cleaned = []
        for ts in db["scheduled_uploads"][channel_id]:
            dt = _parse_channel_slot_local(ts)
            if dt and dt > cutoff:
                cleaned.append(ts)
        db["scheduled_uploads"][channel_id] = cleaned

        _save(db)
        return next_slot


def reassign_scheduled_upload_channel(publish_at, from_channel_id, to_channel_id):
    """Move um slot reservado de um canal para outro.

    Usado quando o upload acaba por ser publicado num canal diferente do previsto
    (ex.: rotação de credenciais)."""
    with _lock:
        if not publish_at or not from_channel_id or not to_channel_id or from_channel_id == to_channel_id:
            return {"moved": False, "reason": "noop"}

        db = _load()
        from datetime import datetime

        if "scheduled_uploads" not in db:
            db["scheduled_uploads"] = {}
        if from_channel_id not in db["scheduled_uploads"]:
            db["scheduled_uploads"][from_channel_id] = []
        if to_channel_id not in db["scheduled_uploads"]:
            db["scheduled_uploads"][to_channel_id] = []

        if isinstance(publish_at, datetime):
            target_dt = publish_at
        else:
            try:
                target_dt = datetime.fromisoformat(str(publish_at).replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
            except Exception:
                return {"moved": False, "reason": "invalid_publish_at"}

        moved_out = False
        remaining = []
        for ts in db["scheduled_uploads"].get(from_channel_id, []):
            try:
                dt = datetime.fromisoformat(ts)
            except Exception:
                continue
            if (not moved_out) and abs((dt - target_dt).total_seconds()) <= 120:
                moved_out = True
                continue
            remaining.append(ts)
        db["scheduled_uploads"][from_channel_id] = remaining

        already_exists = False
        for ts in db["scheduled_uploads"].get(to_channel_id, []):
            try:
                dt = datetime.fromisoformat(ts)
                if abs((dt - target_dt).total_seconds()) <= 120:
                    already_exists = True
                    break
            except Exception:
                continue

        if not already_exists:
            db["scheduled_uploads"][to_channel_id].append(target_dt.isoformat())

        _save(db)
        return {"moved": moved_out, "added": (not already_exists), "from": from_channel_id, "to": to_channel_id}


def register_scheduled_upload(channel_id, publish_at):
    """[DEPRECATED] Regista um novo agendamento para este canal.
    NOTA: Use get_next_scheduled_slot() que já faz o registro atomicamente."""
    with _lock:
        db = _load()
        if "scheduled_uploads" not in db:
            db["scheduled_uploads"] = {}
        
        if channel_id not in db["scheduled_uploads"]:
            db["scheduled_uploads"][channel_id] = []
        
        # Adicionar timestamp
        from datetime import datetime
        if isinstance(publish_at, datetime):
            publish_at = publish_at.isoformat()
        
        db["scheduled_uploads"][channel_id].append(publish_at)
        
        # Limpar agendamentos antigos (mais de 7 dias no passado)
        now = datetime.now()
        db["scheduled_uploads"][channel_id] = [
            ts for ts in db["scheduled_uploads"][channel_id]
            if datetime.fromisoformat(ts) > now
        ]
        
        _save(db)
        return publish_at


def clear_old_scheduled_uploads():
    """Remove agendamentos antigos (mais de 24h no passado)."""
    with _lock:
        db = _load()
        from datetime import datetime, timedelta
        now = datetime.now()
        cutoff = now - timedelta(hours=24)
        
        if "scheduled_uploads" not in db:
            return
        
        for channel_id in db["scheduled_uploads"]:
            db["scheduled_uploads"][channel_id] = [
                ts for ts in db["scheduled_uploads"][channel_id]
                if datetime.fromisoformat(ts) > cutoff
            ]
        
        _save(db)


def get_all_scheduled_videos():
    """Retorna todos os vídeos agendados (posted com youtube_publish_at) + slots reservados.
    
    Returns:
        dict com: scheduled_videos (list), scheduled_slots (dict channel_id -> [timestamps]),
                  settings de agendamento
    """
    with _lock:
        db = _load()
        from datetime import datetime
        
        settings = db.get("settings", {})
        
        # Vídeos publicados que têm agendamento
        posted = db.get("posted_videos", [])
        scheduled_videos = []
        for v in posted:
            publish_at = v.get("youtube_publish_at", "")
            if publish_at:
                scheduled_videos.append(v)
        
        # Ordenar por data de agendamento
        def sort_key(v):
            try:
                return datetime.fromisoformat(v.get("youtube_publish_at", "").replace("Z", "+00:00").replace(".000Z", ""))
            except Exception:
                try:
                    return datetime.strptime(v.get("youtube_publish_at", ""), "%Y-%m-%dT%H:%M:%S.000Z")
                except Exception:
                    return datetime.min
        scheduled_videos.sort(key=sort_key)
        
        # Slots reservados no sistema
        slots = db.get("scheduled_uploads", {})
        
        return {
            "scheduled_videos": scheduled_videos,
            "scheduled_slots": slots,
            "schedule_enabled": settings.get("schedule_enabled", True),
            "schedule_interval_hours": settings.get("schedule_interval_hours", 2),
            "schedule_max_per_batch": settings.get("schedule_max_per_batch", 5),
            "schedule_videos_per_day": settings.get("schedule_videos_per_day", 12),
            "schedule_start_time": settings.get("schedule_start_time", "08:00"),
            "schedule_end_time": settings.get("schedule_end_time", "22:00"),
        }


def rearrange_scheduled_slots(channel_id=None, interval_hours=2, videos_per_day=12, start_time="08:00", end_time="22:00"):
    """Reagenda todos os slots futuros segundo os novos parâmetros.
    
    Recalcula os horários de todos os slots e vídeos agendados futuros.
    """
    with _lock:
        db = _load()
        from datetime import datetime, timedelta, timezone
        
        now = datetime.now()
        
        if "scheduled_uploads" not in db:
            db["scheduled_uploads"] = {}
        
        # Parse start/end times
        try:
            start_h, start_m = map(int, start_time.split(":"))
            end_h, end_m = map(int, end_time.split(":"))
        except Exception:
            start_h, start_m = 8, 0
            end_h, end_m = 22, 0
        
        # Determinar canais a processar
        if channel_id:
            channels_to_process = [channel_id]
        else:
            channels_to_process = list(db["scheduled_uploads"].keys())
        
        # Vídeos publicados com agendamento futuro
        posted = db.get("posted_videos", [])
        
        for ch_id in channels_to_process:
            if ch_id not in db["scheduled_uploads"]:
                continue
            
            # Contar quantos slots futuros existem
            future_slots = []
            for ts_str in db["scheduled_uploads"][ch_id]:
                try:
                    dt = datetime.fromisoformat(ts_str)
                    if dt > now:
                        future_slots.append(ts_str)
                except Exception:
                    continue
            
            num_future = len(future_slots)
            if num_future == 0:
                continue
            
            # Recalcular novos slots
            new_slots = []
            current = now + timedelta(minutes=2)
            
            # Ajustar para a hora de início se antes
            if current.hour < start_h or (current.hour == start_h and current.minute < start_m):
                current = current.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            elif current.hour > end_h or (current.hour == end_h and current.minute > end_m):
                # Passar para o dia seguinte
                current = (current + timedelta(days=1)).replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            
            day_count = 0
            current_day = current.date()
            
            for i in range(num_future):
                # Verificar se ultrapassou a hora de fim do dia
                if current.hour > end_h or (current.hour == end_h and current.minute > end_m):
                    current = (current + timedelta(days=1)).replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                    current_day = current.date()
                    day_count = 0
                
                # Verificar se mudou de dia (intervalo cruzou meia-noite)
                if current.date() != current_day:
                    current_day = current.date()
                    day_count = 0
                
                # Verificar se atingiu o máximo por dia
                if day_count >= videos_per_day:
                    current = (current + timedelta(days=1)).replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                    current_day = current.date()
                    day_count = 0
                
                new_slots.append(current.isoformat())
                day_count += 1
                current = current + timedelta(hours=interval_hours)
            
            # Manter slots passados, substituir futuros
            past_slots = [
                ts for ts in db["scheduled_uploads"][ch_id]
                if datetime.fromisoformat(ts) <= now
            ]
            db["scheduled_uploads"][ch_id] = past_slots + new_slots
        
        # Atualizar posted videos com agendamento futuro
        for v in posted:
            publish_at = v.get("youtube_publish_at", "")
            if not publish_at:
                continue
            try:
                pub_dt = datetime.fromisoformat(publish_at.replace("Z", "+00:00").replace(".000Z", ""))
            except Exception:
                try:
                    pub_dt = datetime.strptime(publish_at, "%Y-%m-%dT%H:%M:%S.000Z")
                except Exception:
                    continue
            
            # Só reagendar vídeos com publish_at no futuro e do canal correto
            if pub_dt.replace(tzinfo=None) > now:
                if channel_id and v.get("channel_id") != channel_id:
                    continue
                v["_needs_rearrange"] = True
        
        # Rearranjar posted videos futuros
        rescheduled_videos = []  # Lista de vídeos reagendados para atualizar no YouTube
        future_posted = [v for v in posted if v.get("_needs_rearrange")]
        if future_posted:
            # Agrupar por canal
            by_channel = {}
            for v in future_posted:
                ch = v.get("channel_id", "unknown")
                if ch not in by_channel:
                    by_channel[ch] = []
                by_channel[ch].append(v)
            
            for ch, videos in by_channel.items():
                current = now + timedelta(minutes=2)
                if current.hour < start_h or (current.hour == start_h and current.minute < start_m):
                    current = current.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                elif current.hour > end_h or (current.hour == end_h and current.minute > end_m):
                    current = (current + timedelta(days=1)).replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                
                day_count = 0
                current_day = current.date()
                
                for v in videos:
                    if current.hour > end_h or (current.hour == end_h and current.minute > end_m):
                        current = (current + timedelta(days=1)).replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                        current_day = current.date()
                        day_count = 0
                    if current.date() != current_day:
                        current_day = current.date()
                        day_count = 0
                    if day_count >= videos_per_day:
                        current = (current + timedelta(days=1)).replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                        current_day = current.date()
                        day_count = 0
                    
                    # Converter hora local para UTC para o YouTube
                    local_dt = current.astimezone()  # attach local tz
                    utc_dt = local_dt.astimezone(timezone.utc)
                    new_publish_at = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    v["youtube_publish_at"] = new_publish_at
                    day_count += 1
                    current = current + timedelta(hours=interval_hours)
                    
                    # Guardar info para atualizar no YouTube
                    yt_id = v.get("youtube_video_id")
                    if yt_id:
                        rescheduled_videos.append({
                            "youtube_video_id": yt_id,
                            "youtube_publish_at": new_publish_at,
                            "channel_id": v.get("channel_id"),
                        })
                    
                    del v["_needs_rearrange"]
        
        # Limpar flag de qualquer que não foi processado
        for v in posted:
            v.pop("_needs_rearrange", None)
        
        _save(db)
        return rescheduled_videos


def clear_all_scheduled_slots(channel_id=None):
    """Limpa todos os agendamentos futuros."""
    with _lock:
        db = _load()
        from datetime import datetime
        now = datetime.now()
        
        if "scheduled_uploads" not in db:
            db["scheduled_uploads"] = {}
            _save(db)
            return
        
        if channel_id:
            if channel_id in db["scheduled_uploads"]:
                db["scheduled_uploads"][channel_id] = [
                    ts for ts in db["scheduled_uploads"][channel_id]
                    if datetime.fromisoformat(ts) <= now
                ]
        else:
            for ch_id in db["scheduled_uploads"]:
                db["scheduled_uploads"][ch_id] = [
                    ts for ts in db["scheduled_uploads"][ch_id]
                    if datetime.fromisoformat(ts) <= now
                ]
        
        _save(db)


# ═══════════════════════════════════════════════
#  CANAIS YOUTUBE
# ═══════════════════════════════════════════════
