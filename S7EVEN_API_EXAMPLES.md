# S7even AI — Cheat Sheet de API

Colecção de exemplos prontos-a-usar para testar a API S7even.

## 🔗 Base URL

```
http://localhost:5000
```

⚠️ Nota: Substitui `localhost:5000` pelo teu domínio/IP se estiver noutro servidor.

---

## 1️⃣ CRIAR VÍDEO S7EVEN

### Exemplo 1A: Criar com tema específico

```bash
curl -X POST http://localhost:5000/api/s7even \
  -H "Content-Type: application/json" \
  -d '{
    "tema_preferido": "crime bizarro",
    "channel_id": null,
    "auto_publish": false
  }'
```

**Resposta (sucesso):**
```json
{
  "sucesso": true,
  "video": {
    "titulo": "O Passaporte do País Fantasma",
    "arquivo_spec": "downloads/s7even_video_spec.json",
    "blocos_totais": 5,
    "tempo_criacao": "2025-03-08T15:30:45.123456"
  },
  "queue_item_id": "89a2b3c4-d5e6-7f8g-9h0i-j1k2l3m4n5o6",
  "queue_item": { ... },
  "mensagem": "Vídeo S7even 'O Passaporte do País Fantasma' criado e adicionado à queue!"
}
```

### Exemplo 1B: Tema aleatório

```bash
curl -X POST http://localhost:5000/api/s7even \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Exemplo 1C: Com ElevenLabs (narração premium)

Primeiro, configura em `.env` ou PowerShell:

```powershell
# PowerShell (Windows)
$env:ELEVENLABS_API_KEY = "sk_abcd1234efgh5678..."
$env:ELEVENLABS_VOICE_ID = "Antoni"

# Bash/Linux
export ELEVENLABS_API_KEY="sk_abcd1234efgh5678..."
export ELEVENLABS_VOICE_ID="Antoni"
```

Depois:

```bash
curl -X POST http://localhost:5000/api/s7even \
  -H "Content-Type: application/json" \
  -d '{
    "tema_preferido": "mistério histórico",
    "usar_elevenlabs": true,
    "auto_publish": false
  }'
```

### Exemplo 1D: Com auto-publicação num canal

```bash
curl -X POST http://localhost:5000/api/s7even \
  -H "Content-Type: application/json" \
  -d '{
    "tema_preferido": "anomalia paranormal",
    "channel_id": "seu-channel-id-aqui",
    "auto_publish": true,
    "usar_elevenlabs": false
  }'
```

### Exemplo 1E: Resposta com erro

```bash
# Se Ollama não está a rodar, por exemplo:
curl -X POST http://localhost:5000/api/s7even \
  -H "Content-Type: application/json" \
  -d '{"tema_preferido": "teste"}'

# Resposta:
{
  "sucesso": false,
  "erro": "Conexão recusada à Ollama (porta 11434)",
  "timestamp": "2025-03-08T15:31:00.000000"
}
```

---

## 2️⃣ LISTAR VÍDEOS S7EVEN

### Exemplo 2A: Listar todos

```bash
curl -X GET http://localhost:5000/api/s7even
```

**Resposta:**
```json
{
  "sucesso": true,
  "total": 3,
  "videos": [
    {
      "id": "89a2b3c4-d5e6-...",
      "title": "[S7even] O Passaporte do País Fantasma",
      "url": "s7even://downloads/s7even_video_spec.json",
      "status": "queued",
      "content_type": "s7even",
      "progress": 0,
      "created_at": "2025-03-08T15:30:45"
    },
    ...
  ]
}
```

---

## 3️⃣ OBTER DETALHES DE UM VÍDEO

### Exemplo 3A: Ver detalhes completos

```bash
curl -X GET http://localhost:5000/api/s7even/89a2b3c4-d5e6-7f8g-9h0i-j1k2l3m4n5o6
```

**Resposta:**
```json
{
  "sucesso": true,
  "video": {
    "id": "89a2b3c4-d5e6-...",
    "title": "[S7even] O Passaporte do País Fantasma",
    "url": "s7even://downloads/s7even_video_spec.json",
    "status": "queued",
    "progress": 0,
    "s7even_spec_file": "downloads/s7even_video_spec.json",
    ...
  },
  "historia": {
    "titulo": "O Passaporte do País Fantasma",
    "resumo": "Em 1954, um homem apareceu num aeroporto com um passaporte de um país que não existe.",
    "personagens_principais": ["John Zegrus"],
    "data_evento": "1954-07-20",
    "local": "Aeroporto de Bruxelas",
    "fatos_chocantes": [
      "Passaporte de 'Taured' — país que não existe",
      "Homem calmo e convincente, conhecido em Taured",
      "Desapareceu da quarto de hotel antes de investigação"
    ]
  }
}
```

---

## 4️⃣ PUBLICAR VÍDEO S7EVEN

### Exemplo 4A: Marcar para publicação num canal

```bash
curl -X POST http://localhost:5000/api/s7even/89a2b3c4-d5e6-7f8g-9h0i-j1k2l3m4n5o6/publish \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "seu-channel-id",
    "auto_publish": true
  }'
```

**Resposta:**
```json
{
  "sucesso": true,
  "mensagem": "Vídeo marcado para processamento e publicação",
  "item": {
    "id": "89a2b3c4-d5e6-...",
    "status": "queued",
    "auto_publish": true,
    "channel_id": "seu-channel-id"
  }
}
```

### Exemplo 4B: Publicar sem auto-publish (manual)

```bash
curl -X POST http://localhost:5000/api/s7even/89a2b3c4-d5e6-7f8g-9h0i-j1k2l3m4n5o6/publish \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "seu-channel-id",
    "auto_publish": false
  }'
```

---

## 🔗 COMBINAÇÕES ÚTEIS (SCRIPTS)

### Script 1: Criar 5 vídeos em lote

```bash
#!/bin/bash

# Cria 5 vídeos S7even com temas diferentes
TEMAS=(
  "crime bizarro"
  "mistério histórico"
  "anomalia paranormal"
  "descoberta científica assustadora"
  "desaparecimento inexplicável"
)

echo "🎬 Criando 5 vídeos S7even..."

for tema in "${TEMAS[@]}"; do
  echo "📝 Criando: $tema"
  
  curl -X POST http://localhost:5000/api/s7even \
    -H "Content-Type: application/json" \
    -d "{
      \"tema_preferido\": \"$tema\",
      \"auto_publish\": false
    }" | jq '.queue_item_id'
  
  echo "✅ Criado!"
  sleep 2  # aguarda 2s entre criações
done

echo "✅ Todos os vídeos criados!"
```

Uso:
```bash
chmod +x create_s7even_batch.sh
./create_s7even_batch.sh
```

### Script 2: Monitorizar status

```bash
#!/bin/bash

# Verifica status de todos os vídeos S7even a cada 5s

echo "🔄 Monitorizado S7even videos..."

while true; do
  clear
  echo "═══════════════════════════════════════"
  echo "  S7EVEN VIDEOS — STATUS EM TEMPO REAL"
  echo "═══════════════════════════════════════"
  echo ""
  
  curl -s -X GET http://localhost:5000/api/s7even | jq '
    .videos |
    map(
      select(.content_type == "s7even") |
      "[\(.status | ascii_upcase)] \(.title) (\(.progress)%)"
    ) |
    .[]
  '
  
  echo ""
  echo "Actualizado: $(date +'%H:%M:%S')"
  echo ""
  echo "Pressiona Ctrl+C para parar"
  
  sleep 5
done
```

### Script 3: Publicar vídeos automaticamente

```bash
#!/bin/bash

# Publica todos os vídeos S7even em fila

CHANNEL_ID="seu-channel-id"

echo "📤 Publicando vídeos S7even..."

curl -s http://localhost:5000/api/s7even | jq -r '.videos[].id' | while read VIDEO_ID; do
  echo "Publicando: $VIDEO_ID"
  
  curl -X POST http://localhost:5000/api/s7even/$VIDEO_ID/publish \
    -H "Content-Type: application/json" \
    -d "{
      \"channel_id\": \"$CHANNEL_ID\",
      \"auto_publish\": true
    }"
  
  echo "✅ Publicado!"
  sleep 1
done

echo "✅ Todos os vídeos foram publicados!"
```

---

## 🧪 TESTES COM JAVASCRIPT (Fetch API)

### Exemplo: Criar vídeo (no console do browser)

```javascript
// Abre DevTools (F12) → Console

fetch('http://localhost:5000/api/s7even', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    tema_preferido: 'crime bizarro',
    auto_publish: false
  })
})
.then(res => res.json())
.then(data => {
  console.log('✅ Vídeo criado!');
  console.log('ID:', data.queue_item_id);
  console.log('Título:', data.video.titulo);
  console.log('Spec:', data.video.arquivo_spec);
})
.catch(err => console.error('Erro:', err));
```

### Exemplo: Listar vídeos (JavaScript)

```javascript
fetch('http://localhost:5000/api/s7even')
  .then(res => res.json())
  .then(data => {
    console.table(data.videos.map(v => ({
      ID: v.id.slice(0, 8) + '...',
      Título: v.title,
      Status: v.status,
      Progresso: v.progress + '%'
    })));
  });
```

---

## 🔍 DEBUGGING & TROUBLESHOOTING

### Verificar se servidor está online

```bash
curl -I http://localhost:5000/
# Response: HTTP/1.0 200 OK
```

### Ver logs do servidor

```bash
# No terminal onde está a rodar o servidor:
tail -f output.log  # ou acompanha no próprio terminal
```

### Testar conexão a Ollama

```bash
# Ollama deve estar a rodar:
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1",
    "prompt": "Olá",
    "stream": false
  }'
```

### Verificar credenciais de API (ElevenLabs)

```bash
curl -X GET https://api.elevenlabs.io/v1/voices \
  -H "xi-api-key: sk_seu_token"
```

---

## 📋 REFERÊNCIA RÁPIDA

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/s7even` | POST | Criar novo vídeo |
| `/api/s7even` | GET | Listar vídeos |
| `/api/s7even/<id>` | GET | Detalhes de um vídeo |
| `/api/s7even/<id>/publish` | POST | Marcar para publicação |

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `tema_preferido` | string | aleatório | crime, mistério, anomalia, etc. |
| `channel_id` | string | null | ID do canal YouTube |
| `auto_publish` | boolean | false | Publicar automaticamente? |
| `usar_elevenlabs` | boolean | false | Usar narração premium? |
| `gerar_imagens_midjourney` | boolean | false | Gerar imagens custom? |

---

## 📚 Ver Mais

- `S7EVEN_AI.md` — Documentação completa
- `test_s7even_ai.py` — Testes e exemplos
- `s7even_ai.py` — Código-fonte comentado

---

**Happy API Hacking!** 🚀
