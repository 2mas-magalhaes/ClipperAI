# S7even AI — Quick Start Guide

Implementação completa do sistema de criação de documentários de mistério tipo S7even.

## 📦 O que foi implementado?

### 1. **Módulo Core: `s7even_ai.py`** (700+ linhas)
- ✅ System Prompt "O Arquivista" (persona narrativa configurável)
- ✅ Pesquisa de histórias com Ollama (local + fallback pré-definido)
- ✅ Geração de guião estruturado tipo S7even (5 blocos narrativos)
- ✅ Busca automática de imagens (Unsplash → Pexels → Pixabay)
- ✅ Geração de áudio narração (ElevenLabs → gTTS → pyttsx3)
- ✅ Exportação para FFmpeg (JSON com timeline completa)
- ✅ Pipeline integrada (tudo em 1 chamada)

### 2. **API REST Endpoints** (em `app.py`)
- `POST /api/s7even` — Criar novo vídeo S7even
- `GET /api/s7even` — Listar todos os S7even videos
- `GET /api/s7even/<video_id>` — Obter detalhes
- `POST /api/s7even/<video_id>/publish` — Marcar para publicação

### 3. **Integração com Queue Existente**
- ✅ Vídeos S7even adicionados à queue como itens normais
- ✅ Detecta automaticamente tipo "s7even"
- ✅ Worker processará quando implementado
- ✅ Suporta auto-publish e agendamento

### 4. **Documentação**
- ✅ `S7EVEN_AI.md` — Documentação completa (uso, configuração, exemplos)
- ✅ `test_s7even_ai.py` — Script de teste com 6 cenários
- ✅ `S7EVEN_QUICKSTART.md` — Este ficheiro (setup rápido)

## 🚀 Como Começar em 5 Minutos?

### Passo 1: Verifica Dependências

```bash
# Verifica Ollama (para pesquisa de histórias)
ollama list
# Output esperado: llama3.1 (ou outro modelo)

# Se não tem, instala:
ollama pull llama3.1

# Verifica Python packages
python -m pip list | findstr -E "faster.whisper|requests|ollama"
```

### Passo 2: Inicia o Servidor ClipAI

```bash
# Terminal 1
python run_server.py

# Output esperado:
# ✅ Ollamá conectado
# ✅ Servidor iniciado em http://localhost:5000
```

### Passo 3: Cria um Vídeo S7even (Terminal 2)

**Opção A: Via API REST**

```bash
curl -X POST http://localhost:5000/api/s7even \
  -H "Content-Type: application/json" \
  -d '{
    "tema_preferido": "crime bizarro",
    "auto_publish": false
  }'

# Response esperado (JSON com video_id, titulo, arquivo_spec)
```

**Opção B: Via Python Direto**

```bash
python test_s7even_ai.py
```

### Passo 4: Acompanha a Criação

Verifica os logs no Terminal 1:
```
🎬 INICIANDO CRIAÇÃO DE VÍDEO S7EVEN
[1/5] PESQUISA DE HISTÓRIA
✅ História encontrada: O Passaporte de um País Fantasma
[2/5] GERAÇÃO DE GUIÃO
✅ Guião gerado com 5 blocos
[3/5] BUSCA DE IMAGENS
✅ Bloco 1: imagem Pexels encontrada
...
[5/5] EXPORTAR PARA EDITOR
✅ Especificação de vídeo exportada: downloads/s7even_video_spec.json
```

### Passo 5: Guarda em Downloads

```
downloads/
├── s7even_audio/
│   ├── bloco_1.mp3          (narração Hook)
│   ├── bloco_2.mp3          (narração Contexto)
│   └── ... (5 blocos total)
└── s7even_video_spec.json   (spec para edição)
```

## 🎯 Casos de Uso

### Caso 1: Criar vídeo de teste

```bash
curl -X POST http://localhost:5000/api/s7ever \
  -H "Content-Type: application/json" \
  -d '{
    "tema_preferido": "mistério histórico",
    "channel_id": null,
    "auto_publish": false
  }'
```

### Caso 2: Criar múltiplos videos

```bash
# Em loop (bash/zsh)
for tema in "crime bizarro" "anomalia paranormal" "descoberta científica"; do
  curl -X POST http://localhost:5000/api/s7even \
    -H "Content-Type: application/json" \
    -d "{\"tema_preferido\": \"$tema\", \"auto_publish\": false}"
  echo ""
  sleep 2  # respira entre chamadas
done
```

### Caso 3: Com ElevenLabs (narração premium)

Primeiro, configura variáveis:

```bash
# Adiciona ao .env ou copia em PowerShell Windows:
$env:ELEVENLABS_API_KEY = "sk_...sua_chave..."
$env:ELEVENLABS_VOICE_ID = "Antoni"

# Depois:
curl -X POST http://localhost:5000/api/s7even \
  -H "Content-Type: application/json" \
  -d '{
    "tema_preferido": "crime bizarro",
    "usar_elevenlabs": true
  }'
```

## 📊 Estrutura de Ficheiros Criados

### Ficheiro de Spec (JSON)

```
downloads/s7even_video_spec.json
├── titulo: "O Passaporte do País Fantasma"
├── duracao_total_segundos: 90
├── fps: 30
├── resolucao: "1920x1080"
└── timeline: [
    {
      "bloco_id": 1,
      "secao": "HOOK",
      "tempo_inicio": 0,
      "arquivo_audio": "downloads/s7even_audio/bloco_1.mp3",
      "arquivo_imagem": "https://..../vintage-airport.jpg",
      "efeito_visual": "zoom_in_rapido",
      "efeito_sonoro": "Som de carimbo + Bass Drop"
    },
    ...
  ]
```

### Áudio (MP3)

Cada bloco tem um ficheiro MP3 separado:
- `bloco_1.mp3` — Hook (5s)
- `bloco_2.mp3` — Contexto (25s)
- `bloco_3.mp3` — Mistério (30s)
- `bloco_4.mp3` — Clímax (20s)
- `bloco_5.mp3` — Reflexão/Closure (10s)

## 🔧 Próximas Implementações

Para tornar **completamente automático** (do gen até ao YouTube):

### 1. Integrar FFmpeg para edição automática

```python
# Em worker.py (todo)
def editar_s7even_video(spec_file):
    spec = json.load(spec_file)
    cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", "filelist.txt",  # gerado do spec
        "-vf", "scale=1920:1080,fps=30",
        "-c:v", "libx264",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "output_final.mp4"
    ]
    subprocess.run(cmd, check=True)
```

### 2. Hook no Worker para S7even

```python
# Em worker.py
if item.get("url").startswith("s7even://"):
    spec_file = item.get("s7even_spec_file")
    # Edita o vídeo
    video_path = editar_s7even_video(spec_file)
    # Publica no YouTube (existe código já)
    upload_video_to_youtube(video_path, ...)
```

### 3. Dashboard UI para S7even

Adicionar tab no `templates/index.html`:
```html
<div class="tab s7even-videos">
  <h3>🎬 S7even Documentários</h3>
  <button onclick="criarS7evenVideo()">+ Novo Documentário</button>
  <!-- Lista de vídeos S7even com status -->
</div>
```

### 4. Scheduling/Publishing

```python
# Adicionar ao worker
if item.get("content_type") == "s7even" and item.get("auto_publish"):
    # Processa e publica automaticamente
    processar_e_publicar_s7even(item)
```

## 🧪 Testes

Executar suite de testes:

```bash
# Teste completo (6 cenários)
python test_s7even_ai.py

# Teste unitário específico
python -m pytest test_s7even_ai.py::teste_1_criar_video -v

# Teste API REST
curl -I http://localhost:5000/api/s7even
```

## 🔑 Configuração Avançada

### Usar ElevenLabs

Adiciona ao `.env`:
```
ELEVENLABS_API_KEY=sk_58...xyz  # De https://elevenlabs.io/api-keys
ELEVENLABS_VOICE_ID=Antoni      # Recomendado: documentário profundo
```

### Usar Stable Diffusion (imagens)

```
STABLE_DIFFUSION_API_URL=http://localhost:7860
```

### Usar Hugging Face (pesquisa de histórias)

```
HUGGINGFACE_API_KEY=hf_...
```

## 📈 Ciclo Completo Esperado

```
[Utilizador] → POST /api/s7even
    ↓
[s7even_ai] → Pesquisa história (Ollama)
    ↓
[s7even_ai] → Gera guião (estrutura S7even)
    ↓
[s7even_ai] → Busca imagens (Pexels/Unsplash)
    ↓
[s7even_ai] → Gera áudio (gTTS/ElevenLabs)
    ↓
[s7even_ai] → Exporta spec JSON
    ↓
[app.py] → Adiciona à queue
    ↓
[worker] → Detecta "s7even://"
    ↓
[worker] → FFmpeg compõe vídeo
    ↓
[worker] → Upload YouTube (com OAuth)
    ↓
[YouTube] → Vídeo publicado (privado)
    ↓
[Dashboard] → User escolhe vai ao "Go Live"
    ↓
[Success] → Vídeo público no YouTube
```

## 🐛 FAQ

**P: Preciso de chaves API para tudo?**
R: Não! Funciona completamente gratuito com:
- Ollama (local, gratis)
- gTTS (Google TTS, gratis)
- Pexels (imagens gratis)
- Pixabay (imagens gratis)

APIs pagas são opcionais (ElevenLabs para vozes premium, Midjourney para imagens custom).

**P: Quanto tempo demora criar um vídeo?**
R: ~30-60 segundos dependendo de:
- Ollama (pesquisa) — 10-15s
- Geração de guião — 15-20s
- Busca de imagens — 5-10s
- Geração de áudio — 5s
- Exportação — 1s

**P: Funciona offline?**
R: Sim! Com Ollama local + pyttsx3 + imagens pré-carregadas.

**P: Posso customizar a persona "Arquivista"?**
R: Sim — edita a variável `SYSTEM_PROMPT_ARQUIVISTA` em `s7even_ai.py`.

## 🎓 Aprender Mais

- Vê `S7EVEN_AI.md` — Documentação completa
- Lê code em `s7even_ai.py` — Bem comentado
- Estuda `test_s7even_ai.py` — Exemplos práticos
- Explora `app.py` — Rotas API

## 📞 Suporte

```
Alguma dúvida? Abre issue no repositório a descrever:
  1. O que tentaste fazer
  2. Qual foi o erro exacto
  3. Output do terminal (logs)
  4. Versão Python e SO
```

---

**Pronto? Vamo-nos!**

```bash
# Começa já:
python test_s7even_ai.py

# Ou:
python run_server.py
# + curl -X POST http://localhost:5000/api/s7even -H "Content-Type: application/json" -d '{}'
```

🚀 **Happy Movie Making!** 🎬
