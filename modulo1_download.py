import yt_dlp
import os
import subprocess
import glob
import logging

try:
    from proxy_rotator import get_proxy, remove_bad_proxy, apply_proxy_to_opts, refresh_proxies
    _HAS_PROXY = True
except ImportError:
    _HAS_PROXY = False
    def get_proxy(): return None
    def remove_bad_proxy(p): pass
    def apply_proxy_to_opts(o, p=None): return o
    def refresh_proxies(**kw): pass

# Fallback API alternativa: pytubefix (fork atualizado do pytube)
try:
    from pytubefix import YouTube
    _HAS_PYTUBE = True
except ImportError:
    _HAS_PYTUBE = False


def _make_progress_hook(external_callback=None):
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
                    # Callback externo para atualizar DB
                    if external_callback:
                        try:
                            external_callback(pct)
                        except Exception:
                            pass
        elif d['status'] == 'finished':
            print(f"  ⬇ |{'█' * 20}| 100% ✅")
            if external_callback:
                try:
                    external_callback(100)
                except Exception:
                    pass

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


def _max_altura_disponivel(url_video, ydl_opts):
    """
    Consulta metadados sem descarregar e devolve a maior resolução de vídeo disponível
    para as opções atuais do yt-dlp (cookies/client/headers).
    """
    try:
        opts_info = dict(ydl_opts)
        opts_info['skip_download'] = True
        opts_info['quiet'] = True
        opts_info['no_warnings'] = True
        with yt_dlp.YoutubeDL(opts_info) as ydl:
            info = ydl.extract_info(url_video, download=False)
        formatos = info.get('formats', []) if info else []
        alturas = [
            int(f.get('height', 0) or 0)
            for f in formatos
            if f.get('vcodec') not in (None, 'none')
        ]
        return max(alturas) if alturas else 0
    except Exception:
        return 0


def _baixar_com_pytube(url_video, caminho_saida):
    """
    Fallback usando biblioteca pytubefix (fork atualizado do pytube).
    Retorna True se sucesso, False se falhar.
    """
    if not _HAS_PYTUBE:
        return False
    
    try:
        print("  📦 Tentando pytubefix (API alternativa)...")
        
        # Criar objeto YouTube
        yt = YouTube(url_video)
        
        # Tentar obter título (pode falhar se bot detection)
        try:
            titulo = yt.title[:50]
            print(f"     Título: {titulo}...")
        except Exception:
            print(f"     (sem título - possível bot detection)")
        
        # Obter streams progressivos MP4 (vídeo+áudio integrado)
        streams = yt.streams.filter(
            progressive=True, 
            file_extension='mp4'
        )
        
        if not streams:
            print(f"  ⚠️ Pytubefix: nenhum stream progressivo encontrado")
            return False
        
        # Ordenar por resolução e pegar o melhor
        melhor = streams.order_by('resolution').desc().first()
        
        if not melhor:
            print(f"  ⚠️ Pytubefix: erro ao selecionar stream")
            return False
        
        print(f"     Stream: {melhor.resolution} @ {melhor.fps}fps ({melhor.filesize / (1024*1024):.1f}MB)")
        
        # Download direto
        pasta_destino = os.path.dirname(caminho_saida)
        nome_temp = f"pytubefix_{os.getpid()}.mp4"
        
        print(f"     A descarregar...")
        melhor.download(output_path=pasta_destino, filename=nome_temp)
        
        caminho_temp = os.path.join(pasta_destino, nome_temp)
        
        # Verificar e mover
        if os.path.exists(caminho_temp):
            tamanho = os.path.getsize(caminho_temp)
            if tamanho > 50000:  # > 50KB
                # Remover destino se já existe
                if os.path.exists(caminho_saida):
                    os.remove(caminho_saida)
                os.rename(caminho_temp, caminho_saida)
                
                # Validar
                valido, detalhe = _validar_video(caminho_saida)
                if valido:
                    print(f"✅ Download concluído via pytubefix! ({detalhe})")
                    return True
                else:
                    print(f"  ⚠️ Pytubefix: ficheiro inválido - {detalhe}")
                    if os.path.exists(caminho_saida):
                        os.remove(caminho_saida)
                    return False
            else:
                print(f"  ⚠️ Pytubefix: ficheiro muito pequeno ({tamanho} bytes)")
                if os.path.exists(caminho_temp):
                    os.remove(caminho_temp)
                return False
        else:
            print(f"  ⚠️ Pytubefix: ficheiro de saída não foi criado")
            return False
    
    except Exception as e:
        erro_str = str(e)
        # Bot detection é comum - não é erro grave
        if 'BotDetection' in erro_str or 'bot' in erro_str.lower():
            print(f"  ⚠️ Pytubefix: bot detection (comum em alguns vídeos)")
        else:
            print(f"  ⚠️ Pytubefix falhou: {erro_str[:120]}")
        
        # Limpar ficheiros temporários
        try:
            pasta_destino = os.path.dirname(caminho_saida)
            for f in os.listdir(pasta_destino):
                if f.startswith('pytubefix_'):
                    try:
                        os.remove(os.path.join(pasta_destino, f))
                    except:
                        pass
        except:
            pass
        
        return False


def baixar_video_youtube(url_do_video, nome_arquivo="video_original", progress_callback=None):
    """
    Baixa um vídeo do YouTube ou copia um ficheiro local.

    Prioridade de formatos (YouTube):
      1. Melhor vídeo ≤1080p mp4/webm + melhor áudio → merge mp4
      2. Melhor vídeo qualquer resolução + melhor áudio → merge mp4
      3. Melhor ficheiro único mp4
      4. Melhor disponível (qualquer formato)

    Para ficheiros locais (prefixo local://):
      - Copia diretamente para downloads/

    Args:
        url_do_video (str): URL do vídeo do YouTube ou local://caminho/para/video.mp4
        nome_arquivo (str): Nome do arquivo a ser salvo (sem extensão)
        progress_callback (callable): Função callback(pct) para atualizar progresso

    Returns:
        str: Caminho completo do arquivo baixado ou None se falhar
    """
    # Cria a pasta downloads se ela não existir
    pasta_destino = "downloads"
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)

    caminho_completo = f"{pasta_destino}/{nome_arquivo}.mp4"

    # Suporte a ficheiros locais
    if url_do_video.startswith('local://'):
        caminho_local = url_do_video.replace('local://', '', 1)
        if not os.path.exists(caminho_local):
            print(f"❌ Ficheiro local não encontrado: {caminho_local}")
            return None
        
        # Copiar ficheiro
        import shutil as sh_util
        try:
            print(f"📁 Copiando ficheiro local: {os.path.basename(caminho_local)}...")
            sh_util.copy2(caminho_local, caminho_completo)
            tamanho = os.path.getsize(caminho_completo)
            print(f"✅ Ficheiro copiado ({tamanho / (1024*1024):.1f}MB)")
            if progress_callback:
                try:
                    progress_callback(100)
                except:
                    pass
            return caminho_completo
        except Exception as e:
            print(f"❌ Erro ao copiar ficheiro: {e}")
            return None

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
        'progress_hooks': [_make_progress_hook(progress_callback)],
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

    # Estratégias de fallback simplificadas (3 métodos essenciais):
    # 1. Sem cookies (mais rápido, qualidade alta)
    # 2. Firefox + cookies (melhor bypass Cloudflare/bot detection)
    # 3. Android client (bypass age-gate e vídeos restritos)
    # Se falharem → proxies → iOS client (último recurso)
    tentativas = []

    # User-Agent atualizado (Firefox 2026)
    UA_FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
    UA_CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

    # 1. Sem cookies primeiro (mais rápido e funciona na maioria dos casos)
    opts_sem_cookies = dict(ydl_opts_base)
    tentativas.append(("sem cookies", opts_sem_cookies))

    # 2. Firefox + cookies + User-Agent (recomendado para Cloudflare)
    opts_firefox = dict(ydl_opts_base)
    opts_firefox['cookiesfrombrowser'] = ('firefox',)
    opts_firefox['http_headers'] = {'User-Agent': UA_FIREFOX}
    tentativas.append(("Firefox + cookies", opts_firefox))

    # 3. Android client (bypass age-gate e algumas restrições)
    opts_android = dict(ydl_opts_base)
    opts_android['extractor_args'] = {'youtube': {'player_client': ['android']}}
    tentativas.append(("Android client", opts_android))

    ultimo_erro = None

    # ── Tentativas SEM proxy (máximo 3 métodos) ──
    for descricao, ydl_opts in tentativas:
        try:
            _limpar_parciais(caminho_completo)
            if not descricao.startswith("sem cookies"):
                print(f"  🔐 Tentando com {descricao}...")

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
            _limpar_parciais(caminho_completo)
            if os.path.exists(caminho_completo):
                try:
                    os.remove(caminho_completo)
                except Exception:
                    pass
            # Não imprimir erros de cookies — são esperados
            err_str = str(e).lower()
            if 'cookie' not in err_str and 'dpapi' not in err_str:
                print(f"  ⚠️ {descricao} falhou: {str(e)[:80]}")

    # ── Tentativas com PROXY ROTATIVA (quando os métodos falharam) ──
    if _HAS_PROXY:
        print("  🔄 A tentar com proxies...")
        proxies_usadas = set()
        for proxy_attempt in range(5):
            try:
                proxy_url = get_proxy()
                if not proxy_url or proxy_url in proxies_usadas:
                    # Refrescar se as proxies se esgotaram
                    if proxy_attempt > 0:
                        refresh_proxies(force=True)
                        proxy_url = get_proxy()
                    if not proxy_url or proxy_url in proxies_usadas:
                        break
                proxies_usadas.add(proxy_url)

                print(f"  🌐 Proxy #{proxy_attempt+1}: {proxy_url[:40]}...")
                _limpar_parciais(caminho_completo)

                opts_proxy = dict(ydl_opts_base)
                opts_proxy['proxy'] = proxy_url
                opts_proxy['socket_timeout'] = 20
                opts_proxy['retries'] = 3
                # Adicionar User-Agent para melhor compatibilidade
                opts_proxy['http_headers'] = {'User-Agent': UA_CHROME}

                # Download direto (sem pré-verificação de resolução para não gastar proxy)
                with yt_dlp.YoutubeDL(opts_proxy) as ydl:
                    ydl.download([url_do_video])

                valido, detalhe = _validar_video(caminho_completo)
                if valido:
                    print(f"✅ Download concluído via proxy! ({detalhe})")
                    print(f"   Salvo em: {caminho_completo}")
                    return caminho_completo
                else:
                    print(f"  ⚠️ Proxy download inválido: {detalhe}")
                    remove_bad_proxy(proxy_url)
                    if os.path.exists(caminho_completo):
                        os.remove(caminho_completo)

            except Exception as e:
                erro_str = str(e).lower()
                print(f"  ⚠️ Proxy #{proxy_attempt+1} falhou: {str(e)[:100]}")
                if proxy_url:
                    remove_bad_proxy(proxy_url)
                ultimo_erro = e
                _limpar_parciais(caminho_completo)
                if os.path.exists(caminho_completo):
                    try:
                        os.remove(caminho_completo)
                    except Exception:
                        pass
                # Se é erro de SOCKS/conexão, tentar próxima proxy
                if any(x in erro_str for x in ['socks', 'proxy', 'connect', 'timeout', 'refused', 'reset']):
                    continue
                # Outros erros (ex: bot detection) — também tentar próxima
                continue

    # ── Fallback Final: Pytube (API completamente diferente) ──
    if _HAS_PYTUBE:
        if _baixar_com_pytube(url_do_video, caminho_completo):
            # Refrescar proxies para próxima utilização
            if _HAS_PROXY:
                refresh_proxies(force=True)
            return caminho_completo

    print(f"❌ Erro ao baixar o vídeo: {ultimo_erro}")
    print("💡 Dica: inicie sessão no YouTube no navegador e volte a tentar.")
    if _HAS_PROXY:
        print("🔄 A refrescar lista de proxies para a próxima tentativa...")
        try:
            refresh_proxies(force=True)
        except Exception:
            pass
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
        # 3 métodos principais + proxy
        tentativas_sat = []
        tentativas_sat.append(('sem cookies', ydl_opts_dl))
        opts_opera = dict(ydl_opts_dl)
        opts_opera['cookiesfrombrowser'] = ('opera',)
        tentativas_sat.append(('cookies Opera', opts_opera))
        opts_android = dict(ydl_opts_dl)
        opts_android['extractor_args'] = {'youtube': {'player_client': ['android']}}
        tentativas_sat.append(('android client', opts_android))
        # Proxy como fallback
        if _HAS_PROXY:
            proxy_url = get_proxy()
            if proxy_url:
                opts_px = dict(ydl_opts_dl)
                opts_px['proxy'] = proxy_url
                tentativas_sat.append((f'proxy', opts_px))
                opts_px['proxy'] = proxy_url
                tentativas_sat.append((f'proxy ({proxy_url[:30]}...)', opts_px))

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
