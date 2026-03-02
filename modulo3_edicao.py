"""
MÓDULO 3 - Edição Ultra-Profissional de Vídeos (V6 - Maximum Quality)

Pipeline por clipe:
  1. Cortar segmento (frame-exact re-encode, CRF 14 master quality)
  2. Jump cuts — remove silêncios com trim+concat (sincronia A/V perfeita)
  3. Gerar legendas ASS karaoke (palavra activa amarelo 108%, grupos de 3)
  4. Aplicar TODOS os efeitos profissionais num único passo FFmpeg
  5. Loop infinito seamless (dissolve + exponential audio crossfade)

Efeitos Ultra-Profissionais (World-Class):
  ✦ Jump cuts automáticos (trim+atrim+concat — sincronia A/V perfeita)
  ✦ DNN Face tracking inteligente (ResNet SSD — 95%+ accuracy)
  ✦ Breathing zoom dinâmico (1.00x↔1.03x, ciclo 8s) — vídeo sempre "vivo"
  ✦ Zoom 1.15x na face durante fala (exponential smoothing ultra-smooth)
  ✦ Color grading cinematográfico (contrast 1.05, saturation 1.15, gamma 1.02)
  ✦ Temporal denoise (hqdn3d=1.5:1.0:2.0:1.5)
  ✦ Sharpen adaptativo 5x5 (unsharp=5:5:0.6)
  ✦ Vinheta cinematográfica suave (vignette PI/4:0.35)
  ✦ Punch entry flash branco (0.15s) + Fade in/out suaves
  ✦ Barra de progresso neon animada com glow (cresce com t/duração)
  ✦ Legendas karaoke word-by-word: palavra activa amarelo 108%, inactivas 65%
  ✦ Layout split 60/40: conteúdo no topo + satisfying/gameplay em baixo
  ✦ Background desfocado nas margens (boxblur + eq dark)
  ✦ Loop infinito seamless (smoothup > dissolve > fade fallback)
  ✦ Encoding premium: CRF 14 / CQ 14, high profile, B-frames, AAC 192k
"""

import json
import subprocess
import os
import math
import shutil
import random


# ── Auto-download dos modelos DNN na primeira importação ──
def _garantir_modelos_dnn():
    """Verifica se os modelos DNN existem, senão tenta descarregar."""
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    prototxt = os.path.join(model_dir, "deploy.prototxt")
    caffemodel = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")
    if os.path.exists(prototxt) and os.path.exists(caffemodel):
        if os.path.getsize(caffemodel) > 1000:
            return  # modelos já existem
    try:
        from download_models import download_modelos
        download_modelos()
    except Exception:
        pass  # fallback para Haar cascade se não conseguir

_garantir_modelos_dnn()


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
    if not os.path.exists(caminho_video):
        print(f"⚠️ Ficheiro não encontrado: {caminho_video}")
        return None
    if os.path.getsize(caminho_video) < 1000:
        print(f"⚠️ Ficheiro demasiado pequeno/corrompido: {caminho_video}")
        return None
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            caminho_video
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        return float(res.stdout.strip())
    except Exception as e:
        print(f"⚠️ Erro ao obter duração de '{caminho_video}': {e}")
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


def obter_fps_video(caminho_video):
    """Retorna o FPS do vídeo."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=r_frame_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            caminho_video
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        frac = res.stdout.strip()
        if '/' in frac:
            num, den = map(int, frac.split('/'))
            return round(num / max(1, den), 2)
        return float(frac)
    except Exception:
        return 30.0


def _obter_duracao_video(caminho_video):
    """Retorna a duração do vídeo em segundos."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            caminho_video
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            dur = res.stdout.strip()
            if dur:
                return float(dur)
    except Exception:
        pass
    return 60.0  # fallback: assume 60 segundos


def formatar_tempo_ass(segundos):
    """Converte segundos (float) para formato ASS (H:MM:SS.cc)."""
    segundos = max(0, float(segundos))
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    cs = int((segundos % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ════════════════════════════════════════════════════════════
#  JUMP CUTS — CÁLCULO DE INTERVALOS DE FALA
# ════════════════════════════════════════════════════════════

def calcular_intervalos_fala(segmentos_whisper, inicio_corte, duracao_clip, merge_gap=0.35):
    """
    Calcula os intervalos de fala de um clip a partir dos segmentos Whisper.
    Usado para jump cuts, zoom dinâmico e sincronização de legendas.

    Returns:
        list: [[ini_rel, fim_rel], ...] em segundos relativos ao início do clip (t=0)
    """
    fim_corte = inicio_corte + duracao_clip
    margem = 0.06
    intervalos = []

    for seg in (segmentos_whisper or []):
        seg_ini = float(seg.get("inicio", 0))
        seg_fim = float(seg.get("fim", 0))
        if seg_fim < inicio_corte or seg_ini > fim_corte:
            continue
        ini_rel = max(0.0, seg_ini - inicio_corte - margem)
        fim_rel = min(duracao_clip, seg_fim - inicio_corte + margem)
        if fim_rel <= ini_rel:
            continue
        if intervalos and ini_rel <= intervalos[-1][1] + merge_gap:
            intervalos[-1][1] = max(intervalos[-1][1], fim_rel)
        else:
            intervalos.append([ini_rel, fim_rel])

    return intervalos


def _construir_filtro_concat(intervalos):
    """
    Constrói filter_complex com trim+atrim+concat para jump cuts com
    sincronismo áudio/vídeo PERFEITO.

    Ao contrário de select/aselect+setpts/asetpts (que causam drift
    progressivo porque frames de vídeo e áudio não se alinham perfeitamente),
    trim+atrim garante que cada segmento de áudio e vídeo tem EXACTAMENTE
    a mesma duração, e concat junta-os sequencialmente sem gaps.
    """
    partes = []
    for i, (ini, fim) in enumerate(intervalos):
        partes.append(
            f"[0:v]trim=start={ini:.3f}:end={fim:.3f},setpts=PTS-STARTPTS[v{i}]"
        )
        partes.append(
            f"[0:a]atrim=start={ini:.3f}:end={fim:.3f},asetpts=PTS-STARTPTS[a{i}]"
        )

    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(intervalos)))
    n = len(intervalos)
    partes.append(f"{concat_inputs}concat=n={n}:v=1:a=1[vout][aout]")

    return ";".join(partes)


def remap_tempo_clip(t, intervalos_jc):
    """
    Converte um timestamp original do clip (relativo a t=0 do clip antes dos jump cuts)
    para o timestamp equivalente depois dos jump cuts.

    Args:
        t: tempo original em segundos (relativo ao clip)
        intervalos_jc: lista [[ini, fim], ...] dos intervalos de fala mantidos

    Returns:
        float | None: novo timestamp após jump cuts, ou None se o momento foi cortado
    """
    if not intervalos_jc:
        return t  # sem remapping

    acumulado = 0.0
    for ini, fim in intervalos_jc:
        if t < ini:
            return None   # momento está num silêncio cortado
        if ini <= t <= fim:
            return acumulado + (t - ini)
        acumulado += fim - ini

    return None  # depois de todos os intervalos


# ════════════════════════════════════════════════════════════
#  GERAÇÃO DE LEGENDAS ASS (FORMATO PROFISSIONAL)
# ════════════════════════════════════════════════════════════

def gerar_legendas_ass(segmentos, caminho_ass, inicio_corte, duracao_corte, texto_hook="",
                       intervalos_jc=None, duracao_final=None):
    """
    Gera arquivo ASS com legendas profissionais estilo TikTok.

    Se intervalos_jc for fornecido, os timestamps são remapeados para
    compensar os silêncios removidos pelos jump cuts (sincronismo perfeito).

    Args:
        duracao_corte: duração ORIGINAL do clip (antes dos jump cuts)
        duracao_final: duração real do vídeo DEPOIS dos jump cuts (para clamping).
                       Se None, usa duracao_corte.

    Inclui:
    - Legendas dinâmicas word-by-word (grupos de 3 palavras)
    - Palavra activa em amarelo 108% opaque, inactivas a 65% opacity
    - Anti-alias \be1 para look polido móderno
    """
    if duracao_final is None:
        duracao_final = duracao_corte
    fim_corte = inicio_corte + duracao_corte

    # ── HEADER DO ARQUIVO ASS ──
    # PlayResX/Y = 1080x1920 (resolução do vídeo vertical)
    # Legendas posicionadas na zona inferior, bem enquadradas abaixo do vídeo
    # MarginV=160 → base do texto fica a ~160px do fundo, abaixo do conteúdo do vídeo
    header = """[Script Info]
Title: ClipAI Legendas Profissionais
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Legenda,Impact,100,&H00FFFFFF,&H000000FF,&H00000000,&HD2000000,-1,0,0,0,100,100,1,0,1,5,3,5,50,50,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    linhas_eventos = []

    # Hook de abertura REMOVIDO (conforme pedido)

    # ── LEGENDAS DINÂMICAS (KARAOKE WORD-BY-WORD) ──
    # Estratégia: agrupa palavras em grupos de 3 para dar contexto visual,
    # mas cria UM evento por PALAVRA — cada evento tem a palavra activa a
    # amarelo e as restantes do grupo a branco. Timing exacto do Whisper.
    legendas = []

    def _montar_grupo(words, idx_activo):
        """
        Devolve a string ASS para um grupo de palavras onde a palavra activa
        fica a amarelo, ligeiramente maior (108%) e totalmente opaca, enquanto
        as restantes ficam brancas a 65% de opacidade — efeito de elevação visual
        sem layout shift, sem fade intermédio.

        Cores ASS (ABGR):
          &H0000FFFF& = amarelo   &H00FFFFFF& = branco
          &H60& = alpha ~62% opaco (inactive)   &H00& = totalmente opaco
        """
        partes = []
        for m, w in enumerate(words):
            if m == idx_activo:
                # Palavra activa: amarelo, scale 108%, totalmente opaca e nítida
                partes.append(
                    f"{{\\c&H0000FFFF&\\fscx108\\fscy108\\alpha&H00&}}{w}"
                    f"{{\\fscx100\\fscy100\\c&H00FFFFFF&}}"
                )
            else:
                # Palavras inactivas: branco, 65% opacidade (recuam visualmente)
                partes.append(
                    f"{{\\alpha&H60&}}{w}{{\\alpha&H00&}}"
                )
        return " ".join(partes)

    if segmentos:
        for seg in segmentos:
            seg_ini = seg.get("inicio", 0)
            seg_fim = seg.get("fim", 0)

            if seg_fim < inicio_corte or seg_ini > fim_corte:
                continue

            # ── COM TIMESTAMPS POR PALAVRA (Whisper word_timestamps=True) ──
            if "palavras" in seg and seg["palavras"] and len(seg["palavras"]) > 0:
                palavras = seg["palavras"]
                tamanho_grupo = 3

                for j in range(0, len(palavras), tamanho_grupo):
                    grupo = palavras[j:j + tamanho_grupo]
                    if not grupo:
                        continue

                    # Textos em maiúsculas para o grupo inteiro
                    words = [str(p.get("palavra", "")).strip().upper() for p in grupo]
                    words = [w for w in words if w]
                    if not words:
                        continue

                    # Um evento por palavra — timing exacto do Whisper
                    for k, p in enumerate(grupo[:len(words)]):
                        t_word_ini_raw = max(0, float(p.get("inicio", 0)) - inicio_corte)

                        # A palavra activa dura até ao início da próxima
                        if k + 1 < len(grupo):
                            t_word_end_raw = max(0, float(grupo[k + 1].get("inicio", 0)) - inicio_corte)
                        else:
                            t_word_end_raw = max(0, float(p.get("fim", 0)) - inicio_corte)

                        # Sanidade (antes do remap — usa duração ORIGINAL)
                        if t_word_end_raw <= 0:
                            continue
                        if t_word_end_raw <= t_word_ini_raw:
                            t_word_end_raw = t_word_ini_raw + 0.15

                        # ── REMAP após jump cuts ──
                        if intervalos_jc:
                            # Filtra contra duração original (pré-jump-cut)
                            if t_word_ini_raw >= duracao_corte:
                                continue
                            t_word_ini = remap_tempo_clip(t_word_ini_raw, intervalos_jc)
                            t_word_end = remap_tempo_clip(t_word_end_raw, intervalos_jc)
                            # Palavra foi cortada (está num silêncio removido)
                            if t_word_ini is None:
                                continue
                            if t_word_end is None:
                                # Palavra termina num silêncio — usa o ini + duration
                                dur_original = t_word_end_raw - t_word_ini_raw
                                t_word_end = t_word_ini + dur_original
                        else:
                            t_word_ini = t_word_ini_raw
                            t_word_end = t_word_end_raw
                            # Sem jump cuts: filtra contra a duração do clip
                            if t_word_ini >= duracao_corte:
                                continue

                        # Clamp ao final do vídeo REAL (pós-jump-cut)
                        t_word_end = min(t_word_end, duracao_final)
                        if t_word_end - t_word_ini < 0.05:
                            continue

                        texto = _montar_grupo(words, k)
                        legendas.append((t_word_ini, t_word_end, texto))

            else:
                # ── SEM TIMESTAMPS POR PALAVRA: divide o segmento por palavra ──
                t_ini = max(0, float(seg_ini) - inicio_corte)
                t_end = max(0, float(seg_fim) - inicio_corte)

                if t_ini >= duracao_corte or t_end <= 0 or t_ini >= t_end:
                    continue
                t_end = min(t_end, duracao_final)

                texto_seg = str(seg.get("texto", "")).strip().upper()
                if not texto_seg:
                    continue

                pals = texto_seg.split()
                if not pals:
                    continue

                gs = 3
                dur_por_palavra = (t_end - t_ini) / max(1, len(pals))

                for j in range(0, len(pals), gs):
                    grupo_pals = pals[j:j + gs]
                    for k, pal in enumerate(grupo_pals):
                        idx_global = j + k
                        t_w_ini = t_ini + idx_global * dur_por_palavra
                        t_w_end = t_w_ini + dur_por_palavra
                        t_w_end = min(t_w_end, t_end)
                        if t_w_end - t_w_ini < 0.05:
                            continue
                        texto = _montar_grupo(grupo_pals, k)
                        legendas.append((t_w_ini, t_w_end, texto))

    # Fallback se não tem legendas
    if not legendas:
        legendas.append((0, min(5, duracao_final), "{\\c&H00FFFFFF&}..."))

    # ── GERA LINHAS DE DIÁLOGO ──
    for t_ini, t_end, texto in legendas:
        t_inicio_str = formatar_tempo_ass(t_ini)
        t_fim_str = formatar_tempo_ass(t_end)
        # Limpa caracteres que podem quebrar o ASS (exceto os overrides intencionais)
        texto_limpo = texto.replace("\n", " ").replace("\\n", " ")
        # \be1 = borda suavizada (anti-alias); SEM \fad para evitar flicker entre palavras
        linhas_eventos.append(
            f"Dialogue: 0,{t_inicio_str},{t_fim_str},Legenda,,0,0,0,,{{\\be1}}{texto_limpo}"
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
    """
    Corta um segmento do vídeo com re-encode frame-exacto.

    NÃO usamos stream copy: com stream copy, o output começa no keyframe
    mais próximo ANTES de inicio_seg, deslocando o PTS e dessincronizando
    as legendas em todos os clips excepto o primeiro.
    Com -ss ANTES de -i + re-encode, o cut é exacto ao frame e o output
    começa sempre em PTS=0, garantindo sincronismo perfeito das legendas.
    """
    # Validação do ficheiro de entrada
    if not os.path.exists(caminho_video):
        print(f"  ❌ Vídeo de entrada não encontrado: {caminho_video}")
        return False
    tamanho = os.path.getsize(caminho_video)
    if tamanho < 5000:
        print(f"  ❌ Vídeo de entrada corrompido/vazio ({tamanho} bytes): {caminho_video}")
        return False

    try:
        # Tenta NVENC primeiro (GPU, muito rápido e alta qualidade)
        comando_nvenc = [
            'ffmpeg',
            '-ss', str(inicio_seg),
            '-i', caminho_video,
            '-t', str(duracao_seg),
            '-c:v', 'h264_nvenc', '-preset', 'p4', '-rc:v', 'vbr', '-cq:v', '18',
            '-c:a', 'aac', '-b:a', '192k',
            '-avoid_negative_ts', 'make_zero',
            '-y', caminho_saida
        ]
        resultado = subprocess.run(comando_nvenc, capture_output=True, text=True, timeout=120)
        if resultado.returncode == 0 and os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 1000:
            return True

        # Fallback: libx264 ultrafast (rápido, boa qualidade)
        comando = [
            'ffmpeg',
            '-ss', str(inicio_seg),
            '-i', caminho_video,
            '-t', str(duracao_seg),
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '18',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-avoid_negative_ts', 'make_zero',
            '-y', caminho_saida
        ]
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=180)

        if resultado.returncode != 0:
            print(f"  ⚠️ Corte ultrafast falhou, tentando fast...")
            stderr_preview = resultado.stderr[-300:] if resultado.stderr else "sem stderr"
            print(f"     Erro: {stderr_preview}")
            comando_fb = [
                'ffmpeg',
                '-ss', str(inicio_seg),
                '-i', caminho_video,
                '-t', str(duracao_seg),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '18',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-y', caminho_saida
            ]
            resultado = subprocess.run(comando_fb, capture_output=True, text=True, timeout=300)
            if resultado.returncode != 0:
                stderr_fb = resultado.stderr[-300:] if resultado.stderr else "sem stderr"
                print(f"  ❌ Corte fast também falhou: {stderr_fb}")
                return False

        # Valida output
        if not os.path.exists(caminho_saida) or os.path.getsize(caminho_saida) < 1000:
            print(f"  ❌ Output de corte inválido ou vazio")
            return False

        return True
    except subprocess.TimeoutExpired:
        print(f"  ❌ Timeout no corte do vídeo")
        return False
    except Exception as e:
        print(f"  ❌ Erro ao cortar vídeo: {e}")
        return False


# ════════════════════════════════════════════════════════════
#  DETEÇÃO DE FACE PARA CROP INTELIGENTE
# ════════════════════════════════════════════════════════════

def _carregar_dnn_face_detector():
    """
    Carrega o detector de faces DNN (ResNet SSD) do OpenCV.
    Muito mais preciso que Haar cascades (~95% accuracy vs ~60-70%).
    Detecta faces em ângulos, iluminação difícil e parcialmente oclusas.

    Fallback: Haar cascade se o DNN não estiver disponível.
    """
    try:
        import cv2
        # Tenta DNN ResNet SSD (built-in no OpenCV 3.3+)
        model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        prototxt = os.path.join(model_dir, "deploy.prototxt")
        caffemodel = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")

        if os.path.exists(prototxt) and os.path.exists(caffemodel):
            net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
            print("  🧠 DNN face detector (ResNet SSD) carregado")
            return "dnn", net

        # Fallback: Haar cascade
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if not face_cascade.empty():
            print("  ℹ️  Usar Haar cascade (instala modelos DNN para melhor precisão)")
            return "haar", face_cascade

        return None, None
    except Exception:
        return None, None


def _detectar_faces_dnn(net, frame, conf_threshold=0.55):
    """
    Detecta faces usando DNN ResNet SSD.
    Retorna lista de (x, y, w, h, confidence) em coordenadas do frame original.
    """
    import cv2
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(
        cv2.resize(frame, (300, 300)), 1.0, (300, 300),
        (104.0, 177.0, 123.0), swapRB=False, crop=False
    )
    net.setInput(blob)
    detections = net.forward()

    faces = []
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence < conf_threshold:
            continue
        box = detections[0, 0, i, 3:7] * [w, h, w, h]
        x1, y1, x2, y2 = box.astype(int)
        face_w = x2 - x1
        face_h = y2 - y1
        if face_w > 20 and face_h > 20:
            faces.append((x1, y1, face_w, face_h, float(confidence)))
    return faces


def _detectar_faces_haar(cascade, gray_frame, scale=1.0):
    """
    Detecta faces usando Haar cascade (fallback).
    Retorna lista de (x, y, w, h, confidence=0.5).
    """
    faces = cascade.detectMultiScale(
        gray_frame, scaleFactor=1.1, minNeighbors=5,
        minSize=(40, 40)
    )
    result = []
    for (x, y, w, h) in faces:
        rx = int(x / scale)
        ry = int(y / scale)
        rw = int(w / scale)
        rh = int(h / scale)
        result.append((rx, ry, rw, rh, 0.5))
    return result


def _suavizar_tracking(posicoes, window=5):
    """
    Aplica suavização de média móvel às posições de tracking.
    Elimina saltos bruscos entre frames para um crop ultra-smooth.
    """
    if len(posicoes) < window:
        return posicoes

    suavizado = []
    for i in range(len(posicoes)):
        start = max(0, i - window // 2)
        end = min(len(posicoes), i + window // 2 + 1)
        janela = posicoes[start:end]
        media_x = sum(p[0] for p in janela) / len(janela)
        media_y = sum(p[1] for p in janela) / len(janela)
        suavizado.append((media_x, media_y))
    return suavizado


def detectar_centro_falante(caminho_video, largura_video, altura_video, crop_w, crop_h):
    """
    Deteta a posição do falante usando DNN face detection (ResNet SSD).
    Muito superior ao Haar cascade: ~95% accuracy, detecta faces em ângulo,
    iluminação difícil, e parcialmente oclusas.

    Pipeline:
      1. Carrega detector DNN (fallback: Haar cascade)
      2. Amostra frames a cada 1s (mais granular que antes)
      3. Detecta faces com confidence weighting
      4. Aplica suavização temporal (média móvel window=7)
      5. Calcula posição mediana ponderada por confiança
      6. Enquadra com regra dos terços (face a 30% do topo)

    Retorna (x_off, y_off) para o crop FFmpeg.
    Fallback: centro horizontal, terço superior vertical.
    """
    fallback_x = (largura_video - crop_w) // 2
    fallback_y = max(0, (altura_video - crop_h) // 3)
    try:
        import cv2

        # ── Carrega detector (DNN > Haar) ──
        detector_type, detector = _carregar_dnn_face_detector()
        if detector is None:
            print("  ℹ️  Nenhum detector de faces disponível → crop central")
            return fallback_x, fallback_y

        cap = cv2.VideoCapture(caminho_video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        # Amostra a cada 1 segundo (mais granular = tracking mais suave)
        sample_interval = max(1, int(fps * 1.0))
        deteccoes = []  # lista de (cx, cy, confidence)
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_interval == 0:
                faces = []
                if detector_type == "dnn":
                    faces = _detectar_faces_dnn(detector, frame, conf_threshold=0.65)
                elif detector_type == "haar":
                    scale = 0.4
                    small = cv2.resize(frame, None, fx=scale, fy=scale)
                    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                    faces = _detectar_faces_haar(detector, gray, scale)

                if faces:
                    # Seleciona a face com maior confiança (mais fiável)
                    best = max(faces, key=lambda f: f[4])
                    x, y, w, h, conf = best
                    cx = x + w // 2
                    cy = y + h // 2
                    deteccoes.append((cx, cy, conf))

            frame_idx += 1

        cap.release()

        if not deteccoes:
            print("  ℹ️  Nenhuma face detetada → crop central")
            return fallback_x, fallback_y

        # ── Mínimo de deteções para ser fiável ──
        total_amostras = max(1, total_frames // sample_interval)
        det_rate = len(deteccoes) / total_amostras
        if det_rate < 0.25:
            print(f"  ℹ️  Poucas faces detetadas ({det_rate:.0%}) → crop central")
            return fallback_x, fallback_y

        # ── Suavização temporal ──
        posicoes_raw = [(d[0], d[1]) for d in deteccoes]
        posicoes_smooth = _suavizar_tracking(posicoes_raw, window=7)

        # ── Mediana ponderada por confiança ──
        total_conf = sum(d[2] for d in deteccoes)
        if total_conf > 0:
            weighted_cx = sum(posicoes_smooth[i][0] * deteccoes[i][2] for i in range(len(deteccoes))) / total_conf
            weighted_cy = sum(posicoes_smooth[i][1] * deteccoes[i][2] for i in range(len(deteccoes))) / total_conf
        else:
            cx_sorted = sorted(p[0] for p in posicoes_smooth)
            cy_sorted = sorted(p[1] for p in posicoes_smooth)
            weighted_cx = cx_sorted[len(cx_sorted) // 2]
            weighted_cy = cy_sorted[len(cy_sorted) // 2]

        median_cx = int(weighted_cx)
        median_cy = int(weighted_cy)

        # Regra dos terços: face a 30% do topo do enquadramento
        x_off = max(0, min(largura_video - crop_w, median_cx - crop_w // 2))
        y_off = max(0, min(altura_video - crop_h, int(median_cy - crop_h * 0.30)))

        avg_conf = total_conf / len(deteccoes) if deteccoes else 0
        det_rate = len(deteccoes) / max(1, total_frames // sample_interval) * 100
        print(f"  🧠 Face DNN: ({median_cx}, {median_cy}) conf={avg_conf:.0%} det={det_rate:.0f}% → crop ({x_off}, {y_off})")
        return x_off, y_off

    except ImportError:
        print("  ℹ️  OpenCV não disponível → crop central")
        return fallback_x, fallback_y
    except Exception as e:
        print(f"  ⚠️ Deteção de face falhou: {e}")
        return fallback_x, fallback_y


# ════════════════════════════════════════════════════════════
#  DETEÇÃO DE WEBCAM OVERLAY
# ════════════════════════════════════════════════════════════

def detetar_webcam(caminho_video, w_video, h_video):
    """
    Deteta se o vídeo tem uma webcam overlay num canto.

    Procura faces pequenas (<30% do frame) que aparecem consistentemente
    na mesma posição num dos 4 cantos. Típico de vídeos de gaming/streaming.

    Returns:
        dict | None: {'x','y','w','h','face_cx','face_cy','face_w','face_h','corner'}
                     ou None se não detetada.
    """
    try:
        import cv2

        detector_type, detector = _carregar_dnn_face_detector()
        if detector is None:
            return None

        cap = cv2.VideoCapture(caminho_video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        sample_interval = max(1, int(fps * 1.5))
        frame_idx = 0
        corner_faces = {'br': [], 'bl': [], 'tr': [], 'tl': []}

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_interval == 0:
                if detector_type == "dnn":
                    faces = _detectar_faces_dnn(detector, frame, conf_threshold=0.55)
                elif detector_type == "haar":
                    scale = 0.4
                    small = cv2.resize(frame, None, fx=scale, fy=scale)
                    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                    faces = _detectar_faces_haar(detector, gray, scale)
                else:
                    faces = []

                for (x, y, fw, fh, conf) in faces:
                    # Ignora faces grandes (>30% frame) — não são webcam overlay
                    if fw > w_video * 0.30 or fh > h_video * 0.30:
                        continue
                    if fw < 30 or fh < 30:
                        continue

                    cx = x + fw // 2
                    cy = y + fh // 2

                    right = cx > w_video * 0.60
                    left = cx < w_video * 0.40
                    bottom = cy > h_video * 0.55
                    top = cy < h_video * 0.45

                    if right and bottom:
                        corner_faces['br'].append((cx, cy, fw, fh, conf))
                    elif left and bottom:
                        corner_faces['bl'].append((cx, cy, fw, fh, conf))
                    elif right and top:
                        corner_faces['tr'].append((cx, cy, fw, fh, conf))
                    elif left and top:
                        corner_faces['tl'].append((cx, cy, fw, fh, conf))

            frame_idx += 1

        cap.release()

        # Precisa de deteções consistentes
        total_samples = max(1, total_frames // sample_interval)
        min_det = max(3, int(total_samples * 0.20))

        best_corner = None
        best_count = 0
        for corner, fl in corner_faces.items():
            if len(fl) > best_count:
                best_count = len(fl)
                best_corner = corner

        if best_corner is None or best_count < min_det:
            return None

        fl = corner_faces[best_corner]
        avg_cx = int(sum(f[0] for f in fl) / len(fl))
        avg_cy = int(sum(f[1] for f in fl) / len(fl))
        avg_fw = int(sum(f[2] for f in fl) / len(fl))
        avg_fh = int(sum(f[3] for f in fl) / len(fl))

        # Estima região da webcam (face ≈40% da largura da webcam)
        cam_w = min(int(avg_fw * 3.0), int(w_video * 0.35))
        cam_h = min(int(avg_fh * 3.5), int(h_video * 0.40))

        # Snap ao canto
        if 'r' in best_corner:
            cam_x = max(0, w_video - cam_w)
        else:
            cam_x = 0
        if 'b' in best_corner:
            cam_y = max(0, h_video - cam_h)
        else:
            cam_y = 0

        cam_w = min(cam_w, w_video - cam_x)
        cam_h = min(cam_h, h_video - cam_y)

        corner_names = {'br': 'inferior-direito', 'bl': 'inferior-esquerdo',
                        'tr': 'superior-direito', 'tl': 'superior-esquerdo'}

        print(f"  📷 Webcam detetada: {corner_names[best_corner]} ({cam_w}x{cam_h})")
        print(f"     Face: ({avg_cx},{avg_cy}) tamanho={avg_fw}x{avg_fh} det={best_count}/{total_samples}")

        return {
            'x': cam_x, 'y': cam_y, 'w': cam_w, 'h': cam_h,
            'face_cx': avg_cx, 'face_cy': avg_cy,
            'face_w': avg_fw, 'face_h': avg_fh,
            'corner': best_corner
        }

    except ImportError:
        return None
    except Exception as e:
        print(f"  ⚠️ Erro na deteção de webcam: {e}")
        return None


# ════════════════════════════════════════════════════════════
#  DETEÇÃO DE FACE — INFORMAÇÃO DETALHADA PARA ZOOM DINÂMICO
# ════════════════════════════════════════════════════════════

def detectar_face_info(caminho_video):
    """
    Deteta a face principal e retorna informação detalhada.
    Usado para zoom dinâmico (posição relativa da face no frame).

    Returns:
        dict: {"cx": int, "cy": int, "cx_pct": float, "cy_pct": float,
               "avg_conf": float, "det_rate": float}
        ou None se nenhuma face detetada.
    """
    try:
        import cv2
        w, h = obter_dimensoes_video(caminho_video)
        if not w or not h:
            return None

        detector_type, detector = _carregar_dnn_face_detector()
        if detector is None:
            return None

        cap = cv2.VideoCapture(caminho_video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        sample_interval = max(1, int(fps * 1.0))
        deteccoes = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_interval == 0:
                faces = []
                if detector_type == "dnn":
                    faces = _detectar_faces_dnn(detector, frame, conf_threshold=0.60)
                elif detector_type == "haar":
                    scale = 0.4
                    small = cv2.resize(frame, None, fx=scale, fy=scale)
                    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                    faces = _detectar_faces_haar(detector, gray, scale)
                if faces:
                    best = max(faces, key=lambda f: f[4])
                    x, y, fw, fh, conf = best
                    deteccoes.append((x + fw // 2, y + fh // 2, conf))
            frame_idx += 1

        cap.release()

        if not deteccoes:
            return None

        total_amostras = max(1, total_frames // sample_interval)
        det_rate = len(deteccoes) / total_amostras
        if det_rate < 0.20:
            return None

        # Suavização e mediana ponderada
        total_conf = sum(d[2] for d in deteccoes)
        if total_conf > 0:
            wcx = sum(d[0] * d[2] for d in deteccoes) / total_conf
            wcy = sum(d[1] * d[2] for d in deteccoes) / total_conf
        else:
            wcx = sum(d[0] for d in deteccoes) / len(deteccoes)
            wcy = sum(d[1] for d in deteccoes) / len(deteccoes)

        cx = int(wcx)
        cy = int(wcy)
        avg_conf = total_conf / len(deteccoes) if deteccoes else 0

        return {
            "cx": cx, "cy": cy,
            "cx_pct": cx / w, "cy_pct": cy / h,
            "avg_conf": avg_conf, "det_rate": det_rate,
            "video_w": w, "video_h": h
        }
    except Exception:
        return None


# ════════════════════════════════════════════════════════════
#  ZOOM DINÂMICO INTELIGENTE BASEADO EM FALA
# ════════════════════════════════════════════════════════════

def gerar_filtro_zoom_dinamico(intervalos_fala, duracao, face_x_pct, face_y_pct, fps=30,
                               out_w=1080, out_h=1920):
    """
    Gera filtro FFmpeg zoompan para zoom dinâmico baseado em fala.

    Quando a pessoa FALA: zoom suave 1.15x centrado na face.
    Quando NÃO fala: volta suavemente ao plano geral (1.0x).
    Transição ultra-smooth via exponential smoothing (pzoom).

    TAMBÉM aplica um breathing zoom subtil (1.00x ↔ 1.03x, ciclo 8s)
    que mantém o vídeo "vivo" mesmo sem fala.

    Args:
        intervalos_fala: [[ini, fim], ...] intervalos de fala relativos ao clip
        duracao: duração total do clip em segundos
        face_x_pct: posição X da face na frame composta (0.0-1.0)
        face_y_pct: posição Y da face na frame composta (0.0-1.0)
        fps: framerate do vídeo

    Returns:
        str: filtro zoompan FFmpeg ou None
    """
    if not intervalos_fala:
        # Mesmo sem intervalos de fala, aplica breathing zoom muito subtil
        # Amplitude reduzida (0.007) e ciclo longo (12s) para evitar tremores
        breathing = "1.0+0.007*sin(2*PI*on/(12*{fps}))".replace("{fps}", str(fps))
        return (
            f"zoompan=z='{breathing}'"
            f":x='(iw-iw/zoom)*0.5':y='(ih-ih/zoom)*0.5'"
            f":d=1:s={out_w}x{out_h}:fps={fps}"
        )

    # Build between conditions para frames de fala
    conds = []
    for ini, fim in intervalos_fala:
        f_start = max(0, int(ini * fps))
        f_end = int(fim * fps)
        conds.append(f"between(on,{f_start},{f_end})")

    if not conds:
        return None

    speech_cond = "+".join(conds)

    # Expressão de zoom com smooth lerp (exponential smoothing via pzoom)
    # Breathing muito subtil (±0.007, ciclo 12s) para não tremer
    # Speech zoom suave (+0.12) com rate lento (0.012 ≈ 3-4s para convergir)
    breathing_base = f"1.0+0.007*sin(2*PI*on/(12*{fps}))"
    zoom_expr = (
        f"min(1.15,max(1.0,"
        f"if(eq(on,0),1.0,"
        f"pzoom+((({breathing_base})+0.12*min(1,{speech_cond}))-pzoom)*0.012)))"
    )

    # Posição: centra na face quando zoomed, centro da frame quando normal
    x_expr = f"(iw-iw/zoom)*{face_x_pct:.4f}"
    y_expr = f"(ih-ih/zoom)*{face_y_pct:.4f}"

    return (
        f"zoompan=z='{zoom_expr}'"
        f":x='{x_expr}':y='{y_expr}'"
        f":d=1:s={out_w}x{out_h}:fps={fps}"
    )


# Playlist de vídeos satisfatórios (gameplay, parkour, cooking, etc.)
_PLAYLIST_SATISFATORIA = "https://youtube.com/playlist?list=PL8LwzmTmvN4x8w6oFo5u9R8fUsBBl8Af6"


def _encontrar_video_satisfatorio():
    """
    Devolve um vídeo satisfatório aleatório de downloads/satisfying/.
    Se a pasta estiver vazia, descarrega automaticamente 5 vídeos
    aleatórios da playlist _PLAYLIST_SATISFATORIA.

    Returns:
        str | None: caminho do vídeo ou None se não conseguir obter nenhum.
    """
    pasta = os.path.join("downloads", "satisfying")
    os.makedirs(pasta, exist_ok=True)
    exts = ('.mp4', '.avi', '.mov', '.mkv', '.webm')

    def _listar():
        return [
            os.path.join(pasta, f) for f in os.listdir(pasta)
            if f.lower().endswith(exts) and os.path.isfile(os.path.join(pasta, f))
        ]

    videos = _listar()

    # Auto-download da playlist se pasta vazia
    if not videos:
        print("  📥 Pasta satisfying vazia — a descarregar da playlist...")
        try:
            from modulo1_download import baixar_playlist_satisfatoria
            baixar_playlist_satisfatoria(_PLAYLIST_SATISFATORIA, n_videos=5, pasta_destino=pasta)
            videos = _listar()
        except Exception as e:
            print(f"  ⚠️ Erro ao descarregar playlist satisfatória: {e}")

    if not videos:
        print("  ⚠️ Sem vídeos satisfatórios disponíveis, usando layout full-screen")
        return None

    escolhido = random.choice(videos)
    print(f"  🎮 Vídeo satisfatório: {os.path.basename(escolhido)}")
    return escolhido


def gerar_metadados_youtube(titulo_clip, razao_clip, duracao_seg=50, idioma="pt-PT"):
    """
    Gera título e descrição em Português otimizados para YouTube com máximo engajamento.

    Estratégia:
      - Título: hook + [Duração] + #Viral
      - Descrição: resumo + razão do clipe + hashtags virais de trending topics
      - Hashtags: #Shorts, #Viral, #FYP, + domínio específico
    """
    emoji_dict = {
        "polemic": "😤🔥",
        "relatable": "💯😂",
        "surprising": "😲🤯",
        "emotional": "😢❤️",
        "strong": "💪🔥",
        "rhythm": "🎵⚡"
    }

    # Detecta trigger do clipe para customizar title
    trigger = "Viral"
    trigger_pt = "Viral"
    for palavra_chave, emoji in emoji_dict.items():
        if palavra_chave.lower() in razao_clip.lower():
            trigger = palavra_chave.replace("_", " ").title()
            mapa_trigger_pt = {
                "Polemic": "Polémico",
                "Relatable": "Identificável",
                "Surprising": "Surpreendente",
                "Emotional": "Emocional",
                "Strong": "Impactante",
                "Rhythm": "Ritmo Alto"
            }
            trigger_pt = mapa_trigger_pt.get(trigger, "Viral")
            emoji_trigger = emoji
            break
    else:
        emoji_trigger = "🔥"

    # Título: Hook + Trigger + Duração + CTA + Hashtags
    titulo = f"{titulo_clip} {emoji_trigger} | Momento {trigger_pt}"
    if len(titulo) > 60:
        titulo = titulo[:57] + "..."

    # Descrição com razão e hashtags virais
    descricao = f"""{titulo_clip}

{razao_clip}

━━━━━━━━━━━━━━━━━━━━

⏱️ Duração: {int(duracao_seg)}s
💡 Categoria: {trigger_pt}

🚀 HASHTAGS VIRAIS:
#Shorts #YouTubeShorts #Viral #Tendencia #Portugal #Portugues #FYP #ParaTi #ConteudoViral #Clipes #Podcast #IA 

━━━━━━━━━━━━━━━━━━━━

📢 Junte-se à comunidade de criadores virais!
Cada clipe é editado com IA para máximo engajamento.
"""

    return {
        "titulo": titulo,
        "descricao": descricao,
        "hashtags": "#Shorts #YouTubeShorts #Viral #Tendencia #Portugal #Portugues #FYP #ParaTi #ConteudoViral #Clipes #Podcast #IA",
        "trigger": trigger,
        "emojis": emoji_trigger
    }


# ════════════════════════════════════════════════════════════
#  EDIÇÃO PROFISSIONAL (TUDO NUM ÚNICO PASSO FFMPEG)
# ════════════════════════════════════════════════════════════

def aplicar_edicao_profissional(caminho_video, caminho_ass, caminho_saida, duracao_clip,
                                intervalos_fala=None, face_info=None):
    """
    Aplica edição profissional: blurred BG + vídeo completo + zoom dinâmico.

    Layout (1080x1920):
      ┌────────────────┐
      │  Blurred BG    │
      │  ┌──────────┐  │
      │  │ FULL VIDEO │  │
      │  └──────────┘  │
      │  LEGENDAS       │
      └────────────────┘
      + Zoom dinâmico suave na face durante fala
    """
    try:
        w, h = obter_dimensoes_video(caminho_video)
        if not w or not h:
            print("  ⚠️ Não foi possível obter dimensões do vídeo")
            return False

        return _aplicar_edicao_standard(caminho_video, caminho_ass, caminho_saida,
                                          duracao_clip, w, h,
                                          intervalos_fala=intervalos_fala,
                                          face_info=face_info)
    except subprocess.TimeoutExpired:
        print("  ⚠️ FFmpeg timeout")
        return False
    except Exception as e:
        print(f"  ❌ Erro na edição: {e}")
        return False


# ════════════════════════════════════════════════════════════
#  ENCODING HELPERS
# ════════════════════════════════════════════════════════════

def _encode_com_filtros(caminho_video, caminho_saida, vf=None, filter_complex=None,
                        duracao_clip=None):
    """
    Codifica o vídeo com NVENC (GPU) ou libx264 (CPU fallback) — qualidade máxima.
    Aceita -vf (filtro simples) OU -filter_complex (grafos com split/overlay).
    Qualidade optimizada para TikTok/Shorts (1080x1920, ~12-20Mbps, AAC 192k).
    """
    if filter_complex:
        # Áudio: reset PTS + fade in/out suave (sincronizado com fades de vídeo)
        # O delay era causado por fps impreciso no zoompan (int() truncava 29.97→29).
        # Agora com fps exacto, o áudio mantém-se sincronizado.
        audio_chain = "[0:a]asetpts=PTS-STARTPTS"
        if duracao_clip and duracao_clip > 1.0:
            fade_out_start = max(0, duracao_clip - 0.6)
            audio_chain += f",afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out_start:.2f}:d=0.6"
        audio_chain += "[aout]"
        fc_sync = filter_complex + ";" + audio_chain
        filtro_args = ['-filter_complex', fc_sync, '-map', '[out]', '-map', '[aout]']
    elif vf:
        filtro_args = ['-vf', vf]
    else:
        filtro_args = []

    # ── NVENC (GPU — qualidade máxima TikTok) ──
    cmd = [
        'ffmpeg', '-noautorotate', '-i', caminho_video,
        *filtro_args,
        '-c:v', 'h264_nvenc', '-preset', 'p7', '-profile:v', 'high',
        '-rc:v', 'vbr', '-cq:v', '14', '-b:v', '12M',
        '-maxrate', '20M', '-bufsize', '40M',
        '-bf:v', '3', '-g', '60', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
        '-movflags', '+faststart', '-y', caminho_saida
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if res.returncode == 0 and os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 1000:
        print("  ⚡ NVENC P7 (GPU qualidade máxima)")
        return True

    # ── libx264 qualidade máxima ──
    cmd2 = [
        'ffmpeg', '-noautorotate', '-i', caminho_video,
        *filtro_args,
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '14',
        '-profile:v', 'high', '-level', '4.2', '-bf', '3',
        '-maxrate', '20M', '-bufsize', '40M',
        '-threads', '0', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
        '-movflags', '+faststart', '-y', caminho_saida
    ]
    res2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=900)
    if res2.returncode == 0 and os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 1000:
        return True

    # ── Fallback sem legendas ──
    if vf:
        filtros_sem_leg = [f for f in vf.split(',') if not f.startswith('subtitles=')]
        vf_fb = ','.join(filtros_sem_leg)
        cmd3 = [
            'ffmpeg', '-noautorotate', '-i', caminho_video,
            '-vf', vf_fb,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-threads', '0', '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart', '-y', caminho_saida
        ]
        res3 = subprocess.run(cmd3, capture_output=True, text=True, timeout=600)
        if res3.returncode == 0:
            print("  ⚠️ Sem legendas (fallback)")
            return True

    # ── Fallback mínimo ──
    cmd_min = [
        'ffmpeg', '-noautorotate', '-i', caminho_video,
        '-vf', 'scale=1080:1920:flags=lanczos:force_original_aspect_ratio=decrease,'
               'pad=1080:1920:(ow-iw)/2:(oh-ih)/2:0x0f0f14,format=yuv420p',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
        '-threads', '0', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart', '-y', caminho_saida
    ]
    res_min = subprocess.run(cmd_min, capture_output=True, text=True, timeout=600)
    if res_min.returncode == 0:
        print("  ⚠️ Modo mínimo (sem efeitos)")
        return True

    print(f"  ❌ Todos os fallbacks falharam: {res2.stderr[-500:]}")
    return False


def _encode_com_filtros_2in(caminho_video, caminho_video2, caminho_saida,
                            filter_complex, duracao):
    """
    Codifica com dois inputs de vídeo (ex: main + satisfying).
    Input [0] = main video (audio), Input [1] = satisfying video (sem audio, loopado).
    Qualidade máxima TikTok.
    """
    # Áudio: reset PTS + fade in/out suave (delay corrigido pelo fps exacto no zoompan)
    audio_chain = "[0:a]asetpts=PTS-STARTPTS"
    if duracao and duracao > 1.0:
        fade_out_start = max(0, duracao - 0.6)
        audio_chain += f",afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out_start:.2f}:d=0.6"
    audio_chain += "[aout2]"
    fc_sync = filter_complex + ";" + audio_chain

    # ── NVENC ──
    cmd = [
        'ffmpeg', '-noautorotate',
        '-i', caminho_video,
        '-stream_loop', '-1', '-i', caminho_video2,
        '-filter_complex', fc_sync,
        '-map', '[out]', '-map', '[aout2]',
        '-t', str(duracao),
        '-c:v', 'h264_nvenc', '-preset', 'p7', '-profile:v', 'high',
        '-rc:v', 'vbr', '-cq:v', '14', '-b:v', '12M',
        '-maxrate', '20M', '-bufsize', '40M',
        '-bf:v', '3', '-g', '60', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
        '-movflags', '+faststart', '-y', caminho_saida
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if res.returncode == 0 and os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 1000:
        print("  ⚡ NVENC P7 2-input (GPU qualidade máxima)")
        return True

    # ── libx264 fallback ──
    cmd2 = [
        'ffmpeg', '-noautorotate',
        '-i', caminho_video,
        '-stream_loop', '-1', '-i', caminho_video2,
        '-filter_complex', fc_sync,
        '-map', '[out]', '-map', '[aout2]',
        '-t', str(duracao),
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '14',
        '-profile:v', 'high', '-level', '4.2', '-bf', '3',
        '-maxrate', '20M', '-bufsize', '40M',
        '-threads', '0', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
        '-movflags', '+faststart', '-y', caminho_saida
    ]
    res2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=1200)
    if res2.returncode == 0 and os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 1000:
        return True

    # ── Fallback: só video principal sem satisfying ──
    print("  ⚠️ Satisfying split falhou, usando layout full-screen como fallback")
    return False


# ════════════════════════════════════════════════════════════
#  LAYOUT SPLIT — WEBCAM + CONTEÚDO
# ════════════════════════════════════════════════════════════

def _aplicar_edicao_split(caminho_video, caminho_ass, caminho_saida,
                          duracao_clip, w, h, webcam):
    """
    Layout split para vídeos com webcam: conteúdo em cima, webcam grande em baixo.
    Aplica TODOS os efeitos profissionais.

    Layout (1080x1920):
      ┌────────────────┐
      │  CONTEÚDO FILL  │  ~864px — recortado até à webcam, stretch to fill
      ├────────────────┤   8px — divider accent com glow
      │  LEGENDAS       │
      │  WEBCAM GRANDE  │ ~1056px — face grande, olhos no centro vertical
      │ ═══ PROGRESS ══│  barra de progresso neon na base
      └────────────────┘

    EFEITOS PROFISSIONAIS:
      ✦ Temporal denoise (hqdn3d)
      ✦ Color grading cinematográfico
      ✦ Sharpen adaptativo
      ✦ Punch entry flash
      ✦ Fade in/out suave
    """
    BAR_H = 8
    BOT_H = 1056
    TOP_H = 1920 - BOT_H

    corner = webcam['corner']
    face_cx = webcam['face_cx']
    face_cy = webcam['face_cy']
    face_w = webcam['face_w']
    face_h = webcam['face_h']

    # === TOP: conteúdo sem a zona da webcam ===
    if 'b' in corner:
        ct_y = 0
        ct_h = max(int(h * 0.40), webcam['y'])
    else:
        ct_y = webcam['y'] + webcam['h']
        ct_h = max(int(h * 0.40), h - ct_y)

    ct_h = max(100, min(ct_h, h - ct_y))
    ct_h = ct_h - (ct_h % 2)

    # === BOTTOM: crop à volta da face ===
    target_aspect = 1080 / BOT_H
    face_crop_w = max(int(face_w * 2.2), 300)
    face_crop_h = max(int(face_crop_w / target_aspect), 250)
    face_crop_w += face_crop_w % 2
    face_crop_h += face_crop_h % 2
    face_crop_w = min(face_crop_w, w)
    face_crop_h = min(face_crop_h, h)

    olhos_y = face_cy - int(face_h * 0.15)
    fx = max(0, min(face_cx - face_crop_w // 2, w - face_crop_w))
    fy = max(0, min(olhos_y - face_crop_h // 2, h - face_crop_h))

    print(f"  🖼️  Split: topo=crop(0,{ct_y},{w},{ct_h}) → 1080x{TOP_H}")
    print(f"  🖼️  Split: cam=crop({fx},{fy},{face_crop_w},{face_crop_h}) → 1080x{BOT_H}")

    # === FILTER_COMPLEX ===
    parts = []
    parts.append(f"[0:v]split[_v1][_v2]")

    parts.append(
        f"[_v1]crop={w}:{ct_h}:0:{ct_y},"
        f"scale=1080:{TOP_H}:flags=lanczos[_top]"
    )

    parts.append(
        f"[_v2]crop={face_crop_w}:{face_crop_h}:{fx}:{fy},"
        f"scale=1080:{BOT_H}:flags=lanczos[_bot]"
    )

    parts.append(f"[_top][_bot]vstack=inputs=2[_stk]")

    # ══════ TODOS OS EFEITOS PROFISSIONAIS ══════
    fade_out = max(0, duracao_clip - 0.6)
    progress_y = 1920 - 28
    progress_h = 6

    efx = [
        "format=yuv420p",
        # Barra divisória com glow
        f"drawbox=x=0:y={TOP_H - BAR_H//2}:w=iw:h={BAR_H}:color=0x1a1a2e@1.0:t=fill",
        f"drawbox=x=0:y={TOP_H - BAR_H//2}:w=iw:h=2:color=0x6c5ce7@0.8:t=fill",
        f"drawbox=x=0:y={TOP_H + BAR_H//2 - 2}:w=iw:h=2:color=0x6c5ce7@0.8:t=fill",
        # Temporal denoise
        "hqdn3d=1.5:1.0:2.0:1.5",
        # Color grading cinematográfico
        "eq=contrast=1.05:brightness=0.01:saturation=1.15:gamma=1.02",
        # Sharpen adaptativo
        "unsharp=5:5:0.6:5:5:0.0",
        # Punch entry flash
        "fade=t=in:st=0:d=0.15:color=white",
        "fade=t=in:st=0.15:d=0.25:color=black",
        # Fade out
        f"fade=t=out:st={fade_out:.2f}:d=0.6:color=black",
    ]

    if caminho_ass and os.path.exists(caminho_ass):
        ass_path = os.path.abspath(caminho_ass).replace('\\', '/').replace(':', '\\:')
        efx.append(f"subtitles='{ass_path}'")

    parts.append(f"[_stk]{','.join(efx)}[out]")
    fc = ';'.join(parts)

    return _encode_com_filtros(caminho_video, caminho_saida, filter_complex=fc,
                               duracao_clip=duracao_clip)


# ════════════════════════════════════════════════════════════
#  LAYOUT STANDARD — CROP 9:16 COM FACE TRACKING
# ════════════════════════════════════════════════════════════

def _aplicar_edicao_standard(caminho_video, caminho_ass, caminho_saida,
                             duracao_clip, w, h,
                             intervalos_fala=None, face_info=None):
    """
    Layout split: conteúdo principal no topo (60% = 1152px) + vídeo satisfatório em baixo
    (40% = 762px) com TODOS os efeitos profissionais maximizados.

    Se não houver vídeos em downloads/satisfying/, usa layout full-screen com BG desfocado.

    Layout (1080x1920):
      ┌────────────────┐
      │ CONTEÚDO 1152px│  BG desfocado + vídeo centrado + zoom dinâmico + breathing
      │   ── LEGENDAS ─│  ← legendas centradas NA linha divisória
      ├────────────────┤  divider 6px com glow
      │ VÍDEO SAT. 762px│  Gameplay/parkour/satisfying loopado
      │ ═══ PROGRESS ══│  barra de progresso neon na base
      └────────────────┘

    EFEITOS PROFISSIONAIS:
      ✦ Breathing zoom dinâmico (1.00x↔1.03x, ciclo 8s)
      ✦ Zoom 1.15x na face durante fala
      ✦ Temporal denoise (hqdn3d)
      ✦ Color grading cinematográfico (contrast+saturation+gamma)
      ✦ Sharpen adaptativo
      ✦ Punch entry flash (branco 0.15s)
      ✦ Fade in/out suave
      ✦ Legendas karaoke word-by-word
    """
    fps = obter_fps_video(caminho_video) or 30
    video_sat = _encontrar_video_satisfatorio()

    if video_sat:
        # ====== LAYOUT SPLIT: CONTEÚDO (topo 60%) + SAT (baixo 40%) ======
        MAIN_H = 1152   # 60% de 1920 (par)
        BAR_H  = 6
        SAT_H  = 1920 - MAIN_H - BAR_H  # = 762 (par)

        # Escala do vídeo principal para caber em 1080 x MAIN_H (preserva aspect ratio)
        scale_ratio   = min(1080 / w, MAIN_H / h)
        scaled_w_main = int(w * scale_ratio)
        scaled_h_main = int(h * scale_ratio)
        scaled_w_main -= scaled_w_main % 2
        scaled_h_main -= scaled_h_main % 2
        overlay_x_main = max(0, (1080 - scaled_w_main) // 2)
        overlay_y_main = max(0, (MAIN_H - scaled_h_main) // 2)

        # Posição da face na área MAIN_H composta (para zoom dinâmico)
        if face_info and face_info.get("cx_pct"):
            face_x_c = (overlay_x_main + face_info["cx_pct"] * scaled_w_main) / 1080
            face_y_c = (overlay_y_main + face_info["cy_pct"] * scaled_h_main) / MAIN_H
        else:
            face_x_c = 0.5
            face_y_c = 0.5

        parts = []
        # Input [0] = main video, Input [1] = satisfying (loopado)

        # Split em vmain (foreground) e vblur (background desfocado)
        parts.append("[0:v]split=2[_vmain][_vblur]")

        # Background desfocado da área principal (1080 x MAIN_H)
        parts.append(
            f"[_vblur]scale=1080:{MAIN_H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop=1080:{MAIN_H},"
            f"boxblur=20:4,"
            f"eq=brightness=-0.12:saturation=0.35[_bg]"
        )

        # Foreground principal (aspect ratio preservado, centrado)
        parts.append(
            f"[_vmain]scale={scaled_w_main}:{scaled_h_main}:flags=lanczos[_fg]"
        )

        # Composit foreground sobre background
        parts.append(
            f"[_bg][_fg]overlay={overlay_x_main}:{overlay_y_main}[_composed]"
        )

        # Zoom dinâmico + breathing dentro da área MAIN_H
        zoom_label = "_composed"
        zf = gerar_filtro_zoom_dinamico(
            intervalos_fala, duracao_clip,
            face_x_c, face_y_c, fps,
            out_w=1080, out_h=MAIN_H
        )
        if zf:
            parts.append(f"[_composed]{zf}[_zoomed]")
            zoom_label = "_zoomed"
            print(f"  🔍 Zoom dinâmico + breathing: face=({face_x_c:.0%},{face_y_c:.0%})")

        # ══════ EFEITOS PROFISSIONAIS NA ÁREA PRINCIPAL ══════
        fade_out = max(0, duracao_clip - 0.6)
        efx_main = [
            "format=yuv420p",
            # Temporal denoise (remove ruído sem perder detalhe)
            "hqdn3d=1.5:1.0:2.0:1.5",
            # Color grading cinematográfico
            "eq=contrast=1.05:brightness=0.01:saturation=1.15:gamma=1.02",
            # Sharpen adaptativo (nitidez profissional)
            "unsharp=5:5:0.6:5:5:0.0",
        ]
        parts.append(f"[{zoom_label}]{','.join(efx_main)}[_main_out]")

        # Vídeo satisfatório: scale to fill 1080 x SAT_H, crop centrado exacto
        # Começa num ponto aleatório garantindo que cabe duracao_clip completa
        # Ex: se SAT tem 200s e clip tem 50s, pode começar entre 0s e 150s
        sat_dur = _obter_duracao_video(video_sat)
        max_start = max(0, sat_dur - duracao_clip)
        sat_start = random.uniform(0, max_start) if max_start > 0 else 0
        parts.append(
            f"[1:v]trim=start={sat_start:.2f}:duration={duracao_clip:.3f},setpts=PTS-STARTPTS,"
            f"scale=1080:{SAT_H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop=1080:{SAT_H}[_sat]"
        )

        # Stack: main content (topo) + satisfying (baixo) = 1920px exacto
        parts.append("[_main_out][_sat]vstack=inputs=2[_vstk]")
        bar_y = MAIN_H  # divider logo abaixo do conteúdo principal

        # ══════ EFEITOS FINAIS NO FRAME COMPLETO ══════
        # Barra divisória com glow neon
        # Barra de progresso na base (dentro do satisfying, a 20px do fundo)
        progress_y = 1920 - 28
        progress_h = 6
        margin_v_leg = (1920 - MAIN_H) + 8  # = 776

        efx_final = [
            "format=yuv420p",
            # Barra divisória accent com glow
            f"drawbox=x=0:y={bar_y}:w=iw:h={BAR_H}:color=0x1a1a2e@1.0:t=fill",
            f"drawbox=x=0:y={bar_y}:w=iw:h=2:color=0x6c5ce7@0.8:t=fill",
            f"drawbox=x=0:y={bar_y+BAR_H-2}:w=iw:h=2:color=0x6c5ce7@0.8:t=fill",
            # Punch entry flash (flash branco 0.15s no início)
            "fade=t=in:st=0:d=0.15:color=white",
            # Fade in normal (preto, mais longo)
            "fade=t=in:st=0.15:d=0.25:color=black",
            # Fade out suave
            f"fade=t=out:st={fade_out:.2f}:d=0.6:color=black",
        ]
        if caminho_ass and os.path.exists(caminho_ass):
            ass_path = os.path.abspath(caminho_ass).replace('\\', '/').replace(':', '\\:')
            efx_final.append(
                f"subtitles='{ass_path}':force_style='Alignment=2,MarginV={margin_v_leg},Fontsize=90'"
            )
        parts.append(f"[_vstk]{','.join(efx_final)}[out]")
        fc = ';'.join(parts)

        # Encoding com 2 inputs
        return _encode_com_filtros_2in(
            caminho_video, video_sat, caminho_saida,
            filter_complex=fc, duracao=duracao_clip
        )

    else:
        # ====== LAYOUT FULL-SCREEN: blurred BG + todos os efeitos ======
        scale_ratio = 1080 / w
        scaled_h = int(h * scale_ratio)
        y_offset  = (1920 - scaled_h) / 2

        if face_info and face_info.get("cx_pct"):
            face_x_composed = face_info["cx_pct"]
            face_y_composed = (y_offset + face_info["cy_pct"] * scaled_h) / 1920
        else:
            face_x_composed = 0.5
            face_y_composed = 0.50

        parts = []
        parts.append("[0:v]split=2[_vmain][_vblur]")
        parts.append(
            "[_vblur]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "boxblur=22:5,"
            "eq=brightness=-0.10:saturation=0.4[_bg]"
        )
        parts.append(f"[_vmain]scale=1080:{scaled_h}:flags=lanczos[_fg]")
        overlay_y = max(0, (1920 - scaled_h) // 2)
        parts.append(f"[_bg][_fg]overlay=0:{overlay_y}[_composed]")

        # Zoom dinâmico + breathing
        zoom_filter = gerar_filtro_zoom_dinamico(
            intervalos_fala, duracao_clip,
            face_x_composed, face_y_composed, fps
        )
        if zoom_filter:
            parts.append(f"[_composed]{zoom_filter}[_zoomed]")
            current_label = "_zoomed"
            print(f"  🔍 Zoom dinâmico + breathing: face=({face_x_composed:.0%},{face_y_composed:.0%})")
        else:
            current_label = "_composed"

        # ══════ TODOS OS EFEITOS PROFISSIONAIS ══════
        fade_out_start = max(0, duracao_clip - 0.6)
        progress_y = 1920 - 28
        progress_h = 6

        efx = [
            "format=yuv420p",
            # Temporal denoise
            "hqdn3d=1.5:1.0:2.0:1.5",
            # Color grading cinematográfico
            "eq=contrast=1.05:brightness=0.01:saturation=1.15:gamma=1.02",
            # Sharpen adaptativo
            "unsharp=5:5:0.6:5:5:0.0",
            # Punch entry flash
            "fade=t=in:st=0:d=0.15:color=white",
            "fade=t=in:st=0.15:d=0.25:color=black",
            # Fade out
            f"fade=t=out:st={fade_out_start:.2f}:d=0.6:color=black",
        ]
        if caminho_ass and os.path.exists(caminho_ass):
            ass_path = os.path.abspath(caminho_ass).replace('\\', '/').replace(':', '\\:')
            efx.append(f"subtitles='{ass_path}'")
        parts.append(f"[{current_label}]{','.join(efx)}[out]")
        fc = ';'.join(parts)
        return _encode_com_filtros(caminho_video, caminho_saida, filter_complex=fc,
                                   duracao_clip=duracao_clip)


# ════════════════════════════════════════════════════════════
#  EFEITO DE LOOP INFINITO (crossfade fim → início)
# ════════════════════════════════════════════════════════════

def aplicar_loop_infinito(caminho_entrada, caminho_saida, duracao_clip, xfade_dur=2.0):
    """
    Aplica um loop infinito MATEMATICAMENTE PERFEITO.

    Técnica correcta (frame-exact seamless loop):
    ─────────────────────────────────────────────
    Seja D = duração do clip original, X = duração do crossfade.

    Output = clip[X → D-X]  (conteúdo puro, sem fades nas bordas)
           + crossfade(clip[D-X → D] → clip[0 → X])   (dissolve no final)
    Output duration = D - X

    ┌──────────────────────────────────────────────────────┐
    │ clip original │ X │ conteúdo puro D-2X │ X │ X     │
    │               ↑                         ↑crossfade  │
    │           início output              início↓fim xfade│
    └──────────────────────────────────────────────────────┘

    Resultado:
      • Último frame do output = clip[X]  ← 100% clip início pós-crossfade
      • Primeiro frame do output = clip[X] ← exactamente igual
      • Ao fazer replay a plataforma volta a t=0 = clip[X] → sem corte visível
      • Áudio segue a mesma lógica (exponential crossfade)

    Encoding premium (CRF 16 / CQ 16, high profile, AAC 192k).
    """
    try:
        # ── Limites do crossfade ──────────────────────────────────────────
        # Precisa de D > 2*X para haver conteúdo puro no meio.
        # Máximo: 20% do clip ou 3s (o que for menor).
        xfade_dur = min(xfade_dur, duracao_clip * 0.20, 3.0)
        xfade_dur = max(0.5, xfade_dur)

        # Garante que D > 2*X (mínimo 0.5s de conteúdo puro no meio)
        if duracao_clip < 2 * xfade_dur + 0.5:
            xfade_dur = max(0.2, (duracao_clip - 0.5) / 2)

        X  = xfade_dur
        D  = duracao_clip

        # ── Pontos-chave (todos em segundos do clip ORIGINAL) ─────────────
        # vmain = clip[X : D]  →  duração = D-X
        # vstart = clip[0 : X] →  duração = X  (o início que vai "entrar" no fim)
        # xfade offset dentro de vmain = (D-X) - X = D-2X
        vmain_dur  = D - X                # duração de vmain
        xfade_offset = max(0.05, D - 2 * X)  # início do crossfade dentro de vmain

        print(f"  🔁 Loop: D={D:.2f}s  X={X:.2f}s  "
              f"conteúdo_puro={xfade_offset:.2f}s  output={vmain_dur:.2f}s")

        # Lista de transições a tentar (da mais elegante para a mais simples)
        transitions = ["smoothup", "dissolve", "fade"]

        for transition_name in transitions:
            # ── FILTER COMPLEX ────────────────────────────────────────────
            # Vídeo:
            #   [vmain]  = clip[X:D]  (split 1 — conteúdo principal)
            #   [vstart] = clip[0:X]  (split 2 — início do clip para entrar no crossfade)
            #   xfade a partir de xfade_offset dentro de vmain, duração X
            #   output = vmain[:xfade_offset] + dissolve(vmain[xfade_offset:] ↗ vstart) = D-X total
            #
            # Áudio: mesma lógica com acrossfade
            fc = (
                f"[0:v]split=2[_vsplit1][_vsplit2];"

                # vmain: clip[X → D], duração = D-X
                f"[_vsplit1]trim=start={X:.4f}:end={D:.4f},"
                f"setpts=PTS-STARTPTS[_vmain];"

                # vstart: clip[0 → X], duração = X  (loop-back intro)
                f"[_vsplit2]trim=start=0:end={X:.4f},"
                f"setpts=PTS-STARTPTS[_vstart];"

                # Crossfade: vmain → vstart, começa em xfade_offset dentro de vmain
                f"[_vmain][_vstart]xfade=transition={transition_name}"
                f":duration={X:.4f}:offset={xfade_offset:.4f}[vout];"

                # Áudio: mesma divisão
                f"[0:a]asplit=2[_asplit1][_asplit2];"

                f"[_asplit1]atrim=start={X:.4f}:end={D:.4f},"
                f"asetpts=PTS-STARTPTS[_amain];"

                f"[_asplit2]atrim=start=0:end={X:.4f},"
                f"asetpts=PTS-STARTPTS[_astart];"

                # acrossfade exponencial (ducking natural)
                f"[_amain][_astart]acrossfade=d={X:.4f}:c1=exp:c2=exp[aout]"
            )

            # ── NVENC (GPU) ───────────────────────────────────────────────
            cmd_nvenc = [
                'ffmpeg', '-i', caminho_entrada,
                '-filter_complex', fc,
                '-map', '[vout]', '-map', '[aout]',
                '-c:v', 'h264_nvenc',
                '-preset', 'p5', '-profile:v', 'high',
                '-rc:v', 'vbr', '-cq:v', '16', '-b:v', '0',
                '-maxrate', '14M', '-bufsize', '28M',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                '-movflags', '+faststart', '-y', caminho_saida
            ]
            res = subprocess.run(cmd_nvenc, capture_output=True, text=True, timeout=300)
            if res.returncode == 0 and os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 1000:
                print(f"  🔁 Loop perfeito ({transition_name}, NVENC) "
                      f"— {X:.1f}s dissolve · output {vmain_dur:.1f}s")
                return True

            # ── libx264 fallback ──────────────────────────────────────────
            cmd_x264 = [
                'ffmpeg', '-i', caminho_entrada,
                '-filter_complex', fc,
                '-map', '[vout]', '-map', '[aout]',
                '-c:v', 'libx264',
                '-preset', 'slow', '-crf', '16',
                '-profile:v', 'high', '-level', '4.2',
                '-threads', '0', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                '-movflags', '+faststart', '-y', caminho_saida
            ]
            res2 = subprocess.run(cmd_x264, capture_output=True, text=True, timeout=600)
            if res2.returncode == 0 and os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 1000:
                print(f"  🔁 Loop perfeito ({transition_name}, x264) "
                      f"— {X:.1f}s dissolve · output {vmain_dur:.1f}s")
                return True

            # ── Diagnóstico se falhou ─────────────────────────────────────
            stderr_preview = (res2.stderr or res.stderr or "")[-400:]
            print(f"  ⚠️  Transição '{transition_name}' falhou: {stderr_preview[-200:]}")

        print(f"  ⚠️ Loop infinito falhou com todas as transições")
        return False

    except subprocess.TimeoutExpired:
        print(f"  ⚠️ Loop infinito timeout")
        return False
    except Exception as e:
        print(f"  ❌ Erro no loop infinito: {e}")
        return False


# ════════════════════════════════════════════════════════════
#  PIPELINE PRINCIPAL
# ════════════════════════════════════════════════════════════

def editar_clipes(caminho_video, clipes, segmentos_whisper, pasta_saida="downloads/clips_editados", progress_callback=None):
    """
    Pipeline profissional de edição de clipes.

    Para cada clipe:
      1. Corta o segmento (stream copy, rápido)
      2. Gera legendas ASS com hook + estilo profissional
      3. Aplica crop + todos os efeitos + legendas (encoding único)
      
    Args:
        progress_callback (callable): Função callback(clip_idx, total_clips, pct, detail)
    """
    os.makedirs(pasta_saida, exist_ok=True)

    duracao_total = obter_duracao_video(caminho_video)
    if not duracao_total:
        duracao_total = 300  # Fallback: 5 minutos

    clipes_editados = []
    total_clipes = len(clipes)

    for i, clipe in enumerate(clipes, 1):
        titulo = clipe.get('titulo') or clipe.get('title', f'Clipe {i}')
        print(f"\n{'='*55}")
        print(f"📹 Editando clipe {i}/{total_clipes}: {titulo}")
        print(f"{'='*55}")
        
        if progress_callback:
            progress_callback(i, total_clipes, 0, "Iniciando edição")

        duracao_clip = 50         # 50 segundos por clip
        INTRO_SKIP = 120          # segundos a ignorar no início
        num_clipes = len(clipes)

        # ── Tentar localizar o momento exato via transcript (match Whisper) ──
        inicio = None
        transcript_text = (clipe.get('transcript') or "").strip()
        if transcript_text and segmentos_whisper:
            # Normalizar: minúsculas, sem pontuação extra
            import re as _re
            def _norm(t):
                return _re.sub(r'[^\w\s]', '', t.lower()).strip()

            needle = _norm(transcript_text)
            if len(needle) >= 8:  # só procurar se tiver texto suficiente
                best_score = 0.0
                best_start = None

                # Construir texto corrido com timestamps por segmento
                for seg in segmentos_whisper:
                    seg_text = _norm(seg.get("text", ""))
                    if not seg_text:
                        continue
                    seg_start = seg.get("start", 0)
                    # Ignorar primeiros 2 minutos (intro)
                    if seg_start < INTRO_SKIP:
                        continue
                    # Match exato (substring)
                    if needle[:40] in seg_text:
                        best_start = seg_start
                        best_score = 1.0
                        break
                    # Match parcial (primeiras N palavras)
                    needle_words = needle.split()
                    seg_words = seg_text.split()
                    if len(needle_words) >= 3 and len(seg_words) >= 3:
                        match_count = 0
                        for nw in needle_words[:5]:
                            if nw in seg_words:
                                match_count += 1
                        score = match_count / min(5, len(needle_words))
                        if score > best_score and score >= 0.6:
                            best_score = score
                            best_start = seg_start

                if best_start is not None:
                    # Recuar 2s para dar contexto (mas não antes do INTRO_SKIP)
                    inicio = max(INTRO_SKIP, best_start - 2.0)
                    # Garantir que não ultrapassa o vídeo
                    if inicio + duracao_clip > duracao_total:
                        inicio = max(INTRO_SKIP, duracao_total - duracao_clip)
                    print(f"  🎯 Transcript match! Início em {inicio:.1f}s (score={best_score:.0%})")

        # Fallback: distribuir uniformemente se não encontrou transcript
        if inicio is None:
            zona_inicio = min(INTRO_SKIP, max(0, duracao_total - duracao_clip))
            zona_disponivel = max(0, duracao_total - zona_inicio - duracao_clip)
            espaco = zona_disponivel / max(1, num_clipes)
            inicio = zona_inicio + espaco * (i - 1)
            print(f"  📐 Distribuição uniforme: início em {inicio:.1f}s")

        # Garante que não ultrapassa a duração
        if inicio + duracao_clip > duracao_total:
            inicio = max(INTRO_SKIP if INTRO_SKIP < duracao_total else 0, duracao_total - duracao_clip)
            duracao_clip = min(duracao_clip, duracao_total - inicio)

        if duracao_clip <= 0:
            print(f"  ⚠️ Duração insuficiente para clipe {i}")
            continue

        # Caminhos
        caminho_cortado = f"{pasta_saida}/clip_{i:02d}_temp.mp4"
        caminho_ass = f"{pasta_saida}/clip_{i:02d}_legendas.ass"
        caminho_preloop = f"{pasta_saida}/clip_{i:02d}_preloop.mp4"
        caminho_final = f"{pasta_saida}/clip_{i:02d}_final.mp4"

        # ═══ PASSO 1: CORTAR ═══
        print(f"  ✂️  Cortando ({inicio:.1f}s → {inicio + duracao_clip:.1f}s)...")
        
        if progress_callback:
            progress_callback(i, total_clipes, 10, "Cortando vídeo")
        
        if not cortar_video(caminho_video, inicio, duracao_clip, caminho_cortado):
            print(f"  ⚠️ Pulando clipe {i}")
            continue

        # ═══ PASSO 1.5: JUMP CUTS ═══
        # Calcula intervalos ANTES de gerar ASS para que os timestamps sejam remapeados
        if progress_callback:
            progress_callback(i, total_clipes, 20, "Jump cuts")
        
        intervalos_jc = None
        duracao_clip_original = duracao_clip  # salva duração original (antes dos jump cuts)
        if segmentos_whisper:
            intervalos_calculados = calcular_intervalos_fala(segmentos_whisper, inicio, duracao_clip)
            total_fala = sum(f - s for s, f in intervalos_calculados)
            silencio = duracao_clip - total_fala

            if len(intervalos_calculados) >= 2 and silencio >= 0.5:
                caminho_jumpcut = f"{pasta_saida}/clip_{i:02d}_jumpcut.mp4"

                # Usa trim+atrim+concat para sincronia áudio/vídeo PERFEITA
                filtro_jc = _construir_filtro_concat(intervalos_calculados)

                # Tenta NVENC primeiro
                cmd_jc = [
                    'ffmpeg', '-i', caminho_cortado,
                    '-filter_complex', filtro_jc,
                    '-map', '[vout]', '-map', '[aout]',
                    '-c:v', 'h264_nvenc', '-preset', 'p4', '-rc:v', 'vbr', '-cq:v', '18',
                    '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-y', caminho_jumpcut
                ]
                res_jc = subprocess.run(cmd_jc, capture_output=True, text=True, timeout=300)
                if res_jc.returncode != 0:
                    cmd_jc_cpu = [
                        'ffmpeg', '-i', caminho_cortado,
                        '-filter_complex', filtro_jc,
                        '-map', '[vout]', '-map', '[aout]',
                        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
                        '-y', caminho_jumpcut
                    ]
                    res_jc = subprocess.run(cmd_jc_cpu, capture_output=True, text=True, timeout=600)

                if res_jc.returncode == 0 and os.path.exists(caminho_jumpcut):
                    os.remove(caminho_cortado)
                    caminho_cortado = caminho_jumpcut
                    nova_dur = obter_duracao_video(caminho_cortado) or duracao_clip
                    print(f"  ⚡ Jump cuts: {duracao_clip:.1f}s → {nova_dur:.1f}s (removidos {silencio:.1f}s de silêncio)")
                    intervalos_jc = intervalos_calculados   # activa remap de timestamps
                    duracao_clip = nova_dur
                else:
                    if os.path.exists(caminho_jumpcut):
                        try: os.remove(caminho_jumpcut)
                        except: pass

        # ═══ PASSO 1.8: FACE INFO + INTERVALOS DE FALA (para zoom dinâmico) ═══
        face_info = None
        intervalos_fala = None
        print(f"  🔍 Analisando posição da face para zoom dinâmico...")
        face_info = detectar_face_info(caminho_cortado)
        if face_info:
            print(f"     Face: ({face_info['cx_pct']:.0%}, {face_info['cy_pct']:.0%}) "
                  f"conf={face_info['avg_conf']:.0%} det={face_info['det_rate']:.0%}")
        else:
            print(f"     Sem face detetada → vídeo centrado")
        # Intervalos de fala no timeline POST-jump-cut
        if intervalos_jc is not None:
            # Jump cuts removeram silêncios: o vídeo inteiro é fala
            intervalos_fala = [[0.0, duracao_clip]]
        elif segmentos_whisper:
            intervalos_fala = calcular_intervalos_fala(
                segmentos_whisper, inicio, duracao_clip_original
            )

        # ═══ PASSO 2: GERAR LEGENDAS ASS (com remap de timestamps se houve jump cuts) ═══
        print(f"  📝 Gerando legendas...")
        if segmentos_whisper:
            gerar_legendas_ass(
                segmentos_whisper, caminho_ass,
                inicio, duracao_clip_original,    # duração ORIGINAL para filtrar timestamps Whisper
                texto_hook="",
                intervalos_jc=intervalos_jc,
                duracao_final=duracao_clip,        # duração REAL pós-jump-cut para clamping
            )

        # ═══ PASSO 3: EDIÇÃO PROFISSIONAL COM TODOS OS EFEITOS ═══
        print(f"  🎬 Aplicando edição profissional:")
        print(f"     ✦ Breathing zoom + zoom 1.15x na fala")
        print(f"     ✦ Denoise + Color grade + Sharpen 5x5")
        print(f"     ✦ Vinheta cinematográfica + Punch flash")
        print(f"     ✦ Progress bar neon + Legendas karaoke")
        
        if progress_callback:
            progress_callback(i, total_clipes, 50, "Aplicando efeitos")

        sucesso = aplicar_edicao_profissional(
            caminho_cortado, caminho_ass, caminho_preloop, duracao_clip,
            intervalos_fala=intervalos_fala,
            face_info=face_info
        )

        if not sucesso:
            print(f"  ⚠️ Edição falhou, usando vídeo base")
            shutil.copy2(caminho_cortado, caminho_preloop)

        # ═══ PASSO 4: LOOP INFINITO SEAMLESS ═══
        print(f"     ✦ Loop infinito seamless (dissolve + audio crossfade exponencial)")
        
        if progress_callback:
            progress_callback(i, total_clipes, 90, "Loop infinito")
        
        sucesso_loop = aplicar_loop_infinito(caminho_preloop, caminho_final, duracao_clip)
        if not sucesso_loop:
            print(f"  ⚠️ Loop infinito falhou, usando versão sem loop")
            shutil.copy2(caminho_preloop, caminho_final)

        # Limpa temporários
        for tmp in (caminho_cortado, caminho_preloop):
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass

        # Gera metadados YouTube em Português
        razao = clipe.get('razao', 'Clipe viral interessante')
        metadados_yt = gerar_metadados_youtube(titulo, razao, duracao_clip)

        # Se o Ollama já trouxe copy YouTube (descricao), usa-o
        youtube_titulo_final = (clipe.get('titulo') or metadados_yt["titulo"] or titulo).strip()
        youtube_descricao_final = (clipe.get('descricao') or metadados_yt["descricao"] or "").strip()

        clipe_dict = {
            "numero": i,
            "arquivo": caminho_final,
            "titulo": titulo,
            "razao": razao,
            "youtube": {
                "titulo": youtube_titulo_final,
                "descricao": youtube_descricao_final,
                "hashtags": metadados_yt["hashtags"],
                "trigger": metadados_yt["trigger"]
            }
        }

        clipes_editados.append(clipe_dict)

        if os.path.exists(caminho_final):
            tamanho_mb = os.path.getsize(caminho_final) / (1024 * 1024)
            print(f"  ✅ Clipe {i} concluído ({tamanho_mb:.1f}MB): {caminho_final}")
            print(f"     📌 YouTube: {metadados_yt['titulo']}")
            
            if progress_callback:
                progress_callback(i, total_clipes, 100, "Concluído")

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
