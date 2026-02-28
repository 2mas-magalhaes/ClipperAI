# 🎬 ClipAI - Sistema Automático de Clipagem de Vídeos

Uma solução **100% gratuita** e **open-source** para criar clips virais automaticamente a partir de vídeos do YouTube usando IA.

---

## ✨ Recursos

- ✅ **Download automático** de vídeos do YouTube
- ✅ **Transcrição de áudio** com Whisper (offline)
- ✅ **Análise inteligente** com Llama 2 (offline)
- ✅ **Zero custos** - Tudo roda localmente
- ✅ **Aceleração GPU** - 10x mais rápido com NVIDIA CUDA

---

## 🚀 Início Rápido

### 1. Instalar Ollama (Obrigatório)

```bash
# Vá para https://ollama.ai e baixe o instalador Windows
# Depois baixe o modelo Llama 2
ollama pull llama2
```

### 2. Executar o Sistema

```powershell
python main.py
```

### 3. (Opcional) Ativar GPU para 10x de velocidade

```powershell
python verificar_gpu.py
```

Se não tiver GPU, tudo roda normalmente na CPU!

---

## 📊 Performance

| Recurso | CPU | GPU RTX 3090 |
|---------|-----|---|
| Transcrição 10 min | 3-5 min | 20-60 seg |
| Análise IA | 2-3 min | 30-60 seg |
| **Total** | **5-8 min** | **1-2 min** |

---

## 🏗️ Arquitetura

O sistema é dividido em **5 módulos**:

### Módulo 1️⃣ - Download (`modulo1_download.py`)
- Baixa vídeos do YouTube com `yt-dlp`
- Salva em formato MP4 na melhor qualidade

### Módulo 2️⃣ - Análise (`modulo2_analise.py`)
1. **Extrai áudio** do vídeo com MoviePy
2. **Transcreve** com Faster-Whisper (offline)
3. **Analisa** com Llama 2 (offline)
4. **Identifica** os 3-5 melhores clipes

### Módulo 3️⃣ - Edição (`modulo3_edicao.py`) - *Em desenvolvimento*
- Corta vídeo nos momentos recomendados
- Adiciona legendas animadas
- Converte para formato vertical (9:16)
- Aplica efeitos visuais

### Módulo 4️⃣ - Publicação (`modulo4_publicacao.py`) - *Em desenvolvimento*
- Publica no YouTube Shorts
- Publica no TikTok
- Publica no Instagram Reels

### Módulo 5️⃣ - Aprendizado (`modulo5_feedback.py`) - *Em desenvolvimento*
- Coleta métricas de visualizações
- Treina modelo com padrões de sucesso
- Melhora recomendações ao longo do tempo

---

## 📋 Requisitos

- Python 3.9+
- ~4GB de RAM mínimo (8GB+ recomendado)
- Conexão com internet (para download)
- GPU NVIDIA (opcional, mas recomendado)

---

## 🛠️ Instalação Completa

Veja [SETUP.md](SETUP.md) para:
- ✅ Instalação passo a passo
- ✅ Troubleshooting
- ✅ Configuração de GPU/CUDA
- ✅ Estrutura de pastas

---

## 💻 Tecnologias Utilizadas

| Componente | Tecnologia | Custo |
|---|---|---|
| Download | yt-dlp | Gratuito |
| Transcrição | Faster-Whisper | Gratuito |
| IA (Análise) | Llama 2 via Ollama | Gratuito |
| Edição de Vídeo | FFmpeg + MoviePy | Gratuito |
| Aceleração | PyTorch + CUDA | Gratuito |

---

## 📖 Exemplos de Uso

### Exemplo 1: Analisar um podcast

```python
from modulo1_download import baixar_video_youtube
from modulo2_analise import extrair_audio_do_video, transcrever_audio_whisper, analisar_com_ollama

url = "https://www.youtube.com/watch?v=seu_podcast"
video = baixar_video_youtube(url, "podcast")
audio = extrair_audio_do_video(video)
transcricao = transcrever_audio_whisper(audio)
clipes = analisar_com_ollama(transcricao)
```

### Exemplo 2: Verificar GPU

```bash
python verificar_gpu.py
```

---

## 🤝 Contribuindo

Este projeto é open-source! Contribuições são bem-vindas:

1. Implemente o Módulo 3 (Edição automática)
2. Implemente o Módulo 4 (Publicação)
3. Implemente o Módulo 5 (Aprendizado)
4. Abra um Pull Request!

---

## ⚠️ Avisos Legais

### Copyright
Respeite os direitos autorais dos vídeos! Simply remixing without modification pode resultar em:
- Banimento de canais
- Copyright strikes do YouTube
- Processos legais

**Solução**: O Módulo 3 adiciona:
- Legendas dinâmicas
- Efeitos visuais
- Música de fundo livre de direitos
- Transformações de conteúdo

Isso torna o conteúdo "derivado" e legalmente protegido.

### Termos de Serviço
Cumpra com os ToS do:
- ✅ YouTube
- ✅ TikTok
- ✅ Instagram

---

## 📞 Suporte

Precisa de ajuda?

1. Veja [SETUP.md](SETUP.md) para erros comuns
2. Execute `python verificar_gpu.py` para diagnosticar
3. Verifique se Ollama está rodando: `ollama serve`

---

## 📊 Roadmap

- [ ] Módulo 3: Edição automática de vídeos
- [ ] Módulo 4: Publicação em redes sociais
- [ ] Módulo 5: Sistema de feedback e aprendizado
- [ ] Interface web (Flask/Django)
- [ ] Suporte para mais modelos de IA
- [ ] Agendamento automático
- [ ] Dashboard de analytics

---

## 📄 Licença

MIT License - Veja LICENSE.md para detalhes

---

**Desenvolvido com ❤️ para criadores de conteúdo**

Criando um futuro onde a criação de conteúdo é acessível a todos. 🚀
