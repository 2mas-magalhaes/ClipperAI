"""
S7EVEN AI - Sistema de Criação de Documentários de Mistério (Master Prompt Implementation)

Cria vídeos narrativos curtos (1-3 minutos) tipo canal S7even:
- Histórias de mistério, factos bizarros, eventos inexplicáveis
- Narrativa bem estruturada com suspense
- Estrutura visual cinematográfica (Ken Burns, efeitos profissionais)
- Persona: "O Arquivista" - entidade inteligente, calma, intrigante

Fluxo:
  1. Pesquisa de história (search) → encontra tema cativante
  2. Escrita de guião (estrutura S7even) → hook + contexto + mistério + clímax + reflexão
  3. Geração visual/sonora → mapping imagens, efeitos, música para cada cena
  4. Output estruturado → tabela pronta para editor de vídeo
"""

import os
import json
import logging
import re
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import ollama

# ─────────────────────────────────────────────────────────────
# CONFIGURAÇÃO LOGGER
# ─────────────────────────────────────────────────────────────

logger = logging.getLogger("S7evenAI")
logger.setLevel(logging.INFO)


# ─────────────────────────────────────────────────────────────
# SYSTEM PROMPT - "O ARQUIVISTA"
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT_ARQUIVISTA = """
#[SYSTEM ROLE]
És um Criador de Conteúdo e Diretor de Documentários de Mistério de elite, especializado no estilo do canal de YouTube "S7even". 
O teu objetivo é criar vídeos narrativos curtos (1 a 3 minutos) sobre factos históricos, mistérios da internet, crimes reais ou curiosidades bizarras.

Vais atuar sob a persona de "O Arquivista": uma entidade inteligente, calma, com um tom de voz profundo, intrigante e ligeiramente sombrio, 
que desvenda os segredos do mundo.

#[WORKFLOW - O TEU PROCESSO DE CRIAÇÃO]

**Passo 1: Pesquisa de História**
Encontra 1 (um) facto, história real ou mistério altamente cativante e pouco conhecido.
Temas preferidos: Eventos inexplicáveis, anomalias históricas, paradoxos, crimes resolvidos de forma bizarra, descobertas científicas assustadoras.

**Passo 2: Escrita do Guião (O Estilo S7even)**
O guião DEVE seguir a curva de retenção máxima:
- [0:00 - 0:05] O HOOK: Uma frase de abertura chocante que cria uma pergunta imediata
- [0:05 - 0:30] O CONTEXTO: Estabelecer a normalidade antes de tudo dar para o torto
- [0:30 - 1:00] O MISTÉRIO/CONFLITO: A reviravolta. O que torna esta história única
- [1:00 - 1:20] O CLÍMAX: A resolução ou o facto mais perturbador
- [1:20 - 1:30] OUTRO: Uma reflexão final que deixa o espectador a pensar

**Passo 3: Mapeamento Visual e Sonoro**
Para cada frase falada, define uma imagem (ou prompt) e ambiente sonoro.
Estética: Dark academia, imagens de arquivo (found footage), fotografias antigas, efeito Ken Burns (zoom/pan lento).

#[REGRAS DE NARRAÇÃO]
- Linguagem em Português de Portugal (PT-PT), altamente gramatical
- Frases curtas e de impacto
- [PAUSA] para criar suspense na voz de IA
- Tom confidencial, como contar um segredo ao ouvido do espectador

#[REGRAS DE SAÍDA]
DEVES DEVOLVER SEMPRE EM FORMATO JSON ESTRUTURADO:
{
  "titulo_video": "Título clickbait do vídeo",
  "resumo_facto": "1 frase sobre o que encontraste",
  "persona": "O Arquivista",
  "duracao_estimada": "1:30",
  "blocos": [
    {
      "id": 1,
      "secao": "HOOK",
      "tempo": "0:00-0:05",
      "narrador": "Texto exato para TTS (com [PAUSA] para breaks)",
      "prompt_imagem": "Descrição detalhada para gerar/buscar imagem",
      "tipo_foto": "vintage/arquivo/mistério",
      "efeito_visual": "zoom_in_rapido / pan_lento / dissolve_lento",
      "sfx_audio": "descrição de efeito sonoro + música"
    },
    ...
  ],
  "notas_edicao": "Instruções especiais para o editor de vídeo"
}

Deves ser criativo, envolvente e rigorosamente fiel ao estilo cinematográfico do S7even.
"""


# ─────────────────────────────────────────────────────────────
# FUNÇÃO: PESQUISA DE HISTÓRIA
# ─────────────────────────────────────────────────────────────

def pesquisar_historia(tema_preferido: Optional[str] = None) -> Dict:
    """
    Usa Ollama (local) para gerar uma história interessante de mistério.
    Se não houver Ollama, faz fallback com Base de dados local.
    
    Args:
        tema_preferido: Tipo de história preferida (ex: "crime bizarro", "anomalia histórica")
    
    Returns:
        Dict com informações da história encontrada
    """
    
    prompt_pesquisa = f"""
Gera uma história real, documentada e insólita para um documento tipo "S7even".
Tema preferido: {tema_preferido or 'qualquer mistério, crime bizarro ou anomalia histórica'}

Critérios:
- Facto real e verificável (não ficção)
- Pouco conhecido pelo público geral
- Perturbador, intrigante ou misterioso
- Bem documentado em fontes históricas

MUITO IMPORTANTE: Responde APENAS com JSON válido, sem markdown ou explicações.

{{
  "titulo": "Título da história",
  "resumo": "1-2 frases sobre o que aconteceu",
  "personagens_principais": ["nome1", "nome2"],
  "data_evento": "YYYY-MM-DD ou período",
  "local": "Localização geográfica",
  "fatos_chocantes": ["facto 1", "facto 2", "facto 3"],
  "fonte_referencia": "Onde encontraste isto"
}}
"""
    
    try:
        logger.info("🔍 Pesquisando história com Ollama...")
        response = ollama.generate(
            model="llama3.1",
            prompt=prompt_pesquisa,
            stream=False
        )
        
        raw_response = response.get("response", "").strip()
        
        # Limpar markdown code blocks
        raw_response = re.sub(r'```json\s*', '', raw_response)
        raw_response = re.sub(r'```\s*$', '', raw_response)
        raw_response = raw_response.strip()
        
        # Tentar múltiplas estratégias de extração JSON
        historia = None
        
        # Estratégia 1: JSON direto
        try:
            historia = json.loads(raw_response)
            logger.info(f"✅ História encontrada: {historia.get('titulo', 'Sem título')}")
            return historia
        except json.JSONDecodeError:
            pass
        
        # Estratégia 2: JSON entre chaves (greedy)
        json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_response, re.DOTALL)
        if json_matches:
            for json_str in json_matches:
                try:
                    historia = json.loads(json_str)
                    if historia.get('titulo') and historia.get('resumo'):
                        logger.info(f"✅ História encontrada: {historia.get('titulo')}")
                        return historia
                except json.JSONDecodeError:
                    continue
        
        # Estratégia 3: Procurar primeiro { até último }
        start_idx = raw_response.find('{')
        end_idx = raw_response.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = raw_response[start_idx:end_idx+1]
            try:
                historia = json.loads(json_str)
                if historia.get('titulo') and historia.get('resumo'):
                    logger.info(f"✅ História encontrada: {historia.get('titulo')}")
                    return historia
            except json.JSONDecodeError as e:
                logger.debug(f"Tentativa 3 falhou: {e}")
        
        logger.warning(f"⚠️ Ollama devolveu resposta: {raw_response[:200]}...")
    
    except Exception as e:
        logger.warning(f"⚠️ Erro ao pesquisar com Ollama: {e}")
    
    # Fallback: Histórias pré-definidas
    historias_fallback = [
        {
            "titulo": "O Passaporte do País Fantasma",
            "resumo": "Em 1954, um homem apareceu num aeroporto europeu com um passaporte de um país que não existe.",
            "personagens_principais": ["John Zegrus (pseudo)"],
            "data_evento": "1954-07-20",
            "local": "Aeroporto de Bruxelas, Bélgica",
            "fatos_chocantes": [
                "Passaporte de 'Taured' - país que não existe em nenhum mapa",
                "Homem calmo e convincente, conhecido em Taured",
                "Desapareceu da quarto de hotel antes de investigação completa"
            ],
            "fonte_referencia": "Caso documentado em ficheiros de polícia belga"
        },
        {
            "titulo": "A Hora do Assassinato que Não Havia",
            "resumo": "Um relógio parou exactamente à hora do crime, mas ninguém sabe como ou porquê.",
            "personagens_principais": ["Vítima anónima", "Suspeito desconhecido"],
            "data_evento": "Vários casos históricos",
            "local": "Europa",
            "fatos_chocantes": [
                "Presença paranormal em certos crime",
                "Objetos inanimados 'testemunham' o crime",
                "Coincidências temporais demasiado precisas"
            ],
            "fonte_referencia": "Casos criminais documentados"
        }
    ]
    
    import random
    historia = random.choice(historias_fallback)
    logger.info(f"✅ Usando história fallback: {historia.get('titulo')}")
    return historia


# ─────────────────────────────────────────────────────────────
# FUNÇÃO: GERAÇÃO DE GUIÃO S7EVEN
# ─────────────────────────────────────────────────────────────

def gerar_guiao_s7even(historia: Dict) -> Dict:
    """
    Transforma uma história em guião estruturado tipo S7even.
    Usa Ollama com a System Prompt do Arquivista.
    
    Args:
        historia: Dict com dados da história (resultado de pesquisar_historia)
    
    Returns:
        Dict estruturado com blocos de narração, imagens e efeitos
    """
    
    contexto_historia = f"""
HISTÓRIA A ESTRUTURAR:
Título: {historia.get('titulo')}
Resumo: {historia.get('resumo')}
Data: {historia.get('data_evento')}
Local: {historia.get('local')}
Factos Chocantes: {', '.join(historia.get('fatos_chocantes', []))}

Usa todos estes detalhes para criar um guião envolvente tipo S7even.
O vídeo deve ter ~1:30 de duração total.
IMPORTANTE: Responde APENAS com JSON válido, sem markdown ou explicações extra.
"""
    
    prompt_completo = SYSTEM_PROMPT_ARQUIVISTA + "\n\n" + contexto_historia
    
    try:
        logger.info("✍️  Gerando guião com Ollama (Arquivista)...")
        response = ollama.generate(
            model="llama3.1",
            prompt=prompt_completo,
            stream=False
        )
        
        raw_output = response.get("response", "")
        
        # Tentar extrair JSON da resposta
        json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if json_match:
            guiao = json.loads(json_match.group())
            logger.info(f"✅ Guião gerado com {len(guiao.get('blocos', []))} blocos")
            return guiao
    
    except Exception as e:
        logger.warning(f"⚠️ Erro ao gerar guião: {e}")
    
    # Fallback: Guião estruturado manualmente
    guiao_fallback = {
        "titulo_video": historia.get('titulo', 'Mistério Desconhecido'),
        "resumo_facto": historia.get('resumo', 'Um facto histórico perturbador'),
        "persona": "O Arquivista",
        "duracao_estimada": "1:30",
        "blocos": [
            {
                "id": 1,
                "secao": "HOOK",
                "tempo": "0:00-0:05",
                "narrador": f"Sabias que {historia.get('resumo', 'aconteceu algo inexplicável')}? [PAUSA]",
                "prompt_imagem": "Imagem misteriosa relacionada com o lugar/evento",
                "tipo_foto": "arquivo",
                "efeito_visual": "zoom_in_rapido",
                "sfx_audio": "Som esquisito + Bass Drop intenso"
            },
            {
                "id": 2,
                "secao": "CONTEXTO",
                "tempo": "0:05-0:30",
                "narrador": f"Em {historia.get('data_evento', 'tempos remotos')}, no {historia.get('local', 'lugar indefinido')}, "
                           f"tudo parecia normal. [PAUSA] Ninguém esperava o que viria a acontecer.",
                "prompt_imagem": f"Fotografia histórica de {historia.get('local', 'arquivo')}, época antiga",
                "tipo_foto": "vintage",
                "efeito_visual": "pan_lento",
                "sfx_audio": "Música ambient sombria, tique de relógio ao fundo"
            },
            {
                "id": 3,
                "secao": "MISTÉRIO",
                "tempo": "0:30-1:00",
                "narrador": f"Mas foi quando... [PAUSA] "
                           f"{historia.get('fatos_chocantes', [''])[0] if historia.get('fatos_chocantes') else 'o inexplicável aconteceu'}.",
                "prompt_imagem": "Cena cinematográfica misteriosa, dark academia aesthetic",
                "tipo_foto": "mistério",
                "efeito_visual": "dissolve_lento",
                "sfx_audio": "Tensão crescente, efeitos paranormais suave"
            },
            {
                "id": 4,
                "secao": "CLÍMAX",
                "tempo": "1:00-1:20",
                "narrador": "E até aos dias de hoje... [PAUSA] ninguém consegue explicar o que realmente aconteceu.",
                "prompt_imagem": "Arquivo/documento antigo, assinatura ou evidência física",
                "tipo_foto": "arquivo",
                "efeito_visual": "zoom_in_lento",
                "sfx_audio": "Remate musical dramático, fade lento"
            },
            {
                "id": 5,
                "secao": "REFLEXÃO",
                "tempo": "1:20-1:30",
                "narrador": "Às vezes, os mistérios da história são mais perturbadores do que qualquer ficção. [PAUSA] O Arquivista.",
                "prompt_imagem": "Silhueta figura misteriosa, biblioteca biblioteca de arquivo",
                "tipo_foto": "dark academia",
                "efeito_visual": "fade_out_lento",
                "sfx_audio": "Música de encerramento, fade áudio"
            }
        ],
        "notas_edicao": """
        - Usar Ken Burns (zoom/pan) em TODAS as imagens
        - Legendas em amarelo brilhante quando o Arquivista fala
        - Efeito vinheta cinematográfica (border escuro)
        - Transições: fade (0.5s) entre blocos
        - Pool de música recomendada: "Suspense Strings", "Dark Ambient", "Mystery Theme"
        """
    }
    
    logger.info("✅ Usando guião fallback estruturado")
    return guiao_fallback


# ─────────────────────────────────────────────────────────────
# FUNÇÃO: ENRIQUECER GUIÃO COM IMAGENS
# ─────────────────────────────────────────────────────────────

def buscar_imagens_guiao(guiao: Dict) -> Dict:
    """
    Para cada bloco do guião, tenta buscar imagens reais.
    Tenta (por ordem): Unsplash → Pexels → Pixabay → Fallback descritivo
    
    Args:
        guiao: Guião estruturado do S7even
    
    Returns:
        Guião actualizado com URLs de imagens
    """
    
    logger.info("🖼️  Buscando imagens para os blocos...")
    
    api_keys = {
        "unsplash": os.getenv("UNSPLASH_API_KEY"),
        "pexels": os.getenv("PEXELS_API_KEY"),
        "pixabay": os.getenv("PIXABAY_API_KEY")
    }
    
    for bloco in guiao.get("blocos", []):
        prompt_imagem = bloco.get("prompt_imagem", "")
        
        # Tentar Unsplash
        if api_keys["unsplash"]:
            try:
                url = f"https://api.unsplash.com/search/photos?query={prompt_imagem}&per_page=1"
                headers = {"Authorization": f"Client-ID {api_keys['unsplash']}"}
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("results"):
                        bloco["imagem_url"] = data["results"][0]["urls"]["regular"]
                        bloco["imagem_fonte"] = "unsplash"
                        logger.info(f"  ✅ Bloco {bloco['id']}: imagem Unsplash encontrada")
                        continue
            except Exception as e:
                logger.debug(f"  Unsplash falhou: {e}")
        
        # Tentar Pexels
        if api_keys["pexels"]:
            try:
                url = "https://api.pexels.com/v1/search"
                headers = {"Authorization": api_keys["pexels"]}
                response = requests.get(url, headers=headers, params={"query": prompt_imagem, "per_page": 1}, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("photos"):
                        bloco["imagem_url"] = data["photos"][0]["src"]["original"]
                        bloco["imagem_fonte"] = "pexels"
                        logger.info(f"  ✅ Bloco {bloco['id']}: imagem Pexels encontrada")
                        continue
            except Exception as e:
                logger.debug(f"  Pexels falhou: {e}")
        
        # Fallback: apenas descrição (será usado para Midjourney ou geração local)
        bloco["imagem_url"] = None
        bloco["imagem_fonte"] = "midjourney_pending"
        logger.info(f"  ⏳ Bloco {bloco['id']}: aguardando geração com Midjourney")
    
    return guiao


# ─────────────────────────────────────────────────────────────
# FUNÇÃO: GERAR ÁUDIO TTS
# ─────────────────────────────────────────────────────────────

def gerar_audio_naracao(guiao: Dict, usar_elevenlabs: bool = False) -> Dict:
    """
    Gera áudio para a narração de cada bloco.
    
    Tenta:
      1. ElevenLabs (se API key configurada e usar_elevenlabs=True)
      2. gTTS (Google Text-to-Speech) - GRATUITO
      3. pyttsx3 (local, offline) - GRATUITO
    
    Args:
        guiao: Guião estruturado
        usar_elevenlabs: Se True, tenta ElevenLabs (requer API key)
    
    Returns:
        Guião actualizado com caminhos de áudio
    """
    
    logger.info("🎙️  Gerando áudio de narração...")
    
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "Antoni")  # Voice recomendada: deep, documentary
    
    for bloco in guiao.get("blocos", []):
        texto = bloco.get("narrador", "").replace("[PAUSA]", " ")
        bloco_id = bloco.get("id")
        
        # Caminho de saída
        audio_path = f"downloads/s7even_audio/bloco_{bloco_id}.mp3"
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        
        # 1. Tentar ElevenLabs
        if usar_elevenlabs and elevenlabs_key:
            try:
                logger.info(f"  🔊 Bloco {bloco_id}: gerando com ElevenLabs (voz profunda)...")
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{elevenlabs_voice_id}"
                headers = {
                    "xi-api-key": elevenlabs_key,
                    "Content-Type": "application/json"
                }
                data = {
                    "text": texto,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.9
                    }
                }
                response = requests.post(url, json=data, headers=headers, timeout=30)
                if response.status_code == 200:
                    with open(audio_path, "wb") as f:
                        f.write(response.content)
                    bloco["audio_url"] = audio_path
                    bloco["audio_source"] = "elevenlabs"
                    logger.info(f"  ✅ Bloco {bloco_id}: áudio ElevenLabs gerado")
                    continue
            except Exception as e:
                logger.warning(f"  ⚠️ ElevenLabs falhou: {e}")
        
        # 2. Tentar gTTS (Google TTS) - GRATUITO
        try:
            from gtts import gTTS
            logger.info(f"  🔊 Bloco {bloco_id}: gerando com gTTS (Google)...")
            tts = gTTS(text=texto, lang="pt", slow=False)
            tts.save(audio_path)
            bloco["audio_url"] = audio_path
            bloco["audio_source"] = "gtts"
            logger.info(f"  ✅ Bloco {bloco_id}: áudio gTTS gerado")
            continue
        except ImportError:
            logger.debug("  gTTS não instalado, tentando pyttsx3...")
        except Exception as e:
            logger.warning(f"  ⚠️ gTTS falhou: {e}")
        
        # 3. Fallback: pyttsx3 (local, offline)
        try:
            import pyttsx3
            logger.info(f"  🔊 Bloco {bloco_id}: gerando com pyttsx3 (local/offline)...")
            engine = pyttsx3.init()
            engine.setProperty("rate", 150)  # Velocidade normal
            engine.setProperty("volume", 0.9)
            
            # Tentar configurar português
            try:
                engine.setProperty("voice", [v for v in engine.getProperty("voices") 
                                            if "pt" in v.languages or "portuguese" in v.name.lower()][0].id)
            except:
                pass  # Usar voz padrão se português não disponível
            
            engine.save_to_file(texto, audio_path)
            engine.runAndWait()
            bloco["audio_url"] = audio_path
            bloco["audio_source"] = "pyttsx3"
            logger.info(f"  ✅ Bloco {bloco_id}: áudio pyttsx3 gerado")
        except ImportError:
            logger.warning(f"  ⚠️ pyttsx3 não instalado. Instale com: pip install pyttsx3")
            bloco["audio_url"] = None
            bloco["audio_source"] = "nenhum"
        except Exception as e:
            logger.error(f"  ❌ Erro ao gerar áudio pyttsx3: {e}")
            bloco["audio_url"] = None
    
    return guiao


# ─────────────────────────────────────────────────────────────
# FUNÇÃO: EXPORTAR PARA EDITOR DE VÍDEO
# ─────────────────────────────────────────────────────────────

def exportar_para_ffmpeg(guiao: Dict, output_json: str = "downloads/s7even_video_spec.json") -> str:
    """
    Exporta guião em formato que o FFmpeg/editor de vídeo consegue processar.
    
    Args:
        guiao: Guião estruturado com blocos, imagens e áudio
        output_json: Caminho de saída
    
    Returns:
        Caminho do ficheiro JSON exportado
    """
    
    logger.info("💾 Exportando especificação de vídeo para editor...")
    
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    
    # Estruturar para FFmpeg/editor
    spec_video = {
        "titulo": guiao.get("titulo_video"),
        "resumo": guiao.get("resumo_facto"),
        "duracao_total_segundos": 90,  # ~1:30
        "fps": 30,
        "resolucao": "1920x1080",
        "codec_video": "h264",
        "codec_audio": "aac",
        "timeline": []
    }
    
    tempo_acumulado = 0
    
    for bloco in guiao.get("blocos", []):
        # Parse do tempo
        tempo_str = bloco.get("tempo", "0:00-0:05")
        if "-" in tempo_str:
            tempo_inicio = tempo_str.split("-")[0]
            minutos, segundos = map(int, tempo_inicio.split(":"))
            tempo_seg = minutos * 60 + segundos
        else:
            tempo_seg = tempo_acumulado
        
        evento_timeline = {
            "bloco_id": bloco.get("id"),
            "secao": bloco.get("secao"),
            "tempo_inicio": tempo_seg,
            "duracao": 5,  # Cada bloco dura ~5 segundos
            "texto": bloco.get("narrador"),
            "arquivo_audio": bloco.get("audio_url"),
            "arquivo_imagem": bloco.get("imagem_url"),
            "tipo_imagem": bloco.get("tipo_foto"),
            "efeito_visual": bloco.get("efeito_visual"),
            "efeito_sonoro": bloco.get("sfx_audio"),
            "prompt_imagem": bloco.get("prompt_imagem")
        }
        
        spec_video["timeline"].append(evento_timeline)
        tempo_acumulado += 5
    
    # Salvar JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(spec_video, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Especificação de vídeo exportada: {output_json}")
    return output_json


# ─────────────────────────────────────────────────────────────
# FUNÇÃO PRINCIPAL: PIPELINE COMPLETA
# ─────────────────────────────────────────────────────────────

def criar_video_s7even(tema_preferido: Optional[str] = None,
                       usar_elevenlabs: bool = False,
                       gerar_imagens_midjourney: bool = False) -> Dict:
    """
    Pipeline completa para criar um vídeo estilo S7even:
    
    1. Pesquisa história → 2. Gera guião → 3. Busca imagens → 4. Gera áudio → 5. Exporta spec
    
    Args:
        tema_preferido: Tipo de história (ex: "crime bizarro", "anomalia histórica")
        usar_elevenlabs: Se True, usa ElevenLabs para narração (pago)
        gerar_imagens_midjourney: Se True, marca imagens para Midjourney
    
    Returns:
        Dict com resultado completo e caminhos dos ficheiros
    """
    
    logger.info("=" * 70)
    logger.info("🎬 INICIANDO CRIAÇÃO DE VÍDEO S7EVEN")
    logger.info("=" * 70)
    
    try:
        # 1. PESQUISA
        logger.info("\n[1/5] PESQUISA DE HISTÓRIA")
        historia = pesquisar_historia(tema_preferido)
        
        # 2. GUIÃO
        logger.info("\n[2/5] GERAÇÃO DE GUIÃO")
        guiao = gerar_guiao_s7even(historia)
        
        # 3. IMAGENS
        logger.info("\n[3/5] BUSCA DE IMAGENS")
        guiao = buscar_imagens_guiao(guiao)
        
        # 4. ÁUDIO
        logger.info("\n[4/5] GERAÇÃO DE ÁUDIO")
        guiao = gerar_audio_naracao(guiao, usar_elevenlabs=usar_elevenlabs)
        
        # 5. EXPORTAR
        logger.info("\n[5/5] EXPORTAR PARA EDITOR")
        output_json = exportar_para_ffmpeg(guiao)
        
        resultado = {
            "sucesso": True,
            "titulo": guiao.get("titulo_video"),
            "arquivo_spec": output_json,
            "historia": historia,
            "blocos_totais": len(guiao.get("blocos", [])),
            "tempo_criacao": datetime.now().isoformat()
        }
        
        logger.info("\n" + "=" * 70)
        logger.info(f"✅ VÍDEO S7EVEN CRIADO COM SUCESSO!")
        logger.info(f"   Título: {guiao.get('titulo_video')}")
        logger.info(f"   Blocos: {len(guiao.get('blocos', []))}")
        logger.info(f"   Ficheiro: {output_json}")
        logger.info("=" * 70)
        
        return resultado
    
    except Exception as e:
        logger.error(f"❌ Erro na pipeline S7even: {e}", exc_info=True)
        return {
            "sucesso": False,
            "erro": str(e),
            "tempo_criacao": datetime.now().isoformat()
        }


# ─────────────────────────────────────────────────────────────
# TESTES / MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Teste rápido
    resultado = criar_video_s7even(
        tema_preferido="mistério histórico desconhecido",
        usar_elevenlabs=False,  # Desativado por padrão (é pago)
        gerar_imagens_midjourney=False
    )
    
    print("\n" + json.dumps(resultado, indent=2, ensure_ascii=False))
