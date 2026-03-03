import json
import re
import torch
import subprocess
from faster_whisper import WhisperModel
import ollama


# Cache global para o modelo Whisper
_whisper_model_cache = None


def _sanitize_json_object_text(raw):
    """Tenta reparar JSON quase-válido vindo do LLM (newlines em strings, aspas curvas, trailing commas)."""
    if not raw:
        return raw

    fixed = raw.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")

    out = []
    in_string = False
    escaped = False
    for ch in fixed:
        if ch == '"' and not escaped:
            in_string = not in_string
            out.append(ch)
            continue

        if in_string and ch in ('\n', '\r'):
            out.append('\\n')
            escaped = False
            continue

        out.append(ch)
        escaped = (ch == '\\' and not escaped)
        if ch != '\\':
            escaped = False

    fixed = ''.join(out)
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    return fixed


def _extract_json_objects_relaxed(texto):
    """Extrai objetos JSON mesmo quando vêm múltiplos blocos ou com pequenas quebras de formato."""
    objs = []
    if not texto:
        return objs

    start = -1
    depth = 0
    in_string = False
    escaped = False

    for idx, ch in enumerate(texto):
        if ch == '"' and not escaped:
            in_string = not in_string

        if not in_string:
            if ch == '{':
                if depth == 0:
                    start = idx
                depth += 1
            elif ch == '}':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start != -1:
                        raw = texto[start:idx + 1]
                        objs.append(raw)
                        start = -1

        escaped = (ch == '\\' and not escaped)
        if ch != '\\':
            escaped = False

    return objs


def liberar_gpu_whisper():
    """Liberta a VRAM do Whisper para o Ollama ter GPU total.
    Sem isto, Whisper ocupa ~2GB e o Ollama offloads para CPU (10x mais lento)."""
    global _whisper_model_cache
    if _whisper_model_cache is None:
        return
    try:
        _whisper_model_cache = None
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("  🧹 VRAM libertada (modelo Whisper descarregado)")
    except Exception as e:
        print(f"  ⚠️ Aviso ao libertar GPU: {e}")

def verificar_gpu():
    """
    Verifica se uma GPU NVIDIA está disponível e retorna o device.
    
    Returns:
        tuple: (device: str, gpu_disponivel: bool, info: str)
    """
    gpu_disponivel = torch.cuda.is_available()
    
    if gpu_disponivel:
        device = "cuda"
        gpu_name = torch.cuda.get_device_name(0)
        info = f"✅ GPU detectada: {gpu_name}"
    else:
        device = "cpu"
        info = "⚠️ GPU não detectada. Usando CPU (mais lento, ~2-5 min por vídeo)"
    
    return device, gpu_disponivel, info


def extrair_audio_do_video(caminho_video, caminho_audio="downloads/audio_temp.wav"):
    """
    Extrai o áudio de um vídeo usando FFmpeg (sem dependências de moviepy).
    Usa WAV 16kHz mono: sem encoding lossy + Whisper não precisa resampling.
    
    Args:
        caminho_video (str): Caminho do arquivo de vídeo
        caminho_audio (str): Caminho onde o áudio será salvo
    
    Returns:
        str: Caminho do arquivo de áudio ou None se falhar
    """
    try:
        print(f"Extraindo áudio de: {caminho_video}...")
        print(f"  ⏳ Convertendo para WAV 16kHz (pode demorar em vídeos longos)...")
        
        # WAV PCM 16kHz mono: extração sem encoding (rápida) e formato nativo do Whisper
        # (Whisper usa 16kHz internamente - extrair direto evita resampling extra)
        comando = [
            'ffmpeg',
            '-i', caminho_video,
            '-vn',                  # Sem vídeo
            '-acodec', 'pcm_s16le', # PCM 16-bit (sem perda, sem encoding)
            '-ar', '16000',         # 16kHz = sample rate nativo do Whisper
            '-ac', '1',             # Mono (Whisper usa mono)
            '-y',
            caminho_audio
        ]
        
        import time
        t0 = time.time()
        # Executa FFmpeg (silencioso)
        subprocess.run(comando, capture_output=True, check=True)
        t1 = time.time()
        
        print(f"✅ Áudio extraído em {t1-t0:.1f}s! Salvo em: {caminho_audio}")
        return caminho_audio
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao extrair áudio com FFmpeg: {e}")
        return None
    except FileNotFoundError:
        print("❌ FFmpeg não encontrado! Certifique-se de que está instalado.")
        return None
    except Exception as e:
        print(f"❌ Erro ao extrair áudio: {e}")
        return None

def transcrever_audio_whisper(caminho_audio, progress_callback=None):
    """
    Transcreve um arquivo de áudio usando Faster-Whisper com suporte GPU.
    Roda 100% LOCAL no seu computador, sem custos!
    
    Retorna timestamps de CADA segmento para legendas dinâmicas.
    
    Args:
        caminho_audio (str): Caminho do arquivo de áudio (MP3, WAV, etc)
        progress_callback (callable): Função callback(pct, detail) para atualizar progresso
    
    Returns:
        dict: Dicionário com 'texto_completo' e 'segmentos' (com timestamps)
    """
    try:
        if progress_callback:
            progress_callback(0, "Detectando GPU")
        
        # Detecta GPU
        device, gpu_disponivel, info_gpu = verificar_gpu()
        print(info_gpu)
        
        print(f"Transcrevendo áudio com Faster-Whisper...")
        if gpu_disponivel:
            print(f"⚡ Usando GPU - transcrição RÁPIDA! (aprox. 20-60 segundos)")
        else:
            print(f"⏳ Usando CPU - transcrição mais lenta (aprox. 2-5 minutos)")
        
        if progress_callback:
            progress_callback(10, "Carregando modelo Whisper")
        
        # Carrega o modelo Whisper com suporte GPU
        # CPU: 'small' (bom equilíbrio velocidade/qualidade)
        # GPU: 'medium' ou 'large-v3' (máxima qualidade)
        modelo = "medium" if gpu_disponivel else "small"
        print(f"  📦 Carregando modelo Whisper '{modelo}'...")
        # GTX 1070 é sm_61 → CTranslate2 só suporta int8 e float32 nesta GPU
        # float16/int8_float16 requerem sm_70+ (Volta+)
        # int8 na GPU ainda é muito mais rápido que CPU
        compute_type = "int8" if gpu_disponivel else "int8"
        global _whisper_model_cache
        model = WhisperModel(
            modelo,
            device=device,
            compute_type=compute_type,
            num_workers=4,          # Workers paralelos para I/O
            cpu_threads=4           # Threads para operações CPU auxiliares
        )
        # Guarda referência global para EVITAR que o GC chame o destrutor
        # CTranslate2 crasha (SIGABRT) ao destruir o modelo CUDA
        _whisper_model_cache = model
        
        if progress_callback:
            progress_callback(20, "Transcrevendo")
        
        # Transcreve com word_timestamps para legendas dinâmicas
        # vad_filter=True filtra silêncios e música (só transcreve fala!)
        transcribe_params = {
            "language": "pt",
            "word_timestamps": True,   # Timestamps por palavra
            "vad_filter": True,        # Filtra silêncios/ruído
        }
        
        # GPU: beam_size=1 é o mais rápido; modelo 'medium' já garante qualidade
        if gpu_disponivel:
            transcribe_params["beam_size"] = 1
        
        segments, info = model.transcribe(caminho_audio, **transcribe_params)
        
        # Monta texto completo E segmentos com timestamps
        import time as _time
        t_start = _time.time()
        texto_completo = ""
        lista_segmentos = []
        
        for segment in segments:
            texto_completo += segment.text + " "
            
            # Guarda cada segmento com início e fim
            seg_data = {
                "inicio": segment.start,
                "fim": segment.end,
                "texto": segment.text.strip()
            }
            
            # Também guarda palavras individuais (para legendas animadas)
            if segment.words:
                seg_data["palavras"] = [
                    {
                        "palavra": w.word.strip(),
                        "inicio": w.start,
                        "fim": w.end
                    }
                    for w in segment.words
                ]
            
            lista_segmentos.append(seg_data)
            # Progresso a cada 20 segmentos
            if len(lista_segmentos) % 20 == 0:
                print(f"  📝 {len(lista_segmentos)} segmentos transcritos...")
                if progress_callback:
                    # Estimar progresso (30-90% do range)
                    pct = min(90, 30 + (len(lista_segmentos) * 2))  # assume ~30 segs por min
                    progress_callback(pct, f"{len(lista_segmentos)} segmentos")
        
        t_elapsed = _time.time() - t_start
        print(f"✅ Transcrição concluída em {t_elapsed:.1f}s! ({len(lista_segmentos)} segmentos)", flush=True)
        
        if progress_callback:
            progress_callback(100, "Transcrição completa")
        
        # O modelo fica no _whisper_model_cache global e será libertado
        # por liberar_gpu_whisper() antes de chamar o Ollama.
        print("  ✅ Transcrição pronta, a avançar para análise...", flush=True)
        
        return {
            "texto_completo": texto_completo.strip(),
            "segmentos": lista_segmentos
        }
    except Exception as e:
        print(f"❌ Erro ao transcrever áudio: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None

def analisar_com_ollama(transcrição, modelo=None, progress_callback=None):
    """
    Analisa a transcrição usando Llama 2 rodando localmente via Ollama.
    100% GRATUITO, roda no seu computador!
    
    IMPORTANTE: Você precisa ter o Ollama instalado em seu computador:
    1. Baixe em: https://ollama.ai
    2. Instale normalmente
    3. Abra um terminal E DEIXE RODANDO: ollama serve
    4. Em outro terminal, rode: ollama pull llama2
    5. Agora pode usar este script!
    
    Args:
        transcrição (dict): Dicionário com texto e segmentos da transcrição
        modelo (str, optional): Nome do modelo Ollama a usar. Padrão: "llama3.1"
        progress_callback (callable): Função callback(pct, detail) para atualizar progresso
    
    Returns:
        list: Lista com os clipes recomendados (início, fim, motivo)
    """
    try:
        if progress_callback:
            progress_callback(0, "Verificando Ollama")
        
        # ── Lê o modelo configurado nas definições ──
        if not modelo:
            try:
                import database as _db
                cfg = _db.get_settings()
                modelo = cfg.get("ollama_model", "llama3.1")
            except Exception:
                modelo = "llama3.1"

        # Verifica se Ollama está rodando
        try:
            ollama.list()
        except Exception as e:
            print("❌ Ollama não está rodando!")
            print("💡 Para rodar o Ollama:")
            print("   1. Abra o Ollama Desktop (na barra de tarefas)")
            print("   2. OU abra um terminal e digite: ollama serve")
            return None

        print(f"Analisando vídeo com {modelo} (GRATUITO, no seu computador)...", flush=True)
        
        if progress_callback:
            progress_callback(10, "Preparando transcrição")

        INTRO_SKIP_SEG = 120  # ignora os primeiros 2 min (intro/apresentação)
        CHAR_LIMIT      = 10000  # equilibrio contexto vs velocidade na GPU

        # ── Constrói transcrição com timestamps, pulando a intro ──
        # Formato: "[MM:SS] texto do segmento"
        # Dá ao Llama contexto temporal real para escolher momentos precisos.
        segmentos_filtrados = [
            s for s in (transcrição.get("segmentos") or [])
            if float(s.get("inicio", 0)) >= INTRO_SKIP_SEG
        ]

        if segmentos_filtrados:
            linhas_transcript = []
            for s in segmentos_filtrados:
                t = float(s.get("inicio", 0))
                mm, ss = int(t // 60), int(t % 60)
                linhas_transcript.append(f"[{mm:02d}:{ss:02d}] {s.get('texto', '').strip()}")
            texto_timed = "\n".join(linhas_transcript)
        else:
            # fallback: texto plano sem timestamps, já a saltar os primeiros 2 min
            texto_plano = transcrição["texto_completo"]
            # corta aproximadamente 2 min: ~150 palavras/min × 2 = 300 palavras
            palavras = texto_plano.split()
            texto_timed = " ".join(palavras[300:]) if len(palavras) > 300 else texto_plano

        if len(texto_timed) > CHAR_LIMIT:
            texto_timed = texto_timed[:CHAR_LIMIT] + "\n[... transcript truncated ...]"

        # System message: força o modelo a responder APENAS em JSON e em Português
        system_msg = (
            "És uma API JSON. Responde APENAS com objetos JSON válidos, um por linha. "
            "Sem explicações, sem markdown. Português (Portugal)."
        )

        # Tenta obter a URL do vídeo original (para incluir na descrição)
        video_url = (
            (transcrição or {}).get("video_url")
            or (transcrição or {}).get("url")
            or (transcrição or {}).get("source_url")
            or ""
        )
        if isinstance(video_url, str) and video_url.startswith("local://"):
            video_url = ""

        # Instrução de URL condicional (só se houver URL real)
        url_instrucao = f"Inclui o link do vídeo original na descrição: {video_url}" if video_url else ""

        # User message: prompt conciso para resposta rápida
        user_msg = f"""Transcrição com timestamps (primeiros 2 min ignorados):

{texto_timed}

Escolhe 5-7 momentos virais para YouTube Shorts.

REGRAS:
- Espalha pelo vídeo. EXCLUI patrocínios, intros, partes lentas.
- INCLUI: polémicas, surpresas, picos emocionais, hooks fortes, alta energia.

OUTPUT: objetos JSON, um por linha, SEM markdown. Chaves: titulo, descricao, razao, transcript
{{"titulo":"Título curto viral (max 60 chars)","descricao":"Descrição 2-3 linhas com \\n para quebras. {url_instrucao} Hashtags no fim.","razao":"[GATILHO] nota de edição","transcript":"palavras exatas de abertura"}}

Devolve APENAS JSON:"""
        
        # Chama o modelo via ollama.chat (suporta system message para todos os modelos)
        print(f"  ⏳ Aguardando resposta de {modelo}...", flush=True)
        
        if progress_callback:
            progress_callback(50, f"Consultando {modelo}")
        
        import time as _t2
        _t_llama = _t2.time()
        resposta = ollama.chat(
            model=modelo,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": user_msg},
            ],
            stream=False,
            options={
                "temperature": 0.2,
                "top_p": 0.9,
                "num_ctx": 12000  # Context window aumentado para 12000
            }
        )
        _t_llama_end = _t2.time()
        print(f"  ✅ {modelo} respondeu em {_t_llama_end - _t_llama:.1f}s", flush=True)
        
        if progress_callback:
            progress_callback(75, "Processando resposta")

        # ollama.chat devolve um objeto — o texto está em .message.content
        resposta_texto = resposta.message.content if hasattr(resposta, 'message') else resposta["message"]["content"]
        
        # ── Extrai JSON da resposta (robusto a vários formatos) ──
        try:
            import re as regex
            clipes = []

            # Remove blocos markdown ```json ... ``` ou ``` ... ```
            texto_limpo = regex.sub(r'```(?:json)?\s*', '', resposta_texto)
            texto_limpo = texto_limpo.replace('```', '')

            # Estratégia 1: extrator por balanceamento de chaves + reparação leve
            for raw in _extract_json_objects_relaxed(texto_limpo):
                try:
                    item = json.loads(raw)
                    # Aceita qualquer objecto que tenha título e razão
                    if item.get('titulo') or item.get('title'):
                        clipes.append(item)
                except json.JSONDecodeError:
                    try:
                        fixed = _sanitize_json_object_text(raw)
                        item = json.loads(fixed)
                        if item.get('titulo') or item.get('title'):
                            clipes.append(item)
                    except json.JSONDecodeError:
                        pass

            # Estratégia 2: linha por linha (quando o modelo separa por newlines)
            if not clipes:
                for linha in texto_limpo.splitlines():
                    linha = regex.sub(r'^\d+[.)\-]\s*', '', linha).strip()
                    if linha.startswith('{') and linha.endswith('}'):
                        try:
                            item = json.loads(linha)
                            if item.get('titulo') or item.get('title'):
                                clipes.append(item)
                        except json.JSONDecodeError:
                            try:
                                item = json.loads(_sanitize_json_object_text(linha))
                                if item.get('titulo') or item.get('title'):
                                    clipes.append(item)
                            except json.JSONDecodeError:
                                pass

            # Estratégia 3: array JSON
            if not clipes:
                m = regex.search(r'\[.*?\]', texto_limpo, flags=regex.DOTALL)
                if m:
                    try:
                        arr = json.loads(m.group(0))
                        if isinstance(arr, list):
                            clipes = arr
                    except json.JSONDecodeError:
                        pass

            if clipes:
                # Remove duplicados por título/transcript
                uniq = []
                seen = set()
                for c in clipes:
                    key = ((c.get('titulo') or c.get('title') or '').strip().lower(), (c.get('transcript') or '').strip().lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append(c)
                clipes = uniq

                print(f"✅ Análise concluída! {len(clipes)} clipes recomendados:")
                for i, clipe in enumerate(clipes, 1):
                    titulo = clipe.get('titulo') or clipe.get('title', 'Sem título')
                    print(f"  {i}. {titulo}")
                
                if progress_callback:
                    progress_callback(100, f"{len(clipes)} clips encontrados")
                
                return clipes

            # Nenhuma estratégia funcionou
            print(f"⚠️ [{modelo}] Não foi possível extrair JSON da resposta.")
            print(f"   Resposta (primeiros 400 chars): {resposta_texto[:400]}")
            return None

        except Exception as e:
            print(f"⚠️ Erro ao processar resposta: {e}")
            return None
            
    except Exception as e:
        print(f"❌ Erro ao analisar com Llama: {e}")
        print("💡 Verifique se o Ollama está rodando: ollama serve")
        return None

def salvar_analise(clipes, arquivo_saida="downloads/analise_clipes.json"):
    """
    Salva a análise em um arquivo JSON para usar no próximo módulo.
    
    Args:
        clipes (list): Lista de clipes recomendados
        arquivo_saida (str): Caminho do arquivo de saída
    """
    try:
        with open(arquivo_saida, "w", encoding="utf-8") as f:
            json.dump(clipes, f, indent=2, ensure_ascii=False)
        print(f"✅ Análise salva em: {arquivo_saida}")
    except Exception as e:
        print(f"❌ Erro ao salvar análise: {e}")
