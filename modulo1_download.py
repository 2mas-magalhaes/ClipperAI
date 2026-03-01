import yt_dlp
import os
import subprocess
import glob


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


def _limpar_parciais(caminho_completo):
    """Remove ficheiros .part, .ytdl e temporários de downloads falhados."""
    for ext in ('.part', '.ytdl', '.temp'):
        parcial = caminho_completo + ext
        if os.path.exists(parcial):
            try:
                os.remove(parcial)
            except Exception:
                pass
    # Remove .f*.mp4 (fragmentos do yt-dlp merge)
    base = os.path.splitext(caminho_completo)[0]
    for frag in glob.glob(f"{base}.f*.mp4") + glob.glob(f"{base}.f*.m4a") + glob.glob(f"{base}.f*.webm"):
        try:
            os.remove(frag)
        except Exception:
            pass


def _validar_video(caminho):
    """Verifica se o ficheiro é um vídeo MP4 válido com ffprobe."""
    if not os.path.exists(caminho):
        return False, "Ficheiro não existe"
    tamanho = os.path.getsize(caminho)
    if tamanho < 50000:  # < 50KB = provavelmente corrompido
        return False, f"Ficheiro demasiado pequeno ({tamanho} bytes)"
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration',
            '-show_entries', 'format=duration',
            '-of', 'json',
            caminho
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            return False, f"ffprobe falhou: {res.stderr[:200]}"
        import json
        info = json.loads(res.stdout)
        # Verifica se tem stream de vídeo
        streams = info.get('streams', [])
        if not streams:
            return False, "Sem stream de vídeo"
        w = streams[0].get('width', 0)
        h = streams[0].get('height', 0)
        if w < 100 or h < 100:
            return False, f"Resolução inválida: {w}x{h}"
        dur = float(info.get('format', {}).get('duration', 0))
        if dur < 1:
            return False, f"Duração inválida: {dur}s"
        return True, f"{w}x{h}, {dur:.0f}s, {tamanho/(1024*1024):.1f}MB"
    except Exception as e:
        return False, f"Erro na validação: {e}"


def baixar_video_youtube(url_do_video, nome_arquivo="video_original"):
    """
    Baixa um vídeo do YouTube na melhor qualidade possível (1080p+).

    Prioridade de formatos:
      1. Melhor vídeo ≤1080p mp4/webm + melhor áudio → merge mp4
      2. Melhor vídeo qualquer resolução + melhor áudio → merge mp4
      3. Melhor ficheiro único mp4
      4. Melhor disponível (qualquer formato)

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

    # Remove ficheiro antigo e parciais
    if os.path.exists(caminho_completo):
        os.remove(caminho_completo)
    _limpar_parciais(caminho_completo)

    print(f"Iniciando download de: {url_do_video}...")

    # Formato de alta qualidade para TikTok/Shorts (1080p ideal)
    # Prioriza 1080p porque é o padrão TikTok; aceita melhor se não houver
    formato_hq = (
        'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/'
        'bestvideo[height<=1080]+bestaudio/'
        'bestvideo[ext=mp4]+bestaudio[ext=m4a]/'
        'bestvideo+bestaudio/'
        'best[ext=mp4]/best'
    )

    # Configurações base do yt-dlp — alta qualidade
    ydl_opts_base = {
        'format': formato_hq,
        'merge_output_format': 'mp4',       # Garante output MP4 após merge
        'outtmpl': caminho_completo,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'progress_hooks': [_make_progress_hook()],
        'retries': 5,                       # Retry em caso de erro de rede
        'fragment_retries': 5,
        'file_access_retries': 3,
        'extractor_retries': 3,
        'age_limit': None,                  # Sem limite de idade
        'postprocessors': [{
            'key': 'FFmpegVideoRemuxer',
            'preferedformat': 'mp4',        # Garante container mp4
        }],
        'socket_timeout': 30,
        'http_chunk_size': 10485760,         # 10MB chunks (mais estável)
    }

    # Estratégias de fallback progressivas:
    # 1. Cookies de browser (obtêm formatos DASH 1080p)
    # 2. android client (bypassa age-gate, pode ser <1080p)
    # 3. mweb client (mobile web, outro bypass)
    # 4. formato simples (último recurso)
    tentativas = []

    # Cookies primeiro — é o que dá acesso a formatos 1080p DASH
    for navegador in ["opera", "chrome", "edge", "firefox", "brave"]:
        opts = dict(ydl_opts_base)
        opts['cookiesfrombrowser'] = (navegador,)
        opts['extractor_args'] = {'youtube': {'player_client': ['web', 'android']}}
        tentativas.append((f"cookies do {navegador}", opts))

    # Android client sem cookies (bypassa age-gate, mas pode ser 360p)
    opts_android = dict(ydl_opts_base)
    opts_android['extractor_args'] = {'youtube': {'player_client': ['android']}}
    tentativas.append(("android client (sem cookies)", opts_android))

    # mweb client sem cookies
    opts_mweb = dict(ydl_opts_base)
    opts_mweb['extractor_args'] = {'youtube': {'player_client': ['mweb', 'android']}}
    tentativas.append(("mweb+android client", opts_mweb))

    # Sem restrições como último recurso
    opts_last = dict(ydl_opts_base)
    opts_last['format'] = 'best[ext=mp4]/best'
    tentativas.append(("formato simples (fallback)", opts_last))

    ultimo_erro = None
    for descricao, ydl_opts in tentativas:
        try:
            _limpar_parciais(caminho_completo)  # Limpa parciais de tentativas anteriores
            if descricao != "sem cookies":
                print(f"  🔐 Tentando autenticação com {descricao}...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url_do_video])

            # Valida o ficheiro descarregado
            valido, detalhe = _validar_video(caminho_completo)
            if valido:
                # Rejeitar resolução baixa (<720p) — tentar próximo método
                try:
                    res_w = int(detalhe.split('x')[0])
                    res_h = int(detalhe.split('x')[1].split(',')[0])
                    if max(res_w, res_h) < 720:
                        print(f"  ⚠️ Resolução baixa ({res_w}x{res_h}), a tentar outro método...")
                        if os.path.exists(caminho_completo):
                            os.remove(caminho_completo)
                        ultimo_erro = Exception(f"Resolução baixa: {res_w}x{res_h}")
                        continue
                except (ValueError, IndexError):
                    pass
                print(f"✅ Download concluído! ({detalhe}) [{descricao}]")
                print(f"   Salvo em: {caminho_completo}")
                return caminho_completo
            else:
                print(f"  ⚠️ Download completou mas ficheiro inválido: {detalhe}")
                if os.path.exists(caminho_completo):
                    os.remove(caminho_completo)
                ultimo_erro = Exception(f"Ficheiro inválido: {detalhe}")
                continue

        except Exception as e:
            ultimo_erro = e
            # Limpa ficheiro parcial/corrompido
            _limpar_parciais(caminho_completo)
            if os.path.exists(caminho_completo):
                try:
                    os.remove(caminho_completo)
                except Exception:
                    pass

    print(f"❌ Erro ao baixar o vídeo: {ultimo_erro}")
    print("💡 Dica: inicie sessão no YouTube no navegador e volte a tentar.")
    _limpar_parciais(caminho_completo)
    return None


def baixar_playlist_satisfatoria(url_playlist, n_videos=5, pasta_destino="downloads/satisfying"):
    """
    Descarrega N vídeos aleatórios de uma playlist do YouTube para a pasta satisfying.
    Usa yt-dlp para extrair a lista de vídeos (sem baixar) e depois baixa os escolhidos.

    Args:
        url_playlist (str): URL da playlist do YouTube.
        n_videos (int): Quantos vídeos baixar (default 5).
        pasta_destino (str): Pasta onde guardar os vídeos.

    Returns:
        list[str]: Lista de caminhos dos vídeos baixados com sucesso.
    """
    import random as _random

    os.makedirs(pasta_destino, exist_ok=True)
    print(f"📋 A obter lista da playlist satisfatória...")

    # 1) Extrai apenas metadados da playlist (rápido, sem download)
    ydl_opts_flat = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'playlistend': 200,   # limita a 200 entradas para ser rápido
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'socket_timeout': 30,
    }

    entradas = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            info = ydl.extract_info(url_playlist, download=False)
            entradas = info.get('entries', []) if info else []
    except Exception as e:
        print(f"❌ Erro ao obter playlist: {e}")
        return []

    # Filtra entradas válidas
    entradas = [e for e in entradas if e and e.get('id')]
    if not entradas:
        print("❌ Playlist vazia ou inacessível.")
        return []

    print(f"  📋 {len(entradas)} vídeos na playlist, a escolher {n_videos}...")

    # 2) Escolhe N aleatórios
    escolhidos = _random.sample(entradas, min(n_videos, len(entradas)))

    # Formato: 1080p para qualidade máxima no layout split
    formato_sat = (
        'bestvideo[height=1080][ext=mp4]+bestaudio[ext=m4a]/'
        'bestvideo[height=1080]+bestaudio/'
        'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/'
        'bestvideo[height<=1080]+bestaudio/'
        'bestvideo[ext=mp4]+bestaudio[ext=m4a]/'
        'bestvideo+bestaudio/'
        'best[ext=mp4]/best'
    )

    baixados = []
    for idx, entrada in enumerate(escolhidos, 1):
        vid_id  = entrada.get('id', '')
        titulo  = entrada.get('title', vid_id)
        url_vid = f"https://www.youtube.com/watch?v={vid_id}"
        # Usa o id como nome para evitar conflitos
        nome_ficheiro = f"sat_{vid_id}.mp4"
        caminho = os.path.join(pasta_destino, nome_ficheiro)

        if os.path.exists(caminho) and os.path.getsize(caminho) > 50000:
            print(f"  [{idx}/{len(escolhidos)}] ✅ Já existe: {titulo[:50]}")
            baixados.append(caminho)
            continue

        print(f"  [{idx}/{len(escolhidos)}] ⬇ {titulo[:60]}")

        ydl_opts_dl = {
            'format': formato_sat,
            'merge_output_format': 'mp4',
            'outtmpl': caminho,
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'progress_hooks': [_make_progress_hook()],
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 30,
            'http_chunk_size': 10485760,
            'postprocessors': [{
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': 'mp4',
            }],
        }

        ok = False
        # Cookies primeiro (merge DASH precisa de autenticação na maioria dos casos)
        tentativas_sat = []
        for navegador in ['chrome', 'edge', 'firefox', 'brave', 'opera']:
            opts_c = dict(ydl_opts_dl)
            opts_c['cookiesfrombrowser'] = (navegador,)
            tentativas_sat.append((f'cookies {navegador}', opts_c))
        tentativas_sat.append(('sem cookies', ydl_opts_dl))

        for desc_t, opts_t in tentativas_sat:
            try:
                _limpar_parciais(caminho)
                with yt_dlp.YoutubeDL(opts_t) as ydl:
                    ydl.download([url_vid])
                valido, detalhe = _validar_video(caminho)
                if valido:
                    # Rejeitar se resolução < 720p (queremos qualidade)
                    try:
                        res_w = int(detalhe.split('x')[0])
                        res_h = int(detalhe.split('x')[1].split(',')[0])
                        if max(res_w, res_h) < 720:
                            print(f"    ⚠️ Resolução baixa ({detalhe}), a tentar outro método...")
                            if os.path.exists(caminho):
                                os.remove(caminho)
                            continue
                    except (ValueError, IndexError):
                        pass
                    print(f"    ✅ {detalhe} ({desc_t})")
                    baixados.append(caminho)
                    ok = True
                    break
                else:
                    if os.path.exists(caminho):
                        os.remove(caminho)
            except Exception as e:
                _limpar_parciais(caminho)
                if os.path.exists(caminho):
                    try:
                        os.remove(caminho)
                    except Exception:
                        pass
                if desc_t != tentativas_sat[-1][0]:
                    continue
                print(f"    ❌ Falhou: {e}")

        if not ok:
            print(f"    ⚠️ Pulando vídeo {vid_id}")

    print(f"  🎮 {len(baixados)}/{len(escolhidos)} vídeos satisfatórios prontos")
    return baixados
