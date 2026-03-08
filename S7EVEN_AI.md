# S7even AI — Documentários de Mistério com IA

Sistema de criação automática de vídeos documentários estilo **S7even** para YouTube.

## 🎬 O que é?

Um sistema completo que gera vídeos narrativos curtos (1-3 min) sobre:
- 🔍 Mistérios históricos desconh ecidos
- 🕵️ Crimes reais bizarros
- 👻 Anomalias paranormais documentadas
- 📚 Factos científicos assustadores
- 🌍 Eventos inexplicáveis

**Estilo**: Narração cinematográfica tipo S7even com:
- Persona "O Arquivista" (voz profunda, intrigada, sombria)
- Estrutura narrativa de suspense (Hook → Contexto → Mistério → Clímax → Reflexão)
- Efeitos visuais Ken Burns (zoom/pan lento)
- Música ambiente dark e efeitos sonoros

## 🚀 Como Usar

### 1️⃣ **Via API REST**

#### Criar um novo vídeo S7even

```bash
curl -X POST http://localhost:5000/api/s7even \
  -H "Content-Type: application/json" \
  -d '{
    "tema_preferido": "crime bizarro",
    "channel_id": "seu_channel_id",
    "auto_publish": false,
    "usar_elevenlabs": false
  }'
```

**Parâmetros:**
- `tema_preferido`: Tipo de história (opcional)
  - `"crime bizarro"` — crimes reais bizarros
  - `"mistério histórico"` — factos históricos desconhecidos
  - `"anomalia paranormal"` — eventos inexplicáveis
  - `"descoberta científica"` — ciência assustadora
  - Deixa vazio para aleatoriedade
  
- `channel_id`: ID do canal YouTube (usa padrão se omitido)
- `auto_publish`: Se `true`, publica automaticamente após edição
- `usar_elevenlabs`: Se `true`, usa ElevenLabs para narração (requer API key, pago)

**Resposta:**
```json
{
  "sucesso": true,
  "video": {
    "titulo": "O Passaporte do País Fantasma",
    "arquivo_spec": "downloads/s7even_video_spec.json",
    "blocos_totais": 5,
    "tempo_criacao": "2025-03-08T14:30:45.123456"
  },
  "queue_item_id": "abc123def456",
  "queue_item": { ... vídeo adicionado à queue ... }
}
```

#### Listar vídeos S7even

```bash
curl http://localhost:5000/api/s7even
```

#### Obter detalhes de um vídeo

```bash
curl http://localhost:5000/api/s7even/abc123def456
```

#### Publicar um vídeo S7even

```bash
curl -X POST http://localhost:5000/api/s7even/abc123def456/publish \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "seu_channel_id",
    "auto_publish": true
  }'
```

### 2️⃣ **Via Python Direto**

```python
import s7even_ai

# Criar vídeo S7even completo
resultado = s7even_ai.criar_video_s7even(
    tema_preferido="mistério histórico",
    usar_elevenlabs=False,  # Usa gTTS/pyttsx3 (gratuito)
    gerar_imagens_midjourney=False
)

if resultado["sucesso"]:
    print(f"✅ Vídeo criado: {resultado['titulo']}")
    print(f"📄 Spec: {resultado['arquivo_spec']}")
else:
    print(f"❌ Erro: {resultado['erro']}")

# Ou fazer passo-a-passo
historia = s7even_ai.pesquisar_historia("crime bizarro")
guiao = s7even_ai.gerar_guiao_s7even(historia)
guiao = s7even_ai.buscar_imagens_guiao(guiao)
guiao = s7even_ai.gerar_audio_naracao(guiao, usar_elevenlabs=False)
spec_path = s7even_ai.exportar_para_ffmpeg(guiao)
```

## 🛠️ Configuração

### APIs Externas (Opcionais, Pagas)

#### ElevenLabs (Narração Premium)

Se queres usar **vozes profissionais** in lá de gTTS/pyttsx3:

1. **Cria conta** em https://elevenlabs.io
2. **Gera API Key** em https://elevenlabs.io/api-keys
3. **Nomeia uma voz** (recomendação: "Antoni" — documentário profundo)
4. **Configura variáveis de ambiente**:

```bash
# .env
ELEVENLABS_API_KEY=sk_58...xyz
ELEVENLABS_VOICE_ID=Antoni
```

Ou:

```powershell
# PowerShell (Windows)
$env:ELEVENLABS_API_KEY = "sk_58...xyz"
$env:ELEVENLABS_VOICE_ID = "Antoni"
```

#### Midjourney / Stable Diffusion (Geração de Imagens)

Para **gerar imagens customizadas** em vez de buscar stock:

1. Setup Midjourney API ou Stable Diffusion local
2. Configura no `.env`:

```bash
MIDJOURNEY_API_KEY=mj_...
# ou
STABLE_DIFFUSION_API_URL=http://localhost:7860
```

A pipeline criará automaticamente prompts tipo:
```
"Fotografia vintage de aeroporto nos anos 50, preto e branco, estilo sombrio, dark academia"
```

#### APIs de Busca de Imagens (Gratuitas)

Para buscar imagens **stock gratuitas** (Pexels, Pixabay):

```bash
# .env
PEXELS_API_KEY=sua_chave_pexels
PIXABAY_API_KEY=sua_chave_pixabay
UNSPLASH_API_KEY=sua_chave_unsplash
```

(opcionais — a pipeline usa fallback se não estiverem configuradas)

## 📊 Estrutura de Saída

### Ficheiro de Especificação do Vídeo

Locação: `downloads/s7even_video_spec.json`

```json
{
  "titulo": "O Passaporte do País Fantasma",
  "resumo": "Em 1954, um homem apareceu num aeroporto com um passaporte de um país que não existe.",
  "duracao_total_segundos": 90,
  "fps": 30,
  "resolucao": "1920x1080",
  "timeline": [
    {
      "bloco_id": 1,
      "secao": "HOOK",
      "tempo_inicio": 0,
      "duracao": 5,
      "texto": "Sabias que em 1954, um homem aterrou no Japão com um passaporte de um país que não existe? [PAUSA]",
      "arquivo_audio": "downloads/s7even_audio/bloco_1.mp3",
      "arquivo_imagem": "https://images.url.com/vintage-airport.jpg",
      "efeito_visual": "zoom_in_rapido",
      "efeito_sonoro": "Som de carimbo + Bass Drop"
    },
    ...
  ]
}
```

### Diretórios de Saída

```
downloads/
├── s7even_audio/           # Áudio da narração (MP3)
│   ├── bloco_1.mp3
│   ├── bloco_2.mp3
│   └── ...
├── s7even_video_spec.json  # Spec do vídeo (para editor)
└── s7even_images/          # Imagens geradas/baixadas (opcional)
    ├── bloco_1_scene.jpg
    └── ...
```

## 🎨 Persona "O Arquivista"

A IA funciona como **uma entidade misteriosa** que narra os vídeos:

- **Tom**: Profundo, intrigante, ligeiramente sombrio
- **Velocidade**: Normal (150 WPM recomendado)
- **Pausas**: [PAUSA] insere hesitações dramáticas
- **Linguagem**: Português de Portugal (PT-PT), gramaticalmente perfeita
- **Estilo**: Frases curtas, impactantes. Como contar um segredo ao ouvido.

Exemplo de narração:
> "Sabias que em 1954... [PAUSA] um homem apareceu num aeroporto europeu? 
> Ele tinhaum passaporte. Mas havia um problema. [PAUSA] 
> O país que nele estava impresso... nunca existiu."

## 🔧 Integração com Worker/Pipeline Existente

O `worker.py` processará automaticamente vídeos S7even adicionados à queue:

```python
# Em worker.py (já suportado)
if "s7even://" in item.get("url", ""):
    # Detecta vídeo S7even
    spec_file = item.get("s7even_spec_file")
    # ... faz edição/processamento ...
    # ... publica se auto_publish=True ...
```

## 📚 Exemplos Avançados

### Gerar múltiplos vídeos em lote

```python
import s7even_ai

temas = [
    "crime bizarro",
    "mistério histórico",
    "anomalia paranormal",
    "descoberta científica"
]

for tema in temas:
    resultado = s7even_ai.criar_video_s7even(tema_preferido=tema)
    if resultado["sucesso"]:
        print(f"✅ {resultado['titulo']}")
    else:
        print(f"❌ {resultado['erro']}")
```

### Customizar persona/tom

(Futuro) — Permitir diferentes personas:
```python
# Em desenvolvimento:
s7even_ai.criar_video_s7even(
    tema_preferido="...",
    persona="O Coletor",  # Outro estilo
    tom="mais assustador"  # Variar intensidade
)
```

## 🐛 Troubleshooting

### Erro: "s7even_ai module not found"

```bash
# Verifica se o arquivo existe
ls -la s7even_ai.py

# Se criar em lugar errado, move para root do projeto
mv /caminho/s7even_ai.py ./s7even_ai.py
```

### Erro: "Ollama not running"

```bash
# Inicia Ollama
ollama serve

# Em outra terminal/janela, testa
ollama pull llama3.1
```

### TTS falhando (gTTS com erro de internet)

```python
# Fallback automático para pyttsx3
import pyttsx3
engine = pyttsx3.init()
engine.say("Teste")
engine.runAndWait()
```

### Imagens não encontradas

As APIs de busca falharam. Fallback automático:
1. Tenta Unsplash → Pexels → Pixabay
2. Se tudo falhar, marca para **Midjourney manual** (sem key)
3. Edita manualmente com imagens custom

## 📈 Roadmap Futuro

- [ ] Suporte a múltiplas línguas (ES, FR, EN, etc.)
- [ ] API de LLMs alternativos (Claude, GPT, Cohere)
- [ ] Diferentes personas/tons narrativos
- [ ] Integração com MongoDB para histórias (em vez de Ollama)
- [ ] Editor web visual de roteiros S7even
- [ ] Publicação automática com scheduling
- [ ] Analytics de engajamento por tema
- [ ] Gerador de thumbnails automático

## 📞 Suporte

**Dúvidas?**

1. Verifica `S7Even AI` logs no terminal
2. Lê `SETUP.md` para configuração base
3. Testa a API com curl (exemplos acima)
4. Abre issue no repositório

---

**Criado em**: Março 2025  
**Autor**: ClipAI + S7even AI  
**Licença**: Vê `README.md`
