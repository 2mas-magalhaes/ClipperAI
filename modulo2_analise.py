import json
import re
import torch
import subprocess
from faster_whisper import WhisperModel
import ollama


# Cache global para o modelo Whisper - NUNCA deixar o GC destruir o modelo
# CTranslate2 tem um bug no destrutor que causa SIGABRT ao libertar memória CUDA
_whisper_model_cache = None

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

def transcrever_audio_whisper(caminho_audio):
    """
    Transcreve um arquivo de áudio usando Faster-Whisper com suporte GPU.
    Roda 100% LOCAL no seu computador, sem custos!
    
    Retorna timestamps de CADA segmento para legendas dinâmicas.
    
    Args:
        caminho_audio (str): Caminho do arquivo de áudio (MP3, WAV, etc)
    
    Returns:
        dict: Dicionário com 'texto_completo' e 'segmentos' (com timestamps)
    """
    try:
        # Detecta GPU
        device, gpu_disponivel, info_gpu = verificar_gpu()
        print(info_gpu)
        
        print(f"Transcrevendo áudio com Faster-Whisper...")
        if gpu_disponivel:
            print(f"⚡ Usando GPU - transcrição RÁPIDA! (aprox. 20-60 segundos)")
        else:
            print(f"⏳ Usando CPU - transcrição mais lenta (aprox. 2-5 minutos)")
        
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
        
        t_elapsed = _time.time() - t_start
        print(f"✅ Transcrição concluída em {t_elapsed:.1f}s! ({len(lista_segmentos)} segmentos)", flush=True)
        
        # NÃO apagar o modelo! O destrutor do CTranslate2 causa SIGABRT.
        # O modelo fica no _whisper_model_cache global.
        # O Ollama é um processo separado com o seu próprio contexto CUDA,
        # por isso consegue gerir a GPU independentemente.
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

def analisar_com_ollama(transcrição, modelo=None):
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
    
    Returns:
        list: Lista com os clipes recomendados (início, fim, motivo)
    """
    try:
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

        INTRO_SKIP_SEG = 120  # ignora os primeiros 2 min (intro/apresentação)
        CHAR_LIMIT      = 20000  # aumentado para dar mais contexto ao Llama

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
            "És uma API que responde APENAS em JSON. "
            "NUNCA escrevas explicações, cumprimentos, markdown, listas com hífen, nem texto fora de objetos JSON. "
            "Responde SEMPRE em Português (Portugal). "
            "Cada resposta é uma sequência de objetos JSON puros, UM POR LINHA, sem mais texto."
        )

        # Tenta obter a URL do vídeo original (para incluir na descrição)
        video_url = (
            (transcrição or {}).get("video_url")
            or (transcrição or {}).get("url")
            or (transcrição or {}).get("source_url")
            or ""
        )

        # User message: prompt de análise de clipes (PT-PT, padrão YouTube)
        user_msg = f"""Tens uma transcrição com timestamps de um vídeo (os primeiros 2 minutos já foram ignorados).

LINK DO VÍDEO ORIGINAL (usa este link na descrição):
{video_url}

TRANSCRIÇÃO (com timestamps):
{texto_timed}

TAREFA:
Escolhe 5 a 7 momentos (clipes) com maior potencial viral para YouTube Shorts.

REGRAS DE SELEÇÃO:
- Espalha os clipes ao longo do vídeo (não escolhas tudo no início).
- EXCLUI: patrocínios, intros/cumprimentos, partes lentas, pedidos de subscrição.
- INCLUI apenas momentos com pelo menos 1 destes gatilhos: POLÉMICA, IDENTIFICÁVEL, SURPREENDENTE, PICO EMOCIONAL, HOOK FORTE, ALTA ENERGIA.

REGRAS DE OUTPUT (CRÍTICO):
- Escreve APENAS em Português (Portugal).
- Output = APENAS objetos JSON, um por linha, sem markdown e sem texto extra.
- Chaves obrigatórias em cada objeto (exatamente estas): titulo, descricao, razao, transcript

FORMATO DE CADA OBJETO JSON (1 por linha):
{{
  "titulo": "Título curto (máx 60 caracteres), estilo YouTube, profissional e viral",
  "descricao": "2-5 linhas, tom YouTube. Inclui SEMPRE o link do vídeo original numa linha separada: {video_url}. Inclui 3-6 hashtags no fim (ex: #Shorts #YouTubeShorts ...)",
  "razao": "[GATILHO] Nota curta de edição (ex: corte seco, punch-in, legenda em destaque)",
  "transcript": "Copia as palavras exatas de abertura (da transcrição) deste momento"
}}

Agora devolve APENAS as linhas JSON:"""
        
        # Chama o modelo via ollama.chat (suporta system message para todos os modelos)
        print(f"  ⏳ Aguardando resposta de {modelo}...", flush=True)
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
                "num_ctx": 8192  # Context window ampliado para melhor análise (8K tokens)
            }
        )
        _t_llama_end = _t2.time()
        print(f"  ✅ {modelo} respondeu em {_t_llama_end - _t_llama:.1f}s", flush=True)

        # ollama.chat devolve um objeto — o texto está em .message.content
        resposta_texto = resposta.message.content if hasattr(resposta, 'message') else resposta["message"]["content"]
        
        # ── Extrai JSON da resposta (robusto a vários formatos) ──
        try:
            import re as regex
            clipes = []

            # Remove blocos markdown ```json ... ``` ou ``` ... ```
            texto_limpo = regex.sub(r'```(?:json)?\s*', '', resposta_texto)
            texto_limpo = texto_limpo.replace('```', '')

            # Estratégia 1: regex greedy que apanha objectos com chaves aninhadas
            # Encontra todos os {…} mesmo com strings longas dentro
            for m in regex.finditer(r'\{(?:[^{}]|\{[^{}]*\})*\}', texto_limpo):
                raw = m.group(0)
                try:
                    item = json.loads(raw)
                    # Aceita qualquer objecto que tenha título e razão
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
                print(f"✅ Análise concluída! {len(clipes)} clipes recomendados:")
                for i, clipe in enumerate(clipes, 1):
                    titulo = clipe.get('titulo') or clipe.get('title', 'Sem título')
                    print(f"  {i}. {titulo}")
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
