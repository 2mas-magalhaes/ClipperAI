# 🤖 AutoManager - Gestão Automática do ClipAI

## O que faz?

O **AutoManager** é um sistema que automatiza completamente o ClipAI:

1. **🗑️ Limpeza Automática**: Remove vídeos antigos processados quando o limite de armazenamento é atingido
2. **📥 Download Automático**: Baixa novos vídeos de uma playlist do YouTube continuamente
3. **♻️ Processamento Contínuo**: Mantém a queue sempre alimentada com novos vídeos

## Como Usar?

### Opção 1: Interface Web ✨ (Recomendado)

1. Inicie o servidor: `python app.py`
2. Abra http://localhost:5000
3. Vá em "Definições" → "Gestão Automática"
4. Configure:
   - ✅ Ativar gestão automática
   - 📺 URL da Playlist (ex: playlists "oddly satisfying", gameplay, cooking)
   - 💾 Limite de armazenamento (padrão: 5GB)
   - ⏱️ Intervalo de verificação (padrão: 15 minutos)
5. Clique em "Guardar e Ativar"

### Opção 2: Script Rápido 🚀

1. Edite o arquivo `config_playlist.py` e coloque a URL da sua playlist
2. Execute: `python config_playlist.py`
3. Inicie o servidor: `python app.py`

## Exemplo de Playlists

- **Oddly Satisfying**: https://www.youtube.com/playlist?list=PLzvRQMJ9HDiSH0UWS9Y3Q9TvCkY_e_EYq
- **Satisfying Videos**: https://www.youtube.com/playlist?list=PLSYrP90Ou9s3tXe28YvOv1cDXRmw5P5HR
- **Minecraft**: https://www.youtube.com/playlist?list=...
- **Cooking**: https://www.youtube.com/playlist?list=...

## Como Funciona?

1. **Verificação Periódica**: A cada X minutos (configurável), o sistema verifica:
   - Tamanho total dos vídeos no disco
   - Quantos vídeos estão na fila
   - Se há novos vídeos na playlist

2. **Limpeza Inteligente**:
   - Se o limite de armazenamento for atingido
   - Remove vídeos mais antigos que já foram processados (status: done/error)
   - Libera espaço até 80% do limite

3. **Download Automático**:
   - Mantém até 3 vídeos na fila
   - Filtra vídeos de 1-20 minutos
   - Ignora vídeos já processados
   - Adiciona até 5 novos vídeos por verificação

## Logs

Os logs do AutoManager aparecem no terminal onde o servidor está rodando:

```
🤖 AutoManager iniciado (limpeza + playlist automática)
   📺 Playlist: https://www.youtube.com/...
💾 Espaço OK: 2341.2MB / 5000MB
🔍 Verificando playlist para novos vídeos...
   ➕ Adicionado: Amazing Satisfying Video #1
   ➕ Adicionado: Satisfying Slime ASMR
✅ 2 novos vídeos adicionados à queue
```

## Vantagens

✅ **Totalmente Automático**: Configure uma vez e deixe rodando  
✅ **Economia de Espaço**: Limpeza automática mantém o disco organizado  
✅ **Processamento 24/7**: Continua baixando e processando vídeos infinitamente  
✅ **Sem Supervisão**: Perfeito para criar um pipeline contínuo de shorts

## Notas

- O Worker precisa estar ativo para processar os vídeos automaticamente
- Certifique-se de ter espaço suficiente em disco antes de configurar
- Recomenda-se usar playlists com vídeos de 1-20 minutos para melhores resultados
- Vídeos processados com sucesso serão movidos para a seção "Revisão" ou "Publicados"

---

**Pronto! Agora seu ClipAI roda no piloto automático! 🚀**
