# 🚀 Instalação Rápida - Funcionalidade Clippy

Guia rápido para instalar e configurar a personagem Clippy no seu ClipAI.

---

## ⚡ Instalação em 3 Passos

### Passo 1: Instalar Dependências Python

```bash
pip install edge-tts Pillow
```

Ou instale todas as dependências do projeto:

```bash
pip install -r requirements.txt
```

### Passo 2: Verificar Ollama

O Ollama deve estar instalado e rodando (já é pré-requisito do ClipAI).

```bash
# Verificar se está instalado
ollama list

# Se não estiver, baixe o modelo
ollama pull llama3.2
```

### Passo 3: Testar a Instalação

```bash
python test_clippy.py
```

Se todos os testes passarem: **✅ Pronto para usar!**

---

## 📝 Verificação Detalhada

### 1. Verificar Edge TTS

```bash
edge-tts --list-voices | grep pt-
```

Você deve ver vozes portuguesas listadas:
- `pt-BR-FranciscaNeural`
- `pt-BR-AntonioNeural`
- `pt-PT-RaquelNeural`
- `pt-PT-DuarteNeural`

### 2. Testar Edge TTS

```bash
edge-tts --text "Olá, eu sou a Clippy!" --voice pt-BR-FranciscaNeural --write-media teste.mp3
```

Isso cria `teste.mp3`. Abra e ouça para verificar.

### 3. Verificar Pillow

```bash
python -c "from PIL import Image; print('Pillow OK')"
```

Deve imprimir: `Pillow OK`

### 4. Verificar Ollama

```bash
ollama run llama3.2 "Olá, gera uma frase curta e viral para um vídeo sobre produtividade"
```

Deve retornar uma resposta da IA.

---

## 🐛 Troubleshooting

### Erro: "edge-tts: command not found"

**Windows:**
```bash
pip install --upgrade edge-tts
```

Depois reinicie o terminal.

Se ainda não funcionar, localize onde o pip instalou:
```bash
pip show edge-tts
```

E adicione o caminho ao PATH do sistema.

**Linux/Mac:**
```bash
pip3 install edge-tts
```

### Erro: "No module named 'PIL'"

```bash
pip install Pillow
```

Se falhar:
```bash
pip install --upgrade Pillow
```

### Erro: "Ollama não responde"

1. Verifique se o Ollama está rodando:
   ```bash
   ollama serve
   ```

2. Em outro terminal, teste:
   ```bash
   ollama list
   ```

3. Se não estiver instalado, vá para:
   **https://ollama.ai**

### Erro: "FFmpeg não encontrado"

O Clippy usa FFmpeg para processar vídeo/áudio.

**Windows:**
```bash
# Baixe FFmpeg de: https://ffmpeg.org/download.html
# Extraia e adicione ao PATH
```

Ou use o script do projeto:
```bash
python download_models.py  # Se existir
```

**Linux:**
```bash
sudo apt install ffmpeg
```

**Mac:**
```bash
brew install ffmpeg
```

### Erro: "ConnectionError" ou "Timeout"

1. Verifique sua conexão com internet (edge-tts precisa conectar inicialmente)
2. Se estiver atrás de proxy/firewall, configure:
   ```bash
   # Windows
   set HTTP_PROXY=http://seu-proxy:porta
   set HTTPS_PROXY=http://seu-proxy:porta
   
   # Linux/Mac
   export HTTP_PROXY=http://seu-proxy:porta
   export HTTPS_PROXY=http://seu-proxy:porta
   ```

### Erro: "Intro Clippy não aparece nos vídeos"

1. Verifique se está ativado em `modulo3_edicao.py`:
   ```python
   adicionar_intro_clippy=True  # Deve estar True
   ```

2. Execute o teste standalone:
   ```bash
   python test_clippy.py
   ```

3. Verifique os logs no console durante o processamento
   - Deve aparecer: "🤖 Criando intro com personagem Clippy (AI)..."

4. Verifique se os arquivos temporários estão sendo criados em `data/`:
   - `clippy_personagem.png`
   - `clippy_voz_temp.mp3`

### Erro: "Voice not found" ou voz robótica

1. Liste as vozes disponíveis:
   ```bash
   edge-tts --list-voices
   ```

2. Escolha uma voz PT e edite `personagem_clippy.py`:
   ```python
   voz = "pt-BR-FranciscaNeural"  # Troque aqui
   ```

### Performance: Intro demora muito

**Otimizações:**

1. **Use GPU** (se disponível):
   - Verifique: `python -c "import torch; print(torch.cuda.is_available())"`
   - FFmpeg usará automaticamente GPU NVIDIA

2. **Reduza qualidade** (se necessário):
   Em `personagem_clippy.py`, na função `criar_intro_clippy()`:
   ```python
   # Troque CRF 18 por CRF 23 (menor qualidade, mais rápido)
   '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
   ```

3. **Cache de intros**:
   Se processar muitos vídeos similares, considere reusar intros.

---

## ✅ Checklist de Instalação

- [ ] edge-tts instalado (`pip install edge-tts`)
- [ ] Pillow instalado (`pip install Pillow`)
- [ ] FFmpeg no PATH (`ffmpeg -version`)
- [ ] Ollama rodando (`ollama list`)
- [ ] Modelo Llama 3.2 baixado (`ollama pull llama3.2`)
- [ ] Teste passou (`python test_clippy.py`)

---

## 🎯 Próximos Passos

Após instalação bem-sucedida:

1. **Processar um vídeo de teste:**
   ```bash
   python main.py
   ```

2. **Verificar o resultado:**
   - Vídeos em: `downloads/clips_editados/`
   - Procure por arquivos `*_final.mp4`
   - Abra e veja a intro do Clippy!

3. **Personalizar:**
   - Voz: Edite `personagem_clippy.py`
   - Aparência: Edite `criar_personagem_clippy()`
   - Duração intro: Edite `modulo3_edicao.py`

4. **Ler documentação completa:**
   - [CLIPPY_README.md](CLIPPY_README.md)
   - [exemplos_clippy.py](exemplos_clippy.py)

---

## 💬 Suporte

Se encontrar problemas não listados aqui:

1. Execute o teste com debug:
   ```bash
   python test_clippy.py
   ```

2. Verifique os logs no console

3. Procure por mensagens de erro específicas

4. Procure no README ou documentação

---

**Pronto! Agora seus vídeos terão hooks virais com a personagem Clippy! 🎉**
