# 🤖 PERSONAGEM CLIPPY - IA COM HOOKS VIRAIS

## 📝 Descrição

A personagem **Clippy** é um clipe de papel com olhos que aparece no início de cada vídeo editado para dar um **hook viral** e aumentar o engajamento.

### ✨ Funcionalidades

1. **Personagem Visual**: Clipe de papel animado com olhos expressivos
2. **Hooks com IA**: Geração automática de hooks virais usando Ollama (Llama 3.2)
3. **Voz Natural**: Síntese de voz usando Microsoft Edge TTS (gratuito e natural)
4. **Integração Automática**: Adicionado automaticamente no início de cada clip editado

---

## 🎯 Como Funciona

### 1. Geração do Hook
O Ollama (Llama 3.2) analisa:
- Título do clip
- Razão pela qual é viral
- Preview da transcrição

E gera um hook curto e impactante (máximo 120 caracteres).

**Exemplos de hooks gerados:**
- "Espera até veres o que acontece a seguir!"
- "Isto vai mudar a tua perspectiva para sempre"
- "Nunca vais acreditar no que ele fez"
- "A verdade que ninguém te conta"

### 2. Síntese de Voz
Usa **edge-tts** (Microsoft) para sintetizar a voz com qualidade natural:
- Voz: `pt-BR-FranciscaNeural` (feminina, jovem, energética)
- Velocidade: +15% (mais dinâmico)
- Tom: +5Hz (mais animado)

### 3. Composição Visual
O vídeo de intro (4-5 segundos) contém:
- Fundo: Primeiro frame do vídeo (desfocado e escurecido)
- Personagem Clippy centralizada
- Texto do hook na parte inferior
- Fade out suave
- Áudio sincronizado com o hook

### 4. Integração
A intro é automaticamente concatenada ao início do vídeo editado antes do loop infinito.

---

## 📦 Instalação

### Dependências Python

```bash
# Instalar edge-tts para síntese de voz
pip install edge-tts

# Já instaladas no projeto:
# - Pillow (para criar imagem do Clippy)
# - ollama (para gerar hooks)
```

### Verificar Instalação

```bash
# Testar edge-tts
edge-tts --text "Olá, eu sou a Clippy!" --voice pt-BR-FranciscaNeural --write-media teste.mp3

# Testar módulo Python
python personagem_clippy.py
```

---

## 🚀 Uso

### No Pipeline Principal

A funcionalidade está **ATIVADA POR PADRÃO** no `modulo3_edicao.py`:

```python
from modulo3_edicao import editar_clipes

# Com intro Clippy (padrão)
clipes_editados = editar_clipes(
    caminho_video, 
    clipes, 
    segmentos_whisper,
    adicionar_intro_clippy=True  # <-- Ativado por padrão
)

# Sem intro Clippy
clipes_editados = editar_clipes(
    caminho_video, 
    clipes, 
    segmentos_whisper,
    adicionar_intro_clippy=False  # <-- Desativar
)
```

### Teste Standalone

```python
from personagem_clippy import (
    criar_personagem_clippy,
    gerar_hook_com_ai,
    sintetizar_voz_hook,
    criar_intro_clippy
)

# 1. Criar imagem do Clippy
imagem = criar_personagem_clippy()

# 2. Gerar hook com AI
hook = gerar_hook_com_ai(
    titulo_clip="Segredo da Produtividade",
    razao_clip="Mostra técnica revolucionária"
)

# 3. Sintetizar voz
audio = sintetizar_voz_hook(hook)

# 4. Criar intro completa
intro = criar_intro_clippy(
    caminho_video_base="video.mp4",
    texto_hook=hook,
    caminho_saida="intro.mp4"
)
```

---

## ⚙️ Configurações

### Personalizar Voz

Edite `personagem_clippy.py` na função `sintetizar_voz_hook()`:

```python
# Vozes disponíveis:
# PT-BR: pt-BR-FranciscaNeural (feminina), pt-BR-AntonioNeural (masculina)
# PT-PT: pt-PT-RaquelNeural (feminina), pt-PT-DuarteNeural (masculina)

voz = "pt-BR-FranciscaNeural"  # Alterar aqui
```

### Personalizar Duração da Intro

Edite `modulo3_edicao.py` onde chama `criar_intro_clippy()`:

```python
intro_criada = criar_intro_clippy(
    caminho_preloop,
    hook_gerado,
    caminho_intro,
    duracao_intro=4.5,  # <-- Alterar aqui (segundos)
    fade_out_duracao=0.5
)
```

### Personalizar Aparência do Clippy

Edite `personagem_clippy.py` na função `criar_personagem_clippy()`:

```python
# Cores
cor_clip = (220, 220, 220, 255)  # Corpo do clipe
cor_olho_branco = (255, 255, 255, 255)
cor_pupila = (50, 50, 50, 255)

# Dimensões
clip_width = largura // 3  # Tamanho do clipe
olho_raio = 70  # Tamanho dos olhos
```

---

## 🎨 Personalização Avançada

### Adicionar Animações

Para adicionar animações à personagem (piscar de olhos, movimento, etc.):

1. Crie múltiplos frames da personagem
2. Use FFmpeg para criar vídeo animado
3. Substitua a imagem estática pelo vídeo animado

```python
# Em personagem_clippy.py
def criar_personagem_animada():
    # Criar frames: clippy_frame_001.png, clippy_frame_002.png, etc.
    # ...
    
    # Converter para vídeo
    subprocess.run([
        'ffmpeg', '-framerate', '30',
        '-i', 'clippy_frame_%03d.png',
        '-c:v', 'libx264', '-pix_fmt', 'yuva420p',
        'clippy_animado.mp4'
    ])
```

### Múltiplas Expressões

Crie diferentes versões do Clippy com expressões variadas:

```python
def criar_personagem_clippy(expressao="feliz"):
    # expressao pode ser: "feliz", "surpreso", "pensativo", etc.
    if expressao == "feliz":
        # Desenhar boca sorridente
        pass
    elif expressao == "surpreso":
        # Olhos maiores, boca "O"
        pass
```

---

## 🐛 Troubleshooting

### Erro: "edge-tts não instalado"

```bash
pip install edge-tts
```

### Erro: "Ollama não responde"

Verifique se o Ollama está rodando:

```bash
ollama list
ollama run llama3.2
```

### Erro: "FFmpeg não encontrado"

Verifique se o FFmpeg está no PATH:

```bash
ffmpeg -version
```

### Intro não aparece nos vídeos

1. Verifique se `adicionar_intro_clippy=True` está ativo
2. Verifique logs no console para erros
3. Teste standalone: `python personagem_clippy.py`

### Voz muito rápida/lenta

Ajuste o parâmetro `--rate` em `sintetizar_voz_hook()`:

```python
'--rate', '+15%',  # +15% = mais rápido | -15% = mais lento
```

---

## 📊 Desempenho

### Tempo de Processamento

Por clip (aprox.):
- Geração de hook (Ollama): ~2-5 segundos
- Síntese de voz (edge-tts): ~1-2 segundos
- Criação da intro (FFmpeg): ~3-5 segundos
- Concatenação: ~1-2 segundos

**Total: ~7-14 segundos adicionais por clip**

### Otimizações Futuras

1. **Cache de hooks**: Reusar hooks similares para temas parecidos
2. **Pre-render Clippy**: Ter vídeos pré-renderizados do Clippy
3. **Processamento paralelo**: Gerar hooks enquanto edita o vídeo
4. **TTS local**: Usar modelo local (piper-tts) para maior velocidade

---

## 🎯 Exemplos de Resultados

### Antes (sem Clippy)
```
[Vídeo começa direto no conteúdo]
```

### Depois (com Clippy)
```
[0-4s] Intro Clippy: "Espera até veres isto!" 
[4s+] Conteúdo principal do vídeo
```

### Métricas de Engajamento Esperadas

Com base em estudos de hooks em vídeos curtos:
- ✅ +15-30% retenção nos primeiros 3 segundos
- ✅ +10-20% taxa de visualização completa
- ✅ +20-40% engajamento (likes/comentários)

---

## 📝 Notas Técnicas

### Formato dos Arquivos

- **Imagem Clippy**: PNG com alpha (transparência)
- **Áudio hook**: MP3, 128kbps, mono
- **Intro final**: MP4, 1080x1920 (vertical), H.264

### Compatibilidade

- ✅ Windows, Linux, macOS
- ✅ Python 3.8+
- ✅ FFmpeg 4.0+
- ✅ GPU (NVIDIA) opcional para encoding mais rápido

---

## 🔮 Roadmap Futuro

- [ ] Múltiplas expressões do Clippy (feliz, surpreso, pensativo)
- [ ] Animações (piscar, movimento)
- [ ] Vozes personalizáveis pelo usuário
- [ ] Hooks A/B testing (gerar múltiplas versões)
- [ ] Integração com métricas de engajamento
- [ ] Personagem customizável (cores, forma, acessórios)
- [ ] Suporte para outros idiomas
- [ ] API REST para geração de hooks

---

## 📄 Licença

Este módulo faz parte do projeto ClipAI e segue a mesma licença.

---

## 🤝 Contribuições

Para melhorias ou sugestões:
1. Teste a funcionalidade
2. Reporte bugs ou ideias
3. Envie pull requests

---

**Desenvolvido com ❤️ para aumentar o engajamento dos seus vídeos!**
