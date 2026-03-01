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

def analisar_com_ollama(transcrição):
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
    
    Returns:
        list: Lista com os clipes recomendados (início, fim, motivo)
    """
    try:
        # Verifica se Ollama está rodando
        try:
            ollama.list()
        except Exception as e:
            print("❌ Ollama não está rodando!")
            print("💡 Para rodar o Ollama:")
            print("   1. Abra o Ollama Desktop (na barra de tarefas)")
            print("   2. OU abra um terminal e digite: ollama serve")
            return None
        
        print("Analisando vídeo com Llama 2 (GRATUITO, no seu computador)...", flush=True)

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

        # Prompt focado em potencial viral com critérios claros de inclusão/exclusão
        prompt = f"""You are a world-class short-form video editor and retention specialist who has optimized countless viral videos on TikTok, Instagram Reels and YouTube Shorts. Your expertise: identifying moments with MAXIMUM RETENTION POWER through pacing, energy escalation, and psychological hooks.

The transcript below ALREADY skips the first 2 minutes (intro). Each line shows the timestamp [MM:SS] followed by the spoken words.

TRANSCRIPT:
{texto_timed}

---

YOUR TASK:
Select 5 to 7 clips (30–60 seconds each) with MAXIMAL ENGAGEMENT POTENTIAL. Spread them across different parts of the video — do NOT cluster them all near the beginning.

CRITICAL EDITING OPTIMIZATION FACTORS:
- ENERGY PEAKS: Prioritize moments where vocal pace ACCELERATES, volume INCREASES, or emotional INTENSITY jumps. These are ZOOM-WORTHY moments (rapid camera movement during peak energy = viewer neuro-lock).
- RHYTHM & PACING: Look for rapid-fire delivery, lists, contrasts, or quick idea volleys. Fast talking = fast editing = viewer cannot look away.
- PATTERN BREAKS: Sudden topic shifts, unexpected revelations, or sharp tonal changes. Brain MUST refocus when pattern breaks.
- OPEN LOOPS: Choose moments that make viewers wonder "wait, what happens next?" Creates irresistible forward momentum.

STRICT EXCLUSION RULES — NEVER select:
- Sponsor segments, ads, brand deals or product promotions
- Video intros where the creator greets the audience or introduces themselves
- Slow, meandering explanations or scene-setting with no payoff
- Filler content, transitions, "stay tuned" or "subscribe" calls to action
- Low-energy delivery, long pauses, or conversational drag

STRICT INCLUSION RULES — clip MUST have at least ONE of these:
1. POLEMIC / CONTROVERSIAL — divisive opinion generating "true vs wrong" comments. High debate energy.
2. RELATABLE — universal feeling triggering "this is literally me". Drives shares and saves.
3. SURPRISING / NOVEL — unknown fact or revelation stopping scrollers mid-swipe. Creates saves.
4. EMOTIONAL PEAK — raw intensity (anger, joy, shock, triumph). Visceral brain engagement = cannot look away.
5. STRONG HOOK — opening line SO PUNCHY the viewer physically cannot continue scrolling.
6. RHYTHM & DELIVERY ENERGY — fast-paced, energetic speech with vocal peaks. Optimal for dynamic editing and zoom effects.

For EACH clip, OUTPUT a JSON object on ONE single line with these exact keys:
{{"titulo":"Punchy title (max 8 words, action-oriented)", "razao":"[trigger] + editing note: suggest zoom/cut/effect if applicable", "transcript":"The exact opening words from the transcript for this clip"}}

Example with editing guidance:
{{"titulo":"Wait, this changes everything", "razao":"[SURPRISING] + High energy delivery - perfect for zoom-in on peak phrase + quick cut transition", "transcript":"[MM:SS] Actually nobody knows..."}}

OUTPUT — respond with ONLY JSON lines, nothing else:
{{"titulo":"T1", "razao":"[trigger] editing note", "transcript":"[T] words"}}
{{"titulo":"T2", "razao":"[trigger] editing note", "transcript":"[T] words"}}
{{"titulo":"T3", "razao":"[trigger] editing note", "transcript":"[T] words"}}
{{"titulo":"T4", "razao":"[trigger] editing note", "transcript":"[T] words"}}
{{"titulo":"T5", "razao":"[trigger] editing note", "transcript":"[T] words"}}"""
        
        # Chama o Llama rodando localmente
        print("  ⏳ Aguardando resposta do Llama 2...", flush=True)
        import time as _t2
        _t_llama = _t2.time()
        resposta = ollama.generate(
            model="llama2",
            prompt=prompt,
            stream=False
        )
        _t_llama_end = _t2.time()
        print(f"  ✅ Llama respondeu em {_t_llama_end - _t_llama:.1f}s", flush=True)
        
        resposta_texto = resposta["response"]
        
        # Extrai JSON da resposta
        try:
            clipes = []
            
            # Estratégia 1: Procura por padrões JSON {...} em qualquer lugar do texto
            import re as regex
            
            # Procura por padrões como {"titulo": ..., "razao": ..., "transcript": ...}
            # Usa um regex mais flexível para encontrar JSONs válidos
            pattern = r'\{[^{}]*"titulo"[^{}]*"razao"[^{}]*(?:"transcript"|"texto")[^{}]*\}'
            matches = regex.findall(pattern, resposta_texto)
            
            if matches:
                for json_str in matches:
                    try:
                        item = json.loads(json_str)
                        clipes.append(item)
                    except json.JSONDecodeError:
                        pass
            
            # Estratégia 2: Se não achou, tenta linha por linha
            if not clipes:
                for linha in resposta_texto.split('\n'):
                    # Remove números de lista (1., 2., etc)
                    linha = regex.sub(r'^\d+\.\s*', '', linha).strip()
                    if linha.startswith('{') and '}' in linha:
                        try:
                            # Extrai o JSON até o primeiro }
                            fim = linha.find('}') + 1
                            json_str = linha[:fim]
                            item = json.loads(json_str)
                            clipes.append(item)
                        except:
                            pass
            
            # Estratégia 3: Procura por um array JSON único
            if not clipes:
                inicio = resposta_texto.find("[")
                fim = resposta_texto.rfind("]") + 1
                if inicio != -1 and fim > inicio:
                    try:
                        json_str = resposta_texto[inicio:fim]
                        clipes = json.loads(json_str)
                        if not isinstance(clipes, list):
                            clipes = [clipes]
                    except:
                        pass
            
            if clipes and len(clipes) > 0:
                print(f"✅ Análise concluída! {len(clipes)} clipes recomendados:")
                for i, clipe in enumerate(clipes, 1):
                    titulo = clipe.get('titulo') or clipe.get('title', 'Sem título')
                    print(f"  {i}. {titulo}")
                return clipes
            
            # Se chegou aqui, não conseguiu parsear
            print("⚠️ Resposta do Llama (primeiros 300 chars):")
            print(resposta_texto[:300])
            print("\n💡 Dica: O Llama pode estar gerando um formato diferente.")
            print("   Tentando usar formato genérico...")
            
            # Tenta criar clipes genéricos baseado no texto
            clipes_genéricos = [
                {
                    "titulo": f"Clipe {i+1}",
                    "razao": "Momento interessante para clip",
                    "transcript": "Conteúdo extraído da transcrição"
                }
                for i in range(min(3, len(resposta_texto) // 200))
            ]
            
            if clipes_genéricos:
                print(f"✅ Usando {len(clipes_genéricos)} clipes genéricos")
                return clipes_genéricos
            
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
