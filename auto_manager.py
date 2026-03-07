"""
Auto Manager - Gerencia automaticamente espaço em disco e downloads de playlists
"""

import os
import json
import glob
import time
import threading
import logging
from datetime import datetime, timedelta
import yt_dlp
import io
import sys

import database as db

# Ficheiro para rastrear vídeos já descarregados pelo AutoManager
_DOWNLOADED_TRACKER = os.path.join("data", "auto_downloaded.json")
_AUTO_DOWNLOADS_DIR = os.path.join("downloads", "auto")
_FAILED_VIDEOS_TRACKER = os.path.join("data", "auto_failed_videos.json")

# Logger do yt-dlp - vai suprimir mensagens repetidas
_YDL_LOGGER = logging.getLogger('yt_dlp')
_YDL_LOGGER.setLevel(logging.CRITICAL)  # Apenas erros críticos, nada mais

# Desabilitar a propagação de logs verbose do yt-dlp
logging.getLogger('yt_dlp.utils').setLevel(logging.CRITICAL)
logging.getLogger('yt_dlp.extractor.youtube').setLevel(logging.CRITICAL)


def _load_downloaded_ids():
    """Carrega IDs de vídeos já descarregados."""
    try:
        if os.path.exists(_DOWNLOADED_TRACKER):
            with open(_DOWNLOADED_TRACKER, "r", encoding="utf-8") as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()


def _save_downloaded_ids(ids_set):
    """Salva IDs de vídeos já descarregados."""
    try:
        os.makedirs(os.path.dirname(_DOWNLOADED_TRACKER), exist_ok=True)
        with open(_DOWNLOADED_TRACKER, "w", encoding="utf-8") as f:
            json.dump(list(ids_set), f)
    except Exception as e:
        logging.error(f"❌ Erro ao salvar tracker: {e}")


def _load_failed_videos():
    """Carrega dict de vídeos que falharam (com razão do erro)."""
    try:
        if os.path.exists(_FAILED_VIDEOS_TRACKER):
            with open(_FAILED_VIDEOS_TRACKER, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_failed_videos(failed_dict):
    """Salva dict de vídeos que falharam."""
    try:
        os.makedirs(os.path.dirname(_FAILED_VIDEOS_TRACKER), exist_ok=True)
        with open(_FAILED_VIDEOS_TRACKER, "w", encoding="utf-8") as f:
            json.dump(failed_dict, f)
    except Exception as e:
        logging.debug(f"Erro ao salvar failed_videos: {e}")


class _SilentYDLLogger:
    """Logger customizado para yt-dlp que suprime erros de bot-detection repetidos."""
    
    def __init__(self, suppress_keywords=None):
        self.suppress_keywords = suppress_keywords or [
            'Sign in to confirm',
            'bot',
            'cookies',
            'authentication',
            'age-gated'
        ]
        self.error_cache = {}  # {video_id: count}
        self.MAX_SAME_ERROR = 2  # Máximo de vezes que imprime o mesmo erro
    
    def debug(self, msg):
        pass  # Ignorar debug messages
    
    def info(self, msg):
        pass  # Ignorar info messages
    
    def warning(self, msg):
        pass  # Ignorar warning messages
    
    def error(self, msg):
        """Suprime erros de bot-detection repetidos."""
        # Verificar se é um dos erros que devemos suprimir
        should_suppress = any(kw.lower() in msg.lower() for kw in self.suppress_keywords)
        
        if should_suppress:
            # Extrair video ID do erro se possível
            vid_id = None
            if '[youtube]' in msg:
                parts = msg.split('[youtube]')
                if len(parts) > 1:
                    vid_info = parts[1].strip().split(':')[0]
                    vid_id = vid_info.strip()
            
            # Contar quantas vezes vimos este erro
            cache_key = vid_id or 'generic'
            count = self.error_cache.get(cache_key, 0)
            
            # Só imprimir na primeira ou segunda ocorrência
            if count < self.MAX_SAME_ERROR:
                # Versão simplificada do erro
                if vid_id:
                    logging.debug(f"⚠️ Vídeo {vid_id}: {msg.split(':')[1] if ':' in msg else 'erro de autenticação - skipando'}")
                self.error_cache[cache_key] = count + 1
            # Senão, silenciar completamente
        else:
            # Erros importantes não relacionados a bot-detection - imprimir
            logging.warning(f"[yt-dlp] {msg}")


class _NullWriter(io.StringIO):
    """Writer que descarta output (para suprimir stderr do yt-dlp)."""
    def write(self, s):
        return len(s)
    
    def flush(self):
        pass


class AutoManager:
    """Gerencia automaticamente limpeza de vídeos e download de playlists."""
    
    def __init__(self, playlist_url=None, max_storage_mb=5000, check_interval_minutes=15):
        """
        Args:
            playlist_url: URL da playlist do YouTube para baixar automaticamente
            max_storage_mb: Limite de armazenamento em MB (default: 5GB)
            check_interval_minutes: Intervalo entre verificações (default: 15 min)
        """
        self.playlist_url = playlist_url
        self.max_storage_mb = max_storage_mb
        self.check_interval = check_interval_minutes * 60  # converter para segundos
        self._running = False
        self._thread = None
        
    def start(self):
        """Inicia o gerenciamento automático."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logging.info(f"🤖 AutoManager iniciado (limpeza + playlist automática)")
        if self.playlist_url:
            logging.info(f"   📺 Playlist: {self.playlist_url}")
    
    def stop(self):
        """Para o gerenciamento automático."""
        self._running = False
        logging.info("🛑 AutoManager parado")
    
    def _loop(self):
        """Loop principal do AutoManager."""
        while self._running:
            try:
                # 1. Limpar vídeos antigos se necessário
                self._cleanup_old_videos()
                
                # 2. Adicionar novos vídeos da playlist se houver espaço
                if self.playlist_url:
                    self._add_videos_from_playlist()
                
            except Exception as e:
                logging.error(f"❌ Erro no AutoManager: {e}")
            
            # Aguardar próxima verificação
            time.sleep(self.check_interval)
    
    def _cleanup_old_videos(self):
        """Remove vídeos antigos para liberar espaço."""
        downloads_folder = "downloads"
        
        # Calcular tamanho atual
        total_size_mb = self._get_folder_size_mb(downloads_folder)
        
        if total_size_mb < self.max_storage_mb:
            logging.debug(f"💾 Espaço OK: {total_size_mb:.0f}MB / {self.max_storage_mb}MB")
            return
        
        logging.info(f"⚠️ Limite de armazenamento atingido: {total_size_mb:.0f}MB / {self.max_storage_mb}MB")
        logging.info("🗑️ Iniciando limpeza automática...")
        
        deleted_count = 0
        freed_mb = 0
        target_mb = self.max_storage_mb * 0.8  # Liberar até 80% do limite

        # 1. Primeiro limpar vídeos auto-descarregados (mais antigos primeiro)
        if os.path.exists(_AUTO_DOWNLOADS_DIR):
            auto_files = []
            for f in os.listdir(_AUTO_DOWNLOADS_DIR):
                fp = os.path.join(_AUTO_DOWNLOADS_DIR, f)
                if os.path.isfile(fp) and f.endswith(('.mp4', '.webm', '.mkv')):
                    auto_files.append((fp, os.path.getmtime(fp), os.path.getsize(fp)))
            # Ordenar por data de modificação (mais antigo primeiro)
            auto_files.sort(key=lambda x: x[1])
            
            for filepath, _, size in auto_files:
                if total_size_mb - freed_mb < target_mb:
                    break
                try:
                    size_mb = size / (1024 * 1024)
                    os.remove(filepath)
                    freed_mb += size_mb
                    deleted_count += 1
                    logging.info(f"   🗑️ Removido: {os.path.basename(filepath)} ({size_mb:.1f}MB)")
                except Exception as e:
                    logging.error(f"   ❌ Erro ao remover {filepath}: {e}")

        # 2. Depois limpar vídeos da queue (concluídos/erros)
        if total_size_mb - freed_mb >= target_mb:
            queue = db.get_queue()
            done_items = [q for q in queue if q.get("status") in ("done", "error")]
            done_items.sort(key=lambda x: x.get("finished_at", ""), reverse=False)
            
            for item in done_items:
                if total_size_mb - freed_mb < target_mb:
                    break
                video_pattern = os.path.join(downloads_folder, f"queue_{item['id']}.*")
                for video_file in glob.glob(video_pattern):
                    if video_file.endswith(('.mp4', '.webm', '.mkv')):
                        try:
                            size_mb = os.path.getsize(video_file) / (1024 * 1024)
                            os.remove(video_file)
                            freed_mb += size_mb
                            deleted_count += 1
                            logging.info(f"   🗑️ Removido: {os.path.basename(video_file)} ({size_mb:.1f}MB)")
                        except Exception as e:
                            logging.error(f"   ❌ Erro ao remover {video_file}: {e}")
        
        if deleted_count > 0:
            logging.info(f"✅ Limpeza concluída: {deleted_count} vídeos removidos, {freed_mb:.1f}MB liberados")
        else:
            logging.info("ℹ️ Nenhum vídeo para remover")
    
    def _get_folder_size_mb(self, folder):
        """Calcula o tamanho total de uma pasta em MB."""
        total = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder):
                for filename in filenames:
                    if filename.endswith(('.mp4', '.webm', '.mkv')):
                        filepath = os.path.join(dirpath, filename)
                        try:
                            total += os.path.getsize(filepath)
                        except Exception:
                            pass
        except Exception:
            pass
        return total / (1024 * 1024)
    
    def _add_videos_from_playlist(self):
        """Descarrega novos vídeos da playlist diretamente (sem aparecer na queue/UI)."""
        try:
            # Criar pasta de downloads automáticos
            os.makedirs(_AUTO_DOWNLOADS_DIR, exist_ok=True)

            # Carregar IDs já descarregados e falhados
            downloaded_ids = _load_downloaded_ids()
            failed_videos = _load_failed_videos()

            # Verificar espaço disponível
            total_size_mb = self._get_folder_size_mb("downloads")
            if total_size_mb >= self.max_storage_mb:
                logging.debug(f"💾 Limite de armazenamento atingido ({total_size_mb:.0f}MB / {self.max_storage_mb}MB), a limpar primeiro...")
                return

            # Buscar vídeos da playlist
            logging.debug(f"🔍 Verificando playlist para novos vídeos...")

            ydl_opts_list = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'playlistend': 20,
                'socket_timeout': 20,
                'logger': _SilentYDLLogger(),  # Logger customizado
            }

            with yt_dlp.YoutubeDL(ydl_opts_list) as ydl:
                info = ydl.extract_info(self.playlist_url, download=False)

                if not info or 'entries' not in info:
                    logging.warning(f"⚠️ Playlist vazia ou inacessível: {self.playlist_url[:50]}...")
                    return

                entries = [e for e in info['entries'] if e]

                if not entries:
                    logging.warning(f"⚠️ Nenhum vídeo encontrado na playlist")
                    return

                # Filtrar vídeos que ainda não foram descarregados E não falharam por bot-detection
                new_entries = []
                for entry in entries:
                    vid_id = entry.get('id', '')
                    if vid_id and vid_id not in downloaded_ids:
                        # ✅ NOVO: Skippar vídeos que falharam por bot-detection
                        if vid_id in failed_videos:
                            fail_reason = failed_videos[vid_id]
                            if 'bot' in fail_reason.lower() or 'authentication' in fail_reason.lower():
                                logging.debug(f"⏭️  Skipando {vid_id} (falha anterior: {fail_reason[:40]}...)")
                                continue
                        
                        duration = entry.get('duration') or 0
                        # Filtrar vídeos muito curtos ou muito longos
                        if duration == 0 or (60 <= duration <= 1200):
                            new_entries.append(entry)

                if not new_entries:
                    logging.debug("✅ Nenhum vídeo novo na playlist")
                    return

                # Descarregar até 2 vídeos por ciclo
                download_count = 0
                for entry in new_entries[:2]:
                    if not self._running:
                        break

                    # Verificar espaço antes de cada download
                    current_size = self._get_folder_size_mb("downloads")
                    if current_size >= self.max_storage_mb:
                        logging.info(f"💾 Limite atingido ({current_size:.0f}MB), parando downloads")
                        break

                    vid_id = entry['id']
                    title = entry.get('title', 'Sem título')
                    video_url = f"https://www.youtube.com/watch?v={vid_id}"
                    safe_name = f"auto_{vid_id}"
                    output_path = os.path.join(_AUTO_DOWNLOADS_DIR, f"{safe_name}.mp4")

                    logging.debug(f"⬇️  AutoManager a descarregar: {title}")

                    try:
                        ydl_opts_dl = {
                            'format': (
                                'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/'
                                'bestvideo[height<=1080]+bestaudio/'
                                'bestvideo+bestaudio/'
                                'best[ext=mp4]/best'
                            ),
                            'merge_output_format': 'mp4',
                            'outtmpl': output_path,
                            'quiet': True,
                            'no_warnings': True,
                            'noprogress': True,
                            'socket_timeout': 30,
                            'retries': 2,  # Reduzido de 3 para 2 (menos tentativas = menos erro spam)
                            'fragment_retries': 2,  # Reduzido de 3 para 2
                            'file_access_retries': 10,      # Windows file lock fix
                            'windowsfilenames': True,
                            'logger': _SilentYDLLogger(),  # Logger customizado para suprimir spam
                        }

                        # Aplicar proxy rotativa (apenas 3 proxies fixas)
                        try:
                            from proxy_rotator import apply_proxy_to_opts
                            ydl_opts_dl = apply_proxy_to_opts(ydl_opts_dl)
                        except ImportError:
                            pass

                        with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl_dl:
                            ydl_dl.download([video_url])

                        if os.path.exists(output_path) and os.path.getsize(output_path) > 50000:
                            downloaded_ids.add(vid_id)
                            _save_downloaded_ids(downloaded_ids)
                            
                            # ✅ NOVO: Remover do cache de erros se conseguiu fazer download
                            if vid_id in failed_videos:
                                del failed_videos[vid_id]
                                _save_failed_videos(failed_videos)
                            
                            size_mb = os.path.getsize(output_path) / (1024 * 1024)
                            download_count += 1
                            logging.info(f"   ✅ Descarregado: {title} ({size_mb:.1f}MB)")
                        else:
                            # Ficheiro inválido, remover
                            if os.path.exists(output_path):
                                os.remove(output_path)
                            logging.debug(f"   ⚠️ Download falhou ou ficheiro inválido: {title}")
                            
                            # Marcar como erro genérico
                            failed_videos[vid_id] = "Ficheiro inválido ou download incompleto"
                            _save_failed_videos(failed_videos)

                    except Exception as dl_err:
                        erro_str = str(dl_err)
                        
                        # ✅ NOVO: Rastrear se é erro de bot-detection
                        if any(x in erro_str.lower() for x in ['bot', 'sign in', 'cookies', 'authentication', 'age']):
                            fail_reason = "Bot-detection/Autenticação necessária"
                            logging.debug(f"   ⏭️  {title}: {fail_reason} (será skipado em futuras tentativas)")
                        else:
                            fail_reason = erro_str[:100]
                            logging.error(f"   ❌ Erro ao descarregar {title}: {fail_reason}")
                        
                        # Guardar falha no cache
                        failed_videos[vid_id] = fail_reason
                        _save_failed_videos(failed_videos)
                        
                        # Limpar ficheiros parciais
                        for ext in ('', '.part', '.ytdl', '.temp'):
                            p = output_path + ext
                            if os.path.exists(p):
                                try:
                                    os.remove(p)
                                except Exception:
                                    pass

                if download_count > 0:
                    logging.info(f"✅ AutoManager: {download_count} vídeos descarregados para {_AUTO_DOWNLOADS_DIR}")

        except Exception as e:
            err_str = str(e).lower()
            if "does not exist" in err_str or "not found" in err_str or "invalid" in err_str:
                logging.warning(f"⚠️ Playlist inválida ou não acessível: {self.playlist_url[:50]}...")
            else:
                logging.error(f"❌ Erro ao buscar playlist: {e}")


# Instância global
auto_manager = AutoManager()


def configure_auto_manager(playlist_url, max_storage_mb=5000, check_interval_minutes=15):
    """Configura e inicia o AutoManager."""
    global auto_manager
    auto_manager.stop()
    auto_manager = AutoManager(playlist_url, max_storage_mb, check_interval_minutes)
    auto_manager.start()
    return auto_manager


def get_auto_manager():
    """Retorna a instância global do AutoManager."""
    return auto_manager
