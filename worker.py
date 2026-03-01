"""
Worker de processamento da queue do ClipAI.
Corre em background thread e processa vídeos da queue sequencialmente.
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import threading
import time
import traceback
from datetime import datetime

import database as db


class QueueWorker:
    """Processa vídeos da queue em background."""

    def __init__(self):
        self._thread = None
        self._running = False
        self._paused = False
        self._current_id = None

    @property
    def is_running(self):
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def is_paused(self):
        return self._paused

    def start(self):
        if self.is_running:
            return
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def _loop(self):
        while self._running:
            if self._paused:
                time.sleep(2)
                continue

            # Encontra o próximo item na queue
            queue = db.get_queue()
            next_item = None
            for item in queue:
                if item["status"] == "queued":
                    next_item = item
                    break

            if not next_item:
                time.sleep(3)
                continue

            self._current_id = next_item["id"]
            self._process_video(next_item)
            self._current_id = None

    def _process_video(self, item):
        """Processa um vídeo: download -> análise -> edição."""
        item_id = item["id"]
        source_video_id = item.get("source_video_id")

        try:
            # ── Verificar dependências antes de começar ──
            missing = []
            try:
                import torch
            except ImportError:
                missing.append("torch (PyTorch)")
            try:
                import faster_whisper
            except ImportError:
                missing.append("faster-whisper")
            try:
                import ollama
            except ImportError:
                missing.append("ollama")
            try:
                import yt_dlp
            except ImportError:
                missing.append("yt-dlp")

            if missing:
                db.update_queue_item(
                    item_id, status="error",
                    error_msg=f"Módulos em falta: {', '.join(missing)}. Instala com: pip install {' '.join(m.split('(')[0].strip() for m in missing)}",
                    status_detail=f"Faltam dependências: {', '.join(missing)}",
                    finished_at=datetime.now().isoformat(),
                )
                return

            # ── ETAPA 1: DOWNLOAD ──
            db.update_queue_item(item_id, status="downloading", progress=5,
                                 status_detail="A iniciar download...",
                                 started_at=datetime.now().isoformat())

            from modulo1_download import baixar_video_youtube
            safe_name = f"queue_{item_id}"
            caminho_video = baixar_video_youtube(item["url"], safe_name)

            if not caminho_video or not os.path.exists(caminho_video):
                db.update_queue_item(item_id, status="error",
                                     error_msg="Falha no download — ficheiro não criado",
                                     progress=0, finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            # Valida que o ficheiro não está corrompido
            tamanho = os.path.getsize(caminho_video)
            if tamanho < 50000:
                db.update_queue_item(item_id, status="error",
                                     error_msg=f"Download corrompido ({tamanho} bytes)",
                                     progress=0, finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            # ── Verifica duração máxima ──
            settings = db.get_settings()
            max_dur_min = int(settings.get("max_video_duration_min") or 0)
            if max_dur_min > 0:
                try:
                    import subprocess as _sp
                    r = _sp.run(
                        ["ffprobe", "-v", "quiet", "-show_entries",
                         "format=duration", "-of", "csv=p=0", caminho_video],
                        capture_output=True, text=True, timeout=30
                    )
                    dur_sec = float(r.stdout.strip() or "0")
                    dur_min = dur_sec / 60
                    if dur_min > max_dur_min:
                        db.update_queue_item(
                            item_id, status="error",
                            error_msg=f"Vídeo demasiado longo: {dur_min:.1f} min (máx: {max_dur_min} min)",
                            status_detail="Vídeo excede o limite de duração",
                            finished_at=datetime.now().isoformat(),
                        )
                        if source_video_id:
                            db.set_recent_video_clip_status(source_video_id, "error")
                        return
                except Exception:
                    pass  # Se ffprobe falhar, continua de qualquer forma

            db.update_queue_item(item_id, progress=25, status_detail="Download concluído")

            # ── ETAPA 2: ANÁLISE ──
            db.update_queue_item(item_id, status="analyzing", progress=30,
                                 status_detail="A extrair áudio...")

            from modulo2_analise import extrair_audio_do_video, transcrever_audio_whisper, analisar_com_ollama, salvar_analise

            caminho_audio = extrair_audio_do_video(caminho_video)
            if not caminho_audio:
                db.update_queue_item(item_id, status="error", error_msg="Falha ao extrair áudio",
                                     finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            db.update_queue_item(item_id, progress=40, status_detail="A transcrever com Whisper...")

            transcricao = transcrever_audio_whisper(caminho_audio)
            if not transcricao:
                db.update_queue_item(item_id, status="error", error_msg="Falha na transcrição",
                                     finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            # Passa a URL original para a análise (para incluir no copy YouTube)
            try:
                transcricao["video_url"] = item.get("url", "")
            except Exception:
                pass

            db.update_queue_item(item_id, progress=55, status_detail="A analisar com Llama...")

            cfg_worker = db.get_settings()
            ollama_model = cfg_worker.get("ollama_model") or "llama3.1"
            clipes_recomendados = analisar_com_ollama(transcricao, modelo=ollama_model)
            if not clipes_recomendados:
                db.update_queue_item(item_id, status="error", error_msg="Falha na análise com Llama",
                                     finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            salvar_analise(clipes_recomendados)
            db.update_queue_item(item_id, progress=65, status_detail="Análise concluída",
                                 clips_total=len(clipes_recomendados))

            # ── ETAPA 3: EDIÇÃO ──
            db.update_queue_item(item_id, status="editing", progress=70,
                                 status_detail="A editar clipes...")

            from modulo3_edicao import ler_analise_clipes, editar_clipes, salvar_lista_clips

            clipes = ler_analise_clipes()
            if not clipes:
                db.update_queue_item(item_id, status="error", error_msg="Falha ao ler análise",
                                     finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            segmentos_whisper = transcricao.get("segmentos", [])
            clipes_editados = editar_clipes(caminho_video, clipes, segmentos_whisper)

            if not clipes_editados:
                db.update_queue_item(item_id, status="error", error_msg="Nenhum clipe editado",
                                     finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            salvar_lista_clips(clipes_editados)

            settings = db.get_settings()
            # Por item: auto_publish override; se None usa o global
            item_auto_publish = item.get("auto_publish")
            if item_auto_publish is None:
                item_auto_publish = bool(settings.get("auto_publish", False))
            auto_publish = bool(item_auto_publish)
            default_channel_id = settings.get("default_channel_id")
            target_channel_id = item.get("channel_id") or default_channel_id

            # Guarda info dos clips no item
            clips_info = []
            for c in clipes_editados:
                review_clip = db.add_review_clip(
                    queue_id=item_id,
                    clip_path=c.get("arquivo", ""),
                    title=c.get("youtube", {}).get("titulo") or c.get("titulo", ""),
                    channel_id=target_channel_id,
                    reason=c.get("razao", ""),
                    youtube_meta=c.get("youtube", {}),
                )

                if auto_publish and target_channel_id and review_clip:
                    db.publish_review_clip(review_clip["id"], target_channel_id)

                clips_info.append({
                    "numero": c.get("numero"),
                    "arquivo": c.get("arquivo", ""),
                    "titulo": c.get("titulo", ""),
                })

            db.update_queue_item(
                item_id,
                status="done",
                progress=100,
                status_detail="Concluído!",
                clips_done=len(clipes_editados),
                clips_total=len(clipes_editados),
                clips=clips_info,
                finished_at=datetime.now().isoformat(),
            )
            if source_video_id:
                db.set_recent_video_clip_status(source_video_id, "done")

        except Exception as e:
            db.update_queue_item(
                item_id,
                status="error",
                error_msg=str(e),
                status_detail=f"Erro: {str(e)[:100]}",
                finished_at=datetime.now().isoformat(),
            )
            if source_video_id:
                db.set_recent_video_clip_status(source_video_id, "error")
            traceback.print_exc()


# Instância global
worker = QueueWorker()
