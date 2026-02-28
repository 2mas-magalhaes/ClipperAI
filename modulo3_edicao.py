"""
MÓDULO 3 - Edição Profissional de Vídeos (V3 - Padrão TikTok/Shorts)

Pipeline por clipe:
  1. Cortar segmento (stream copy, sem perda de qualidade)
  2. Gerar legendas ASS com hook + estilo profissional
  3. Aplicar num único passo: crop 9:16 + efeitos + legendas

Efeitos profissionais incluídos:
  ✦ Crop inteligente 9:16 com leve zoom (105%)
  ✦ Color grading (saturation + contrast boost)
  ✦ Sharpen (nitidez profissional)
  ✦ Fade in/out suave
  ✦ Barra de progresso dourada no fundo
  ✦ Hook de abertura (3s, texto grande amarelo, centro da tela)
  ✦ Legendas word-by-word estilo TikTok (bold, outline, keyword highlight amarelo)
"""

import json
import subprocess
import os
import math
import shutil


# ════════════════════════════════════════════════════════════
#  FUNÇÕES UTILITÁRIAS
# ════════════════════════════════════════════════════════════

def ler_analise_clipes(caminho_json="downloads/analise_clipes.json"):
    """Lê o arquivo JSON com a análise de clipes."""
    try:
        with open(caminho_json, "r", encoding="utf-8") as f:
            clipes = json.load(f)
        print(f"✅ Arquivo de análise carregado: {len(clipes)} clipes encontrados")
        return clipes
    except Exception as e:
        print(f"❌ Erro ao ler análise de clipes: {e}")
        return None


def obter_duracao_video(caminho_video):
    """Obtém a duração total de um vídeo em segundos."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            caminho_video
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception as e:
        print(f"⚠️ Erro ao obter duração: {e}")
        return None


def obter_dimensoes_video(caminho_video):
    """Retorna (largura, altura) do vídeo."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=s=x:p=0',
            caminho_video
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        w, h = map(int, res.stdout.strip().split('x'))
        return w, h
    except Exception as e:
        print(f"⚠️ Erro ao obter dimensões: {e}")
        return None, None


def formatar_tempo_ass(segundos):
    """Converte segundos (float) para formato ASS (H:MM:SS.cc)."""
    segundos = max(0, float(segundos))
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    cs = int((segundos % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ════════════════════════════════════════════════════════════
#  GERAÇÃO DE LEGENDAS ASS (FORMATO PROFISSIONAL)
# ════════════════════════════════════════════════════════════

def criar_texto_hook(segmentos, inicio_corte, duracao_corte):
    """
    Gera texto de hook chamativo baseado na transcrição.
    Pega as primeiras palavras do clipe para gerar curiosidade.
    """
    fim_corte = inicio_corte + duracao_corte
    palavras_clip = []

    for seg in segmentos:
        if seg.get("fim", 0) < inicio_corte or seg.get("inicio", 0) > fim_corte:
            continue

        if "palavras" in seg and seg["palavras"]:
            for p in seg["palavras"]:
                t = p.get("inicio", 0)
                if t >= inicio_corte and t <= fim_corte:
                    palavra = p.get("palavra", "").strip()
                    if palavra:
                        palavras_clip.append(palavra)
        elif seg.get("texto"):
            for w in seg["texto"].split():
                w = w.strip()
                if w:
                    palavras_clip.append(w)

    if not palavras_clip:
        return "ATENÇÃO"

    # Pega primeiras 5 palavras como hook
    n = min(5, len(palavras_clip))
    hook = " ".join(palavras_clip[:n]).upper().strip()

    # Limpa caracteres que quebram ASS
    for ch in ["\\", "{", "}", "\n"]:
        hook = hook.replace(ch, "")

    # Adiciona "..." se cortou
    if len(palavras_clip) > n:
        hook += "..."

    return hook if hook else "ATENÇÃO"


def gerar_legendas_ass(segmentos, caminho_ass, inicio_corte, duracao_corte, texto_hook=""):
    """
    Gera arquivo ASS com legendas profissionais estilo TikTok.

    Inclui:
    - Hook de abertura (3 segundos, texto grande amarelo no centro)
    - Legendas dinâmicas word-by-word (grupos de 3 palavras)
    - Keyword highlighting (1ª palavra de cada grupo em AMARELO)
    - Micro fade in/out em cada legenda para suavidade
    """
    fim_corte = inicio_corte + duracao_corte

    # ── HEADER DO ARQUIVO ASS ──
    # PlayResX/Y = 1080x1920 (resolução do vídeo vertical)
    # MarginV=300 → legendas mais altas (longe do fundo)
    header = """[Script Info]
Title: ClipAI Legendas Profissionais
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Legenda,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&HD2000000,-1,0,0,0,100,100,2,0,1,4,2,2,40,40,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    linhas_eventos = []

    # Hook de abertura REMOVIDO (conforme pedido)

    # ── LEGENDAS DINÂMICAS ──
    legendas = []

    if segmentos:
        for seg in segmentos:
            seg_ini = seg.get("inicio", 0)
            seg_fim = seg.get("fim", 0)

            if seg_fim < inicio_corte or seg_ini > fim_corte:
                continue

            # Usa palavras individuais se disponíveis (grupos de 3)
            if "palavras" in seg and seg["palavras"] and len(seg["palavras"]) > 0:
                palavras = seg["palavras"]
                tamanho_grupo = 3

                for j in range(0, len(palavras), tamanho_grupo):
                    grupo = palavras[j:j + tamanho_grupo]
                    if not grupo:
                        continue

                    t_ini = max(0, float(grupo[0].get("inicio", 0)) - inicio_corte)
                    t_end = max(0, float(grupo[-1].get("fim", 0)) - inicio_corte)

                    if t_ini >= duracao_corte or t_end <= 0 or t_ini >= t_end:
                        continue
                    t_end = min(t_end, duracao_corte)
                    if t_end - t_ini < 0.1:
                        continue

                    # Junta palavras do grupo
                    words = [str(p.get("palavra", "")).strip() for p in grupo]
                    words = [w for w in words if w]
                    if not words:
                        continue

                    # KEYWORD HIGHLIGHT: 1ª palavra em amarelo, resto em branco
                    # \c&H0000FFFF& = amarelo (ASS usa AABBGGRR)
                    # \c&H00FFFFFF& = branco
                    if len(words) >= 2:
                        texto = (
                            "{\\c&H0000FFFF&}" + words[0].upper() +
                            "{\\c&H00FFFFFF&} " + " ".join(w.upper() for w in words[1:])
                        )
                    else:
                        texto = "{\\c&H0000FFFF&}" + words[0].upper() + "{\\c&H00FFFFFF&}"

                    legendas.append((t_ini, t_end, texto))

            else:
                # Sem palavras individuais: usa segmento inteiro
                t_ini = max(0, float(seg_ini) - inicio_corte)
                t_end = max(0, float(seg_fim) - inicio_corte)

                if t_ini >= duracao_corte or t_end <= 0 or t_ini >= t_end:
                    continue
                t_end = min(t_end, duracao_corte)

                texto_seg = str(seg.get("texto", "")).strip().upper()
                if not texto_seg:
                    continue

                # Divide frases longas em grupos de 3
                pals = texto_seg.split()
                if len(pals) > 5:
                    dur_total = t_end - t_ini
                    gs = 3
                    n_grupos = math.ceil(len(pals) / gs)
                    dur_g = dur_total / max(1, n_grupos)

                    for k in range(n_grupos):
                        g_pals = pals[k * gs:(k + 1) * gs]
                        g_ini = t_ini + k * dur_g
                        g_end = g_ini + dur_g

                        if len(g_pals) >= 2:
                            texto = (
                                "{\\c&H0000FFFF&}" + g_pals[0] +
                                "{\\c&H00FFFFFF&} " + " ".join(g_pals[1:])
                            )
                        else:
                            texto = "{\\c&H0000FFFF&}" + g_pals[0] + "{\\c&H00FFFFFF&}"

                        legendas.append((g_ini, g_end, texto))
                else:
                    if len(pals) >= 2:
                        texto = (
                            "{\\c&H0000FFFF&}" + pals[0] +
                            "{\\c&H00FFFFFF&} " + " ".join(pals[1:])
                        )
                    else:
                        texto = "{\\c&H0000FFFF&}" + texto_seg + "{\\c&H00FFFFFF&}"

                    legendas.append((t_ini, t_end, texto))

    # Fallback se não tem legendas
    if not legendas:
        legendas.append((0, min(5, duracao_corte), "{\\c&H00FFFFFF&}..."))

    # ── GERA LINHAS DE DIÁLOGO ──
    for t_ini, t_end, texto in legendas:
        t_inicio_str = formatar_tempo_ass(t_ini)
        t_fim_str = formatar_tempo_ass(t_end)
        # Limpa caracteres que podem quebrar o ASS (exceto os overrides intencionais)
        texto_limpo = texto.replace("\n", " ").replace("\\n", " ")
        # \fad(150,100) = micro fade para transição suave entre legendas
        linhas_eventos.append(
            f"Dialogue: 0,{t_inicio_str},{t_fim_str},Legenda,,0,0,0,,{{\\fad(150,100)}}{texto_limpo}"
        )

    # ── ESCREVE ARQUIVO ASS ──
    try:
        with open(caminho_ass, "w", encoding="utf-8-sig") as f:
            f.write(header)
            for linha in linhas_eventos:
                f.write(linha + "\n")

        print(f"  📝 {len(legendas)} legendas + hook geradas (formato ASS profissional)")
        return caminho_ass
    except Exception as e:
        print(f"  ❌ Erro ao salvar ASS: {e}")
        return None


# ════════════════════════════════════════════════════════════
#  CORTE DE VÍDEO
# ════════════════════════════════════════════════════════════

def cortar_video(caminho_video, inicio_seg, duracao_seg, caminho_saida):
    """Corta um segmento do vídeo (stream copy para velocidade máxima)."""
    try:
        # Tenta stream copy primeiro (instantâneo, sem perda)
        comando = [
            'ffmpeg',
            '-ss', str(inicio_seg),
            '-i', caminho_video,
            '-t', str(duracao_seg),
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
            '-y',
            caminho_saida
        ]
        resultado = subprocess.run(comando, capture_output=True, text=True)

        if resultado.returncode != 0:
            # Fallback: re-encode se copy falhar
            comando_fb = [
                'ffmpeg',
                '-i', caminho_video,
                '-ss', str(inicio_seg),
                '-t', str(duracao_seg),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast',
                '-y',
                caminho_saida
            ]
            subprocess.run(comando_fb, capture_output=True, check=True)

        return True
    except Exception as e:
        print(f"  ❌ Erro ao cortar vídeo: {e}")
        return False


# ════════════════════════════════════════════════════════════
#  DETEÇÃO DE FACE PARA CROP INTELIGENTE
# ════════════════════════════════════════════════════════════

def detectar_centro_falante(caminho_video, largura_video, altura_video, crop_w, crop_h):
    """
    Deteta a posição do falante usando OpenCV Haar face detection.
    Amostra frames a cada 3s, calcula a mediana do centro da face.
    Retorna (x_off, y_off) para o crop FFmpeg.
    Fallback: centro horizontal, terço superior vertical.
    """
    fallback_x = (largura_video - crop_w) // 2
    fallback_y = max(0, (altura_video - crop_h) // 3)
    try:
        import cv2
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            return fallback_x, fallback_y

        cap = cv2.VideoCapture(caminho_video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        sample_interval = max(1, int(fps * 3))  # amostrar 1x/3s
        cx_list, cy_list = [], []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_interval == 0:
                scale = 0.4  # reduz para deteção rápida
                small = cv2.resize(frame, None, fx=scale, fy=scale)
                gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5,
                    minSize=(int(40*scale), int(40*scale))
                )
                if len(faces) > 0:
                    x, y, w, h = max(faces, key=lambda f: f[2]*f[3])
                    cx_list.append(int((x + w/2) / scale))
                    cy_list.append(int((y + h/2) / scale))
            frame_idx += 1

        cap.release()

        if not cx_list:
            return fallback_x, fallback_y

        cx_list.sort(); cy_list.sort()
        median_cx = cx_list[len(cx_list) // 2]
        median_cy = cy_list[len(cy_list) // 2]

        # Regra dos terços: face a 30% do topo do enquadramento
        x_off = max(0, min(largura_video - crop_w, median_cx - crop_w // 2))
        y_off = max(0, min(altura_video - crop_h, int(median_cy - crop_h * 0.30)))

        print(f"  \U0001f464 Face detetada: ({median_cx}, {median_cy}) → crop offset ({x_off}, {y_off})")
        return x_off, y_off

    except ImportError:
        print("  \u2139\ufe0f  OpenCV não disponível → crop central")
        return fallback_x, fallback_y
    except Exception as e:
        print(f"  \u26a0\ufe0f Deteção de face falhou: {e}")
        return fallback_x, fallback_y


# ════════════════════════════════════════════════════════════
#  EDIÇÃO PROFISSIONAL (TUDO NUM ÚNICO PASSO FFMPEG)
# ════════════════════════════════════════════════════════════

def aplicar_edicao_profissional(caminho_video, caminho_ass, caminho_saida, duracao_clip):
    """
    Aplica crop vertical + efeitos visuais + legendas ASS num único passo.

    Efeitos aplicados (em ordem):
      1. Crop inteligente 9:16 com zoom 105%
      2. Scale para 1080x1920
      3. Color grading (saturation, contrast, brightness)
      4. Sharpen (nitidez)
      5. Fade in (0.8s) / Fade out (0.6s)
      6. Barra de progresso dourada (6px no fundo)
      7. Legendas ASS estilizadas (com hook + keyword highlight)
    """
    try:
        # Obtém dimensões do vídeo
        w, h = obter_dimensoes_video(caminho_video)
        if not w or not h:
            print("  ⚠️ Não foi possível obter dimensões do vídeo")
            return False

        # ── CALCULA CROP 9:16 COM ZOOM 108% ──
        zoom = 1.08
        ratio_alvo = 9 / 16
        ratio_atual = w / h

        if ratio_atual > ratio_alvo:
            crop_h_px = int(h / zoom)
            crop_w_px = int(crop_h_px * ratio_alvo)
        else:
            crop_w_px = int(w / zoom)
            crop_h_px = int(crop_w_px / ratio_alvo)

        # ── FACE TRACKING: enquadra o falante ──
        print("  \U0001f50d  Detetando falante para enquadramento...")
        x_off, y_off = detectar_centro_falante(caminho_video, w, h, crop_w_px, crop_h_px)

        # ── CONSTRÓI CADEIA DE FILTROS ──
        filtros = []

        # 1. Crop centrado no falante + Scale para 1080x1920
        filtros.append(f"crop={crop_w_px}:{crop_h_px}:{x_off}:{y_off}")
        filtros.append("scale=1080:1920:flags=lanczos")

        # 2. Color grading (look redes sociais)
        filtros.append("eq=contrast=1.07:brightness=0.015:saturation=1.25")

        # 3. Sharpen leve
        filtros.append("unsharp=3:3:0.6")

        # 4. Vinheta cinematográfica (foca atenção no centro)
        filtros.append("vignette=angle=PI/5:mode=backward")

        # 5. EFEITO DE ENTRADA: zoom punch (1.08→1.0) + flash branco
        #    Usa fade branco (mais impactante que preto)
        fade_out_start = max(0, duracao_clip - 0.7)
        filtros.append("fade=t=in:st=0:d=0.5:color=white")   # punch branco
        filtros.append(f"fade=t=out:st={fade_out_start:.2f}:d=0.7:color=black")

        # 6. Barra de progresso dourada (6px no fundo)
        filtros.append(
            f"drawbox=x=0:y=ih-6:w=iw*t/{duracao_clip:.2f}:h=6:color=gold@0.9:t=fill"
        )

        # 7. Legendas ASS (sem hook, com subt. altas)
        if caminho_ass and os.path.exists(caminho_ass):
            ass_path = os.path.abspath(caminho_ass).replace('\\', '/').replace(':', '\\:')
            filtros.append(f"subtitles='{ass_path}'")

        filtro_completo = ','.join(filtros)

        # ── TENTA NVENC (GPU hardware encoder: 5-10x mais rápido que libx264) ──
        # GTX 1070 suporta h264_nvenc. Qualidade VBR CQ=20 ≈ libx264 CRF=20
        comando_nvenc = [
            'ffmpeg',
            '-i', caminho_video,
            '-vf', filtro_completo,
            '-c:v', 'h264_nvenc',
            '-preset', 'p4',           # P4 = balanço performance/qualidade (p1=ultrafast, p7=hq)
            '-rc:v', 'vbr',            # VBR guiado por qualidade
            '-cq:v', '20',             # CQ 20 ≈ CRF 20 (qualidade visual idêntica)
            '-b:v', '0',               # Sem limite de bitrate (deixa CQ controlar)
            '-maxrate', '8M',          # Teto para picos de cena
            '-bufsize', '16M',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',
            caminho_saida
        ]

        resultado = subprocess.run(comando_nvenc, capture_output=True, text=True, timeout=300)

        if resultado.returncode == 0:
            print(f"  ⚡ NVENC ativo (GPU encoding)")
            return True

        # ── FALLBACK: libx264 se NVENC falhar ──
        print(f"  ⚠️ NVENC falhou, usando libx264...")
        comando = [
            'ffmpeg',
            '-i', caminho_video,
            '-vf', filtro_completo,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '20',
            '-threads', '0',           # Usa todos os cores disponíveis
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',
            caminho_saida
        ]

        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=600)

        if resultado.returncode == 0:
            return True

        # ── FALLBACK: sem legendas se houver erro ──
        print(f"  ⚠️ Erro com legendas, tentando sem legendas...")
        filtros_sem_leg = [f for f in filtros if not f.startswith("subtitles=")]
        filtro_fallback = ','.join(filtros_sem_leg)

        comando_fb = [
            'ffmpeg',
            '-i', caminho_video,
            '-vf', filtro_fallback,
            '-c:v', 'h264_nvenc',
            '-preset', 'p4',
            '-rc:v', 'vbr',
            '-cq:v', '20',
            '-b:v', '0',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            caminho_saida
        ]

        resultado_fb = subprocess.run(comando_fb, capture_output=True, text=True, timeout=600)

        if resultado_fb.returncode == 0:
            print(f"  ⚠️ Efeitos aplicados sem legendas (fallback)")
            return True

        print(f"  ❌ Fallback também falhou: {resultado_fb.stderr[-400:]}")
        return False

    except subprocess.TimeoutExpired:
        print(f"  ⚠️ FFmpeg timeout (>10min)")
        return False
    except Exception as e:
        print(f"  ❌ Erro na edição profissional: {e}")
        return False


# ════════════════════════════════════════════════════════════
#  PIPELINE PRINCIPAL
# ════════════════════════════════════════════════════════════

def editar_clipes(caminho_video, clipes, segmentos_whisper, pasta_saida="downloads/clips_editados"):
    """
    Pipeline profissional de edição de clipes.

    Para cada clipe:
      1. Corta o segmento (stream copy, rápido)
      2. Gera legendas ASS com hook + estilo profissional
      3. Aplica crop + todos os efeitos + legendas (encoding único)
    """
    os.makedirs(pasta_saida, exist_ok=True)

    duracao_total = obter_duracao_video(caminho_video)
    if not duracao_total:
        duracao_total = 300  # Fallback: 5 minutos

    clipes_editados = []

    for i, clipe in enumerate(clipes, 1):
        titulo = clipe.get('titulo') or clipe.get('title', f'Clipe {i}')
        print(f"\n{'='*55}")
        print(f"📹 Editando clipe {i}/{len(clipes)}: {titulo}")
        print(f"{'='*55}")

        # Distribui os clipes ao longo do vídeo
        duracao_clip = 45  # 45 segundos por clip
        num_clipes = len(clipes)
        espaco = max(0, duracao_total - duracao_clip) / max(1, num_clipes)
        inicio = espaco * (i - 1)

        # Garante que não ultrapassa a duração
        if inicio + duracao_clip > duracao_total:
            inicio = max(0, duracao_total - duracao_clip)
            duracao_clip = min(duracao_clip, duracao_total - inicio)

        if duracao_clip <= 0:
            print(f"  ⚠️ Duração insuficiente para clipe {i}")
            continue

        # Caminhos
        caminho_cortado = f"{pasta_saida}/clip_{i:02d}_temp.mp4"
        caminho_ass = f"{pasta_saida}/clip_{i:02d}_legendas.ass"
        caminho_final = f"{pasta_saida}/clip_{i:02d}_final.mp4"

        # ═══ PASSO 1: CORTAR ═══
        print(f"  ✂️  Cortando ({inicio:.1f}s → {inicio + duracao_clip:.1f}s)...")
        if not cortar_video(caminho_video, inicio, duracao_clip, caminho_cortado):
            print(f"  ⚠️ Pulando clipe {i}")
            continue

        # ═══ PASSO 2: GERAR LEGENDAS ASS ═══
        print(f"  📝 Gerando legendas...")
        if segmentos_whisper:
            gerar_legendas_ass(
                segmentos_whisper, caminho_ass,
                inicio, duracao_clip, texto_hook=""  # sem hook
            )

        # ═══ PASSO 3: EDIÇÃO PROFISSIONAL ═══
        print(f"  🎬 Aplicando edição profissional:")
        print(f"     ✦ Face tracking → falante enquadrado")
        print(f"     ✦ Crop 9:16 zoom 108%")
        print(f"     ✦ Color grading + Sharpen + Vinheta")
        print(f"     ✦ Punch in branco + Fade out")
        print(f"     ✦ Barra de progresso dourada")
        print(f"     ✦ Legendas altas com keyword highlight")

        sucesso = aplicar_edicao_profissional(
            caminho_cortado, caminho_ass, caminho_final, duracao_clip
        )

        if not sucesso:
            print(f"  ⚠️ Edição falhou, usando vídeo base")
            shutil.copy2(caminho_cortado, caminho_final)

        # Limpa temporários
        if os.path.exists(caminho_cortado):
            try:
                os.remove(caminho_cortado)
            except Exception:
                pass

        clipes_editados.append(caminho_final)

        if os.path.exists(caminho_final):
            tamanho_mb = os.path.getsize(caminho_final) / (1024 * 1024)
            print(f"  ✅ Clipe {i} concluído ({tamanho_mb:.1f}MB): {caminho_final}")

    return clipes_editados


def salvar_lista_clips(clipes_editados, arquivo_saida="downloads/lista_clips.json"):
    """Salva a lista de vídeos editados em JSON."""
    try:
        dados = {
            "total_clipes": len(clipes_editados),
            "clipes": clipes_editados
        }
        with open(arquivo_saida, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Lista de clips salva em: {arquivo_saida}")
    except Exception as e:
        print(f"❌ Erro ao salvar lista: {e}")
