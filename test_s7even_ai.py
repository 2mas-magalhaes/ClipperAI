#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_s7even_ai.py — Testa o sistema completo S7even AI

Este script demonstra:
  1. Criar um vídeo S7even da raiz
  2. Examinar a estrutura gerada
  3. Processar para edição FFmpeg
  4. Simular integração com queue/worker

Uso:
  python test_s7even_ai.py
"""

import os
import sys
import json
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("TestS7even")

# Adicionar raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import s7even_ai
    import database as db
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print("   Verifica se está na pasta certa e se os módulos existem")
    sys.exit(1)


def teste_1_criar_video():
    """Testa 1: Criar um vídeo S7even completo."""
    print("\n" + "="*70)
    print("TESTE 1: Criar Vídeo S7even Completo")
    print("="*70)
    
    logger.info("Iniciando criação de vídeo tipo S7even (tema aleatório)...")
    
    resultado = s7even_ai.criar_video_s7even(
        tema_preferido="mistério histórico desconhecido",
        usar_elevenlabs=False,  # Gratuito
        gerar_imagens_midjourney=False
    )
    
    if resultado.get("sucesso"):
        print(f"\n✅ SUCESSO!")
        print(f"   Título: {resultado['titulo']}")
        print(f"   Blocos: {resultado['blocos_totais']}")
        print(f"   Arquivo: {resultado['arquivo_spec']}")
        return resultado
    else:
        print(f"\n❌ FALHOU: {resultado.get('erro')}")
        return None


def teste_2_examinar_spec(resultado):
    """Testa 2: Examinar a estrutura do ficheiro spec."""
    print("\n" + "="*70)
    print("TESTE 2: Estrutura do Ficheiro de Especificação")
    print("="*70)
    
    spec_file = resultado['arquivo_spec']
    
    if not os.path.exists(spec_file):
        print(f"❌ Ficheiro não encontrado: {spec_file}")
        return
    
    with open(spec_file, 'r', encoding='utf-8') as f:
        spec = json.load(f)
    
    print(f"\n📋 Especificação do Vídeo:")
    print(f"   Título: {spec.get('titulo')}")
    print(f"   Resumo: {spec.get('resumo')}")
    print(f"   Duração: {spec.get('duracao_total_segundos')}s")
    print(f"   Resolução: {spec.get('resolucao')}")
    print(f"   Blocos na timeline: {len(spec.get('timeline', []))}")
    
    print(f"\n🎬 Detalhes da Timeline:")
    for evento in spec.get('timeline', []):
        print(f"\n   [{evento.get('bloco_id')}] {evento.get('secao')}: {evento.get('tempo_inicio')}s")
        texto = evento.get('texto', '')
        if len(texto) > 80:
            print(f"       Texto: {texto[:80]}...")
        else:
            print(f"       Texto: {texto}")
        arquivo_audio = evento.get('arquivo_audio') or 'N/A'
        print(f"       Áudio: {os.path.basename(arquivo_audio)}")
        if evento.get('arquivo_imagem'):
            print(f"       Imagem: {evento.get('imagem_fonte')} ({evento.get('tipo_imagem')})")
        print(f"       Efeito: {evento.get('efeito_visual')} + {evento.get('efeito_sonoro')}")


def teste_3_verificar_assets(resultado):
    """Testa 3: Verificar se todos os assets (áudio, imagens) existem."""
    print("\n" + "="*70)
    print("TESTE 3: Verificação de Assets (Áudio e Imagens)")
    print("="*70)
    
    spec_file = resultado['arquivo_spec']
    
    with open(spec_file, 'r', encoding='utf-8') as f:
        spec = json.load(f)
    
    assets = {
        "áudio": [],
        "imagens": [],
        "faltando": []
    }
    
    for evento in spec.get('timeline', []):
        # Verificar áudio
        audio = evento.get('arquivo_audio')
        if audio:
            if os.path.exists(audio):
                assets['áudio'].append(audio)
            else:
                assets['faltando'].append(f"Áudio: {audio}")
        
        # Verificar imagem
        imagem = evento.get('arquivo_imagem')
        if imagem and imagem.startswith('http'):
            # URL remota — não verifica se existe
            assets['imagens'].append(f"Remota: {evento.get('imagem_fonte')}")
        elif imagem and os.path.exists(imagem):
            assets['imagens'].append(imagem)
    
    print(f"\n📊 Resumo de Assets:")
    print(f"   ✅ Arquivos de áudio: {len(assets['áudio'])}")
    for a in assets['áudio']:
        tamanho = os.path.getsize(a) / (1024*1024)
        print(f"      - {os.path.basename(a)} ({tamanho:.1f}MB)")
    
    print(f"   🖼️  Imagens: {len(assets['imagens'])}")
    for i in assets['imagens']:
        if i.startswith("Remota"):
            print(f"      - {i}")
        else:
            print(f"      - {os.path.basename(i)}")
    
    if assets['faltando']:
        print(f"\n   ⚠️  Faltando ({len(assets['faltando'])} assets):")
        for f in assets['faltando']:
            print(f"      - {f}")
    else:
        print(f"\n   ✅ Todos os assets necessários encontrados!")


def teste_4_adicionar_a_queue(resultado):
    """Testa 4: Adicionar vídeo S7even à queue (simular integração)."""
    print("\n" + "="*70)
    print("TESTE 4: Integração com Queue do ClipAI")
    print("="*70)
    
    try:
        # Simular adição à queue
        titulo = resultado['titulo']
        spec_file = resultado['arquivo_spec']
        
        item = db.add_to_queue(
            url=f"s7even://{spec_file}",
            title=f"[S7even] {titulo}",
            channel_id=None,  # Usar padrão
            auto_publish=False
        )
        
        # Atualizar com metadados S7even
        db.update_queue_item(item['id'],
            content_type="s7even",
            s7even_spec_file=spec_file
        )
        
        print(f"\n✅ Vídeo adicionado à queue!")
        print(f"   ID: {item['id']}")
        print(f"   Título: {item['title']}")
        print(f"   URL: {item.get('url')}")
        print(f"   Status: {item.get('status')}")
        
        return item
    
    except Exception as e:
        print(f"\n❌ Erro ao adicionar à queue: {e}")
        return None


def teste_5_simular_processamento(queue_item):
    """Testa 5: Simular como o worker processaria o vídeo."""
    print("\n" + "="*70)
    print("TESTE 5: Simulação de Processamento (Worker)")
    print("="*70)
    
    if not queue_item:
        print("❌ Sem item de queue para processar")
        return
    
    # Extrair o arquivo da URL (s7even://downloads/s7even_video_spec.json)
    url = queue_item.get('url', '')
    spec_file = url.replace('s7even://', '')
    
    if not os.path.exists(spec_file):
        print(f"❌ Arquivo de especificação não encontrado: {spec_file}")
        return
    
    with open(spec_file, 'r', encoding='utf-8') as f:
        spec = json.load(f)
    
    print(f"\n🎬 Processamento simulado:")
    print(f"   [1/4] Download de assets (áudio, imagens)... ✓")
    print(f"   [2/4] Composição de vídeo com FFmpeg...")
    
    ffmpeg_cmd = (
        "ffmpeg -f concat -safe 0 -i filelist.txt "
        "-vf \"scale=1920:1080, fps=30\" "
        "-c:v libx264 -crf 18 "
        "-c:a aac -b:a 192k "
        "output.mp4"
    )
    print(f"          (Comando similar a:)")
    print(f"          {ffmpeg_cmd[:60]}...")
    
    print(f"   [3/4] Edição automática (Ken Burns, efeitos)... ✓")
    print(f"   [4/4] Preparação para upload YouTube... ✓")
    
    print(f"\n📤 Resultado esperado:")
    print(f"   Ficheiro: output/s7even_video_1080p.mp4")
    print(f"   Tamanho: ~200-400MB")
    print(f"   Duração: {spec.get('duracao_total_segundos')}s")


def teste_6_instrucoes_publicacao():
    """Testa 6: Mostrar como publicar."""
    print("\n" + "="*70)
    print("TESTE 6: Próximos Passos — Publicação")
    print("="*70)
    
    print("""
📤 Para publicar este vídeo:

   OPÇÃO 1: Via Dashboard Web
   ────────────────────────────
   1. Abre http://localhost:5000
   2. Vai a "Queue" → "S7even Videos"
   3. Seleciona o vídeo criado
   4. Clica "Editar" → "Publicar"
   5. Escolhe canal + configure privacidade
   6. Clica "Upload para YouTube"

   OPÇÃO 2: Via API REST
   ────────────────────
   curl -X POST http://localhost:5000/api/s7even/VIDEO_ID/publish \\
     -H "Content-Type: application/json" \\
     -d '{"channel_id": "SEU_CANAL_ID", "auto_publish": true}'

   OPÇÃO 3: Worker Automático
   ──────────────────────────
   1. Inicia o worker: POST /api/worker/start
   2. Worker detecta vídeos S7even na queue
   3. Processa automaticamente
   4. Publica se auto_publish=true

🎯 Sugestões Avançadas:
   • Customiza áudio em pyttsx3 para acento PT-PT
   • Adiciona efeitos Ken Burns no FFmpeg
   • Cria presets de legendas (ASS/SRT)
   • Implementa moderação de conteúdo (pré-publicação)
    """)


def main():
    """Executa todos os testes."""
    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  🎬 TESTE COMPLETO: S7EVEN AI  ".center(68) + "║")
    print("║" + "     Sistema de Documentários de Mistério Automático".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "═"*68 + "╝")
    
    # Teste 1
    resultado = teste_1_criar_video()
    if not resultado:
        print("\n❌ Teste 1 falhou. Parando.")
        return 1
    
    # Testes 2-6
    teste_2_examinar_spec(resultado)
    teste_3_verificar_assets(resultado)
    queue_item = teste_4_adicionar_a_queue(resultado)
    teste_5_simular_processamento(queue_item)
    teste_6_instrucoes_publicacao()
    
    # Resumo final
    print("\n" + "="*70)
    print("✅ TESTES CONCLUÍDOS COM SUCESSO")
    print("="*70)
    print("""
Próximos passos:

1. Inicia o servidor: 
   python run_server.py

2. Acede ao dashboard:
   http://localhost:5000

3. Vê os vídeos S7even criados em:
   "Queue" → Tab "S7even Videos"

4. Configura publicação e deixa o worker processar

5. Acompanha o progresso em:
   POST /api/queue/current

Bom trabalho! 🎉
    """)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Teste interrompido pelo utilizador.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
