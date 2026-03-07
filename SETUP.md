# 🚀 SETUP - Clipadora AI (100% Gratuita)

Esta é a guia de instalação e configuração da Clipadora AI.

---

## ✅ O que já está instalado:

- ✅ Python (você tem)
- ✅ VS Code (você tem)
- ✅ FFmpeg (instalado via yt-dlp)
- ✅ yt-dlp (para download de vídeos)
- ✅ Faster-Whisper (para transcrição gratuita)
- ✅ MoviePy (para edição de vídeo)
- ✅ Ollama (Python client)

---

## 🆕 NOVA FUNCIONALIDADE: Personagem Clippy com IA

A **Clipadora AI** agora inclui uma personagem AI (clipe de papel com olhos) que:
- 🎯 Aparece no início de cada vídeo com um hook viral
- 🤖 Gera hooks automáticos usando IA (Ollama)
- 🔊 Fala com voz natural (Microsoft Edge TTS)

**Para usar esta funcionalidade, instale as dependências:**

```bash
pip install edge-tts Pillow
```

📖 **Documentação completa**: Veja [CLIPPY_README.md](CLIPPY_README.md)

---

## ⚠️ O que AINDA precisa fazer:

### Passo 1: Instalar o Ollama (CRÍTICO)

O **Ollama** é o programa que roda os modelos de IA localmente. Sem ele, o script não funciona.

1. Vá para: **https://ollama.ai**
2. Clique no botão para **Windows** e baixe o arquivo `.exe`
3. Execute o instalador e siga as instruções
4. Quando terminar, o Ollama estará rodando automaticamente em background

### Passo 2: Baixar o modelo Llama 2 (Importante)

Abra um **Prompt de Comando (cmd.exe)** ou **PowerShell** e DEIXE RODANDO este comando:

```bash
ollama pull llama2
```

Isso vai baixar o modelo Llama 2 (~4GB). Pode levar 5-10 minutos dependendo da sua internet.

Quando terminar, você verá:
```
pulling manifest
pulling 3f1d7b63c4fe...
✓ Done
```

**NÃO FECHE ESTE TERMINAL!** Deixe ele rodando em background ou deixa aberto mesmo.

### Passo 3: Ativar o Ollama

O Ollama agora está rodando como um serviço em background. Você pode verificar se está tudo certo digitando (em outro terminal):

```bash
ollama list
```

Você deve ver algo como:
```
NAME             ID              SIZE      MODIFIED
llama2:latest    abc123...       4.2GB     2 hours ago
```

⚠️ **IMPORTANTE**: Antes de executar `python main.py`, **certifique-se de que o Ollama está rodando!**

Para iniciar o Ollama:
- **Opção 1**: Abra o **Ollama Desktop** (aplicativo - você verá na barra de tarefas)
- **Opção 2**: Abra um terminal e digite: `ollama serve`

Se não fizer isso, o script vai retornar erro "Ollama não está rodando".

---

## 🚀 Agora está pronto para testar!

Abra o VS Code e execute:

```powershell
python main.py
```

O script vai:
1. ✅ Baixar um vídeo do YouTube
2. ✅ Extrair o áudio
3. ✅ Transcrever com Faster-Whisper (pode levar 2-5 min)
4. ✅ Analisar com Llama 2 (pode levar 2-3 min)
5. ✅ Salvar as recomendações de clipes

---

## 💰 Custos

**ZERO REAIS!** 🎉

Tudo roda no seu computador:
- Faster-Whisper = Gratuito (open-source)
- Llama 2 = Gratuito (open-source)
- yt-dlp = Gratuito (open-source)
- MoviePy = Gratuito (open-source)

Você até economiza usando esse setup do que usando APIs pagas!

---

## ⚡ (OPCIONAL) Aceleração com GPU (CUDA)

Quer transcrever vídeos **10x mais rápido**? Use sua GPU NVIDIA!

### Verificar se você tem GPU NVIDIA

1. Abra VS Code e execute:
   ```powershell
   python verificar_gpu.py
   ```

2. Você verá algo como:
   ```
   ✅ CUDA está DISPONÍVEL
   GPU 0:
      Nome: NVIDIA GeForce RTX 4090
      Status: ✅ Funcionando
   ```

Se vir **❌ CUDA NÃO está disponível**, continue os passos abaixo.

### Passo 1: Baixar e Instalar CUDA Toolkit

1. Vá para: **https://developer.nvidia.com/cuda-toolkit**
2. Clique em **"Download Now"**
3. Escolha: **Windows** → **x86_64** → **exe (local)**
4. Baixe e execute o instalador
5. Siga as instruções (pode deixar tudo no padrão)
6. **Reinicie o computador**

### Passo 2: Baixar e Instalar cuDNN

O cuDNN melhora a performance de ML ainda mais:

1. Vá para: **https://developer.nvidia.com/cudnn**
2. Faça login (crie uma conta se precisar)
3. Baixe a versão mais recente para **Windows x86_64**
4. Descompacte o arquivo
5. Copie os arquivos para sua pasta CUDA:
   - `cuda/bin/*` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\bin`
   - `cuda/lib/*` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\lib`
   - `cuda/include/*` → `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\include`

### Passo 3: Verificar Instalação

```powershell
nvcc --version
```

Você deve ver algo como:
```
nvcc: NVIDIA (R) Cuda compiler driver
Cuda compilation tools, release 12.1
```

### Passo 4: Testar Performance

Execute:
```powershell
python verificar_gpu.py
```

Se tudo estiver certo, você verá ✅ em tudo!

---

## ⏱️ Comparação de Performance

| Task | CPU | GPU (RTX 3090) | Speedup |
|------|-----|---|---|
| Transcrição 10 min | 3-5 min | 20-60 seg | **5-15x** ⚡ |
| Análise (Llama) | 2-3 min | 30-60 seg | **5-6x** ⚡ |
| **Total** | **5-8 min** | **1-2 min** | **5-8x** ⚡ |

---

💡 **Dica**: Se você não tem GPU NVIDIA, a versão CPU funciona perfeitamente! Apenas um pouco mais lenta.

---

## 🆘 Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'ollama'"
✅ Solução: Você já tem instalado. Verifique se o Ollama desktop está realmente rodando.

### Erro: "Connection refused" ou "OLLAMA_HOST"
⚠️ Significa que o Ollama não está rodando:
1. Abra o **Ollama Desktop** (veja na sua barra de tarefas/aplicações)
2. Ou abra um terminal e digite: `ollama serve`

### Erro: "model 'llama2' not found"
⚠️ Significa que não baixou o modelo:
1. Abra um terminal
2. Digite: `ollama pull llama2`
3. Espere terminar

---

## 📁 Estrutura do Projeto

```
ClipAI/
├── downloads/              # Vídeos baixados aqui
├── .env                    # Configurações (sem API keys!)
├── main.py                 # Script principal
├── modulo1_download.py     # Baixa vídeos do YouTube
├── modulo2_analise.py      # Transcreve + Analisa com IA
├── modulo3_edicao.py       # (Próximo) Corta e edita vídeos
├── modulo4_publicacao.py   # (Próximo) Publica em redes
├── verificar_gpu.py        # Diagnostica GPU/CUDA (execute: python verificar_gpu.py)
├── SETUP.md                # Este arquivo
└── README.md               # (Próximo) Documentação completa
```

---

Pronto! Agora você tem tudo configurado! 🚀
