"""
Worker de processamento da queue do ClipAI.
Corre em background thread e processa vídeos da queue sequencialmente.
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import copy
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
        self._cancel_ids = set()  # IDs de vídeos a cancelar
        self._upload_blocked_channels = {}  # {channel_id: datetime} - limite de upload por canal

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

    def cancel(self, item_id):
        """Marca um item para ser cancelado."""
        self._cancel_ids.add(item_id)

    def _is_cancelled(self, item_id):
        """Verifica se um item foi marcado para cancelamento."""
        return item_id in self._cancel_ids

    def _clear_cancelled(self, item_id):
        """Remove um item da lista de cancelamento."""
        self._cancel_ids.discard(item_id)

    def _auto_publish_clip(self, review_clip, channel_id):
        """
        Publica automaticamente um clip no YouTube (upload real).
        Retorna True se sucesso, False se falhar.
        """
        import logging
        import database as db
        
        clip_id = review_clip["id"]
        clip_path = review_clip.get("clip_path", "")
        
        # Verificar se ficheiro existe
        if not os.path.exists(clip_path):
            logging.error(f"   ❌ Ficheiro não encontrado: {clip_path}")
            return False
        
        # Buscar canal
        channels = db.get_channels()
        channel = None
        for ch in channels:
            if ch["id"] == channel_id:
                channel = ch
                break
        
        if not channel:
            logging.error(f"   ❌ Canal não encontrado: {channel_id}")
            return False
        
        # Verificar credenciais OAuth
        creds_path = channel.get("credentials_path", "").strip()
        if not creds_path or not os.path.exists(creds_path):
            logging.warning(f"   ⚠️ Canal sem credenciais OAuth configuradas")
            # Publica localmente sem upload
            db.publish_review_clip(clip_id, channel_id)
            return False
        
        # Marcar como uploading
        db.update_review_clip(clip_id, status="uploading")
        
        try:
            # Importar funções necessárias (dentro do try para evitar dependências circulares)
            import sys
            import importlib
            app_module = sys.modules.get('app')
            if not app_module:
                # Se app não está carregado, importar as funções necessárias
                from google.oauth2.credentials import Credentials
                from google_auth_oauthlib.flow import InstalledAppFlow
                from googleapiclient.discovery import build
                from googleapiclient.http import MediaFileUpload
                
                # Função de autenticação simplificada
                def get_youtube_service_simple(creds_path):
                    import pickle
                    SCOPES = ["https://www.googleapis.com/auth/youtube.upload", 
                             "https://www.googleapis.com/auth/youtube"]
                    
                    creds = None
                    token_path = creds_path.replace(".json", "_token.json")
                    pickle_path = creds_path.replace(".json", "_token.pickle")
                    
                    if os.path.exists(pickle_path):
                        with open(pickle_path, "rb") as token:
                            creds = pickle.load(token)
                    elif os.path.exists(token_path):
                        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
                    
                    if not creds or not creds.valid:
                        if creds and creds.expired and creds.refresh_token:
                            from google.auth.transport.requests import Request
                            creds.refresh(Request())
                        else:
                            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                            creds = flow.run_local_server(port=0)
                        
                        with open(pickle_path, "wb") as f:
                            pickle.dump(creds, f)
                    
                    return build("youtube", "v3", credentials=creds)
                
                service = get_youtube_service_simple(creds_path)
            else:
                # Usar funções do app module
                service, auth_logs = app_module._get_youtube_service(creds_path)
                if not service:
                    logging.error(f"   ❌ Falha na autenticação")
                    db.update_review_clip(clip_id, status="pending")
                    return False
            
            # Preparar metadados — deep copy para isolar de outras referências
            youtube_meta = copy.deepcopy(review_clip.get("youtube", {}))
            title = youtube_meta.get("titulo") or review_clip.get("title") or "Clip"
            description = youtube_meta.get("descricao", "")
            
            # Log detalhado para diagnóstico de off-by-one
            logging.info(f"   📋 Upload metadata: file={os.path.basename(clip_path)}")
            logging.info(f"   📋 titulo='{title[:60]}'")
            logging.info(f"   📋 descricao='{(description or '')[:80]}'")
            
            # Configurações do canal
            privacy = channel.get("default_privacy", "private")
            category = channel.get("default_category", "22")
            
            # Aplicar template de descrição do canal (se existir)
            if channel.get("default_video_description"):
                template = channel["default_video_description"]
                description = template.replace("{titulo}", title).replace("{canal_fonte}",
                    review_clip.get("source_channel_name", "")) + "\n\n" + description
            
            # Adicionar URLs originais à descrição sem duplicar links
            video_url = review_clip.get("source_url") or ""
            source_channel_name = review_clip.get("source_channel_name", "")
            source_channel_url = review_clip.get("source_channel_url", "")

            base_lines = (description or "").split("\n")
            filtered_lines = []
            desc_hashtags = []
            for line in base_lines:
                clean_line = (line or "").strip()
                if clean_line.startswith("#"):
                    desc_hashtags.append(clean_line)
                    continue
                if video_url and video_url in clean_line:
                    continue
                if clean_line.startswith("🎬 Vídeo Original:") or clean_line.startswith("📺 Canal Original:"):
                    continue
                filtered_lines.append(line)

            description = "\n".join(filtered_lines).strip()

            if video_url:
                description += f"\n\n🎬 Vídeo Original: {video_url}"
            if source_channel_url:
                description += f"\n📺 Canal Original: {source_channel_url}"
            elif source_channel_name:
                channel_url = f"https://www.youtube.com/@{source_channel_name.replace(' ', '')}"
                description += f"\n📺 Canal Original: {channel_url}"

            # Tags
            default_tags = channel.get("default_tags", "")
            tags = [t.strip() for t in default_tags.split(",") if t.strip()]

            # Hashtags das tags padrão para a descrição
            default_tags_hashtags = []
            for tag in tags:
                raw = tag.lstrip("#").strip().replace(" ", "")
                normalized = "".join(ch for ch in raw if ch.isalnum() or ch == "_")
                if normalized:
                    default_tags_hashtags.append(f"#{normalized}")

            all_desc_hashtags = list(dict.fromkeys(desc_hashtags + default_tags_hashtags))
            if all_desc_hashtags:
                description += "\n\n" + " ".join(all_desc_hashtags)
            
            logging.info(f"   📤 Fazendo upload para o YouTube...")
            
            # Upload do vídeo
            if app_module:
                video_id, url, upload_logs = app_module._upload_video_to_youtube(
                    service, clip_path, title, description, tags, category, privacy
                )
            else:
                # Upload simplificado inline
                from googleapiclient.http import MediaFileUpload
                
                body = {
                    "snippet": {
                        "title": title[:100],
                        "description": description[:5000],
                        "tags": tags,
                        "categoryId": category,
                    },
                    "status": {
                        "privacyStatus": privacy,
                        "selfDeclaredMadeForKids": False,
                    },
                }
                
                media = MediaFileUpload(clip_path, chunksize=1024 * 1024, resumable=True)
                req = service.videos().insert(part="snippet,status", body=body, media_body=media)
                
                response = None
                last_logged_pct = 0
                while response is None:
                    status_obj, response = req.next_chunk()
                    if status_obj:
                        pct = int(status_obj.progress() * 100)
                        if pct >= last_logged_pct + 20:
                            logging.info(f"   📤 Upload: {pct}%")
                            last_logged_pct = pct
                
                video_id = response.get("id", "")
                url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
            
            if not video_id:
                logging.error(f"   ❌ Upload falhou - sem video_id")
                db.update_review_clip(clip_id, status="pending")
                return False
            
            # Atualizar metadados do YouTube no clip via DB (sem mutar referências locais)
            db.update_review_clip(clip_id, youtube_url=url, youtube_video_id=video_id)
            
            # Publicar na BD com os dados reais do YouTube
            result = db.publish_review_clip(clip_id, channel_id)
            
            if result and result.get("video"):
                # Atualizar o vídeo publicado com a URL real
                db.update_posted_video(result["video"]["id"], youtube_url=url)
            
            return True
            
        except Exception as e:
            err_str = str(e)
            # Detectar limite de uploads do YouTube
            if 'uploadLimitExceeded' in err_str or 'exceeded the number of videos' in err_str:
                import logging as _log
                cooldown_hours = 6
                blocked_until = datetime.now() + __import__('datetime').timedelta(hours=cooldown_hours)
                self._upload_blocked_channels[channel_id] = blocked_until
                _log.warning(f"🚫 Limite de uploads do YouTube atingido no canal {channel_id}! Uploads pausados até {blocked_until.strftime('%H:%M')}")
                db.update_review_clip(clip_id, status="pending")
                return False
            
            logging.error(f"   ❌ Erro no upload automático: {e}")
            import traceback
            logging.error(traceback.format_exc())
            db.update_review_clip(clip_id, status="pending")
            return False

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

            # ── Verificar cancelamento ──
            if self._is_cancelled(item_id):
                db.update_queue_item(item_id, status="cancelled",
                                     progress=0,
                                     status_detail="Cancelado pelo utilizador",
                                     finished_at=datetime.now().isoformat())
                self._clear_cancelled(item_id)
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "cancelled")
                return

            # ── ETAPA 1: DOWNLOAD ──
            db.update_queue_item(item_id, status="downloading", progress=5,
                                 status_detail="A iniciar download...",
                                 started_at=datetime.now().isoformat())

            import logging
            logging.info(f"📥 INICIANDO DOWNLOAD: {item.get('title', 'Sem título')}")
            logging.info(f"   URL: {item['url']}")

            from modulo1_download import baixar_video_youtube
            safe_name = f"queue_{item_id}"
            
            # Callback para atualizar progresso do download
            def download_progress_callback(pct):
                # Progresso: 5-25% para download
                progress = 5 + int(pct * 0.20)  # 20% do range total
                db.update_queue_item(item_id, progress=progress, status_detail=f"A descarregar: {pct}%")
                if pct % 10 == 0:  # Log a cada 10%
                    logging.info(f"   ⬇️  Download: {pct}%")
            
            caminho_video = baixar_video_youtube(item["url"], safe_name, progress_callback=download_progress_callback)

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
            duration_seconds = None
            
            try:
                import subprocess as _sp
                r = _sp.run(
                    ["ffprobe", "-v", "quiet", "-show_entries",
                     "format=duration", "-of", "csv=p=0", caminho_video],
                    capture_output=True, text=True, timeout=30
                )
                dur_sec = float(r.stdout.strip() or "0")
                duration_seconds = dur_sec
                dur_min = dur_sec / 60
                
                # Guarda a duração
                db.update_queue_item(item_id, duration_seconds=int(dur_sec))
                
                if max_dur_min > 0 and dur_min > max_dur_min:
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
            logging.info(f"✅ DOWNLOAD CONCLUÍDO: {os.path.basename(caminho_video)} ({tamanho/(1024*1024):.1f}MB)")

            # ── Verificar cancelamento ──
            if self._is_cancelled(item_id):
                db.update_queue_item(item_id, status="cancelled",
                                     progress=25,
                                     status_detail="Cancelado pelo utilizador",
                                     finished_at=datetime.now().isoformat())
                self._clear_cancelled(item_id)
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "cancelled")
                return

            # ── ETAPA 2: ANÁLISE ──
            db.update_queue_item(item_id, status="analyzing", progress=30,
                                 status_detail="A extrair áudio...")

            logging.info(f"🎤 INICIANDO TRANSCRIÇÃO...")

            from modulo2_analise import extrair_audio_do_video, transcrever_audio_whisper, analisar_com_ollama, salvar_analise

            caminho_audio = extrair_audio_do_video(caminho_video)
            logging.info(f"   ✅ Áudio extraído")
            if not caminho_audio:
                db.update_queue_item(item_id, status="error", error_msg="Falha ao extrair áudio",
                                     finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            db.update_queue_item(item_id, progress=40, status_detail="A transcrever com Whisper...")

            # Callback para progresso da transcrição
            def transcribe_progress_callback(pct, detail=""):
                # Progresso: 40-55% para transcrição
                progress = 40 + int(pct * 0.15)  # 15% do range total
                status = f"Whisper: {pct}%" + (f" - {detail}" if detail else "")
                db.update_queue_item(item_id, progress=progress, status_detail=status)
                if pct % 20 == 0:
                    logging.info(f"   🗣️  Transcrição: {pct}% {detail}")

            transcricao = transcrever_audio_whisper(caminho_audio, progress_callback=transcribe_progress_callback)
            if not transcricao:
                db.update_queue_item(item_id, status="error", error_msg="Falha na transcrição",
                                     finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            # Passa a URL original para a análise (para incluir no copy YouTube)
            try:
                original_video_url = item.get("origin_url") or item.get("url", "")
                original_channel_name = item.get("origin_channel_name") or item.get("source_channel_name", "")
                original_channel_url = item.get("origin_channel_url") or ""

                transcricao["video_url"] = original_video_url
                transcricao["source_channel_name"] = original_channel_name
                transcricao["source_channel_url"] = original_channel_url
            except Exception:
                pass

            # Liberta VRAM do Whisper antes de chamar o Ollama
            # Sem isto, Whisper fica com ~2GB na GPU e o Llama offloads para CPU (10x lento)
            try:
                from modulo2_analise import liberar_gpu_whisper
                liberar_gpu_whisper()
            except Exception:
                pass

            db.update_queue_item(item_id, progress=55, status_detail="A analisar com Llama...")
            logging.info(f"🤖 INICIANDO ANÁLISE IA...")

            cfg_worker = db.get_settings()
            ollama_model = cfg_worker.get("ollama_model") or "llama3.1"
            
            # Callback para progresso da análise
            def analyze_progress_callback(pct, detail=""):
                # Progresso: 55-65% para análise
                progress = 55 + int(pct * 0.10)  # 10% do range total
                status = f"Llama: {pct}%" + (f" - {detail}" if detail else "")
                db.update_queue_item(item_id, progress=progress, status_detail=status)
                if pct % 25 == 0:
                    logging.info(f"   🧠 Análise IA: {pct}% {detail}")
            
            clipes_recomendados = analisar_com_ollama(transcricao, modelo=ollama_model, progress_callback=analyze_progress_callback)
            if not clipes_recomendados:
                db.update_queue_item(item_id, status="error", error_msg="Falha na análise com Llama",
                                     finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            salvar_analise(clipes_recomendados)
            db.update_queue_item(item_id, progress=65, status_detail="Análise concluída",
                                 clips_total=len(clipes_recomendados))
            logging.info(f"✅ ANÁLISE CONCLUÍDA: {len(clipes_recomendados)} clips encontrados")

            # ── Verificar cancelamento ──
            if self._is_cancelled(item_id):
                db.update_queue_item(item_id, status="cancelled",
                                     progress=65,
                                     status_detail="Cancelado pelo utilizador",
                                     finished_at=datetime.now().isoformat())
                self._clear_cancelled(item_id)
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "cancelled")
                return

            # ── ETAPA 3: EDIÇÃO ──
            db.update_queue_item(item_id, status="editing", progress=70,
                                 status_detail="A editar clipes...")

            logging.info(f"🎬 INICIANDO EDIÇÃO...")

            from modulo3_edicao import ler_analise_clipes, editar_clipes, salvar_lista_clips

            clipes = ler_analise_clipes()
            if not clipes:
                db.update_queue_item(item_id, status="error", error_msg="Falha ao ler análise",
                                     finished_at=datetime.now().isoformat())
                if source_video_id:
                    db.set_recent_video_clip_status(source_video_id, "error")
                return

            segmentos_whisper = transcricao.get("segmentos", [])
            
            # Callback para progresso da edição
            def edit_progress_callback(clip_idx, total_clips, pct, detail=""):
                # Progresso: 70-100% para edição (30% do range)
                clip_progress = (clip_idx / total_clips) * 100
                overall_pct = 70 + (clip_progress * 0.30)
                status = f"Editando clip {clip_idx}/{total_clips}: {pct}%" + (f" - {detail}" if detail else "")
                db.update_queue_item(item_id, progress=int(overall_pct), status_detail=status)
                if pct in [0, 50, 100]:
                    logging.info(f"   ✂️  Clip {clip_idx}/{total_clips}: {pct}% {detail}")
            
            clipes_editados = editar_clipes(caminho_video, clipes, segmentos_whisper, progress_callback=edit_progress_callback)

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

            logging.info(f"🎬 {len(clipes_editados)} clips editados")
            if auto_publish:
                logging.info(f"🤖 AUTO-PUBLICAÇÃO ATIVADA")
                if target_channel_id:
                    logging.info(f"   Canal de destino: {target_channel_id}")
                else:
                    logging.warning(f"   ⚠️ Nenhum canal configurado - clips irão para revisão")

            # Guarda info dos clips no item
            clips_info = []
            for idx, c in enumerate(clipes_editados, 1):
                review_source_url = item.get("origin_url") or item.get("url", "")
                review_source_channel_name = item.get("origin_channel_name") or item.get("source_channel_name", "")
                review_source_channel_url = item.get("origin_channel_url", "")

                # ── Deep copy youtube meta para isolar cada clip ──
                # Previne que mutações (ex: youtube_meta["url"] = ...) de um clip
                # vazem para o próximo via referência partilhada.
                clip_youtube_meta = copy.deepcopy(c.get("youtube", {}))
                clip_title = clip_youtube_meta.get("titulo") or c.get("titulo", "")
                clip_path = c.get("arquivo", "")

                logging.info(f"   📋 Clip {idx}: ficheiro={os.path.basename(clip_path)} titulo='{clip_title[:50]}'")

                review_clip = db.add_review_clip(
                    queue_id=item_id,
                    clip_path=clip_path,
                    title=clip_title,
                    channel_id=target_channel_id,
                    reason=c.get("razao", ""),
                    youtube_meta=clip_youtube_meta,
                    source_channel_name=review_source_channel_name,
                    source_url=review_source_url,
                )

                if review_clip and review_source_channel_url:
                    db.update_review_clip(review_clip["id"], source_channel_url=review_source_channel_url)

                # AUTO-PUBLICAÇÃO: Fazer upload real ao YouTube
                if auto_publish and target_channel_id and review_clip:
                    # Verificar se uploads estão bloqueados por limite do YouTube (por canal)
                    blocked_until = self._upload_blocked_channels.get(target_channel_id)
                    if blocked_until and datetime.now() < blocked_until:
                        remaining = (blocked_until - datetime.now()).seconds // 60
                        logging.warning(f"   🚫 Canal {target_channel_id} bloqueado (limite YouTube) - retoma em {remaining}min. Clip vai para revisão.")
                        continue
                    elif blocked_until:
                        # Limite expirou, limpar
                        del self._upload_blocked_channels[target_channel_id]
                    
                    logging.info(f"📤 [{idx}/{len(clipes_editados)}] A publicar: {review_clip['title'][:50]}...")
                    logging.info(f"   📝 Descrição (100 chars): {clip_youtube_meta.get('descricao', '')[:100]}")
                    
                    try:
                        # Tentar fazer upload real ao YouTube
                        upload_success = self._auto_publish_clip(review_clip, target_channel_id)
                        
                        if upload_success:
                            logging.info(f"   ✅ Clip publicado com sucesso no YouTube!")
                        else:
                            logging.warning(f"   ⚠️ Upload falhou - clip movido para revisão manual")
                        
                        # Pausa entre uploads para evitar race conditions no YouTube API
                        if idx < len(clipes_editados):
                            logging.info(f"   ⏳ Aguardando 3s antes do próximo upload...")
                            time.sleep(3)
                            
                    except Exception as e:
                        logging.error(f"   ❌ Erro ao publicar clip: {e}")
                        # Se falhar, deixa na revisão para tentar manualmente
                        pass

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
            
            logging.info(f"🎉 PROCESSAMENTO CONCLUÍDO: {len(clipes_editados)} clips editados")
            if auto_publish and target_channel_id:
                logging.info(f"   📤 Auto-publicação executada - verifique os logs de upload acima")
            elif auto_publish and not target_channel_id:
                logging.info(f"   ℹ️ Clips movidos para revisão (nenhum canal configurado)")

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
