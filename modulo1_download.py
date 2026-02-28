import yt_dlp
import os


def _make_progress_hook():
    """Barra de progresso que só imprime a cada 10%."""
    last_milestone = [-1]  # mutable para closure
    
    def hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                pct = int(downloaded / total * 100)
                milestone = pct // 10 * 10  # 0, 10, 20, 30...
                if milestone > last_milestone[0]:
                    last_milestone[0] = milestone
                    bar_len = 20
                    filled = int(bar_len * pct / 100)
                    bar = '█' * filled + '░' * (bar_len - filled)
                    total_mb = total / 1024 / 1024
                    print(f"  ⬇ |{bar}| {pct}% de {total_mb:.0f}MB")
        elif d['status'] == 'finished':
            print(f"  ⬇ |{'█' * 20}| 100% ✅")
    
    return hook


def baixar_video_youtube(url_do_video, nome_arquivo="video_original"):
    """
    Baixa um vídeo do YouTube na melhor qualidade MP4.
    
    Args:
        url_do_video (str): URL do vídeo do YouTube
        nome_arquivo (str): Nome do arquivo a ser salvo (sem extensão)
    
    Returns:
        str: Caminho completo do arquivo baixado ou None se falhar
    """
    # Cria a pasta downloads se ela não existir
    pasta_destino = "downloads"
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
        
    caminho_completo = f"{pasta_destino}/{nome_arquivo}.mp4"
    
    # Remove ficheiro antigo se existir (URL pode ter mudado)
    if os.path.exists(caminho_completo):
        os.remove(caminho_completo)
    
    print(f"Iniciando download de: {url_do_video}...")
    
    # Configurações do yt-dlp
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': caminho_completo,
        'quiet': True,              # Suprime output padrão do yt-dlp
        'no_warnings': True,
        'noprogress': True,         # Suprime linhas [download] nativas
        'progress_hooks': [_make_progress_hook()],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_do_video])
        print(f"✅ Download concluído com sucesso! Salvo em: {caminho_completo}")
        return caminho_completo
    except Exception as e:
        print(f"❌ Erro ao baixar o vídeo: {e}")
        return None
