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
            "ollama_model": "llama2",
            "whisper_model_gpu": "medium",
            "whisper_model_cpu": "small",
            "default_channel_id": None,
            "auto_publish": False,
            "max_clips_per_video": 7,
            "clip_duration_min": 30,
            "clip_duration_max": 60,
            "max_video_duration_min": 60,
        },
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


def update_settings(**kwargs):
    with _lock:
        db = _load()
        db["settings"].update(kwargs)
        _save(db)
        return db["settings"]
