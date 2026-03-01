import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # Evita conflito libiomp5md.dll vs libomp.dll

from dotenv import load_dotenv
from modulo1_download import baixar_video_youtube
from modulo2_analise import extrair_audio_do_video, transcrever_audio_whisper, analisar_com_ollama, salvar_analise, verificar_gpu
from modulo3_edicao import ler_analise_clipes, editar_clipes, salvar_lista_clips

# Carrega as variáveis do arquivo .env
load_dotenv()

def main():
    print("🤖 Iniciando a Clipadora AI (100% GRATUITA)...")
    print("💡 Usando Faster-Whisper + Llama 2 (sem custos!)\n")
    
    # Verifica GPU
    device, gpu_disponivel, info_gpu = verificar_gpu()
    print(info_gpu)
    print()
    
    # Para testar, você pode usar qualquer URL do YouTube (substitua a URL abaixo)
    # IMPORTANTE: Use vídeos com PESSOAS A FALAR português!
    # Exemplos BOM:
    # - Um podcast português
    # - Um vídeo educativo português
    # - Uma entrevista/debate
    # - Um streamer português
    
    url_teste = "https://www.youtube.com/watch?v=67M8fQVI250"  # Testando com novo vídeo
    
    # ============================================
    # ETAPA 1: DOWNLOAD
    # ============================================
    print("\n--- ETAPA 1: DOWNLOAD ---")
    caminho_do_video = baixar_video_youtube(url_teste, "meu_primeiro_teste")
    
    if not caminho_do_video:
        print("\n⚠️ Erro no download. Abortando.")
        return
    
    # ============================================
    # ETAPA 2: ANÁLISE (Whisper + Llama 2)
    # ============================================
    print("\n--- ETAPA 2: ANÁLISE COM IA (100% LOCAL) ---")
    
    # 2.1 Extrai áudio
    caminho_audio = extrair_audio_do_video(caminho_do_video)
    if not caminho_audio:
        print("⚠️ Erro ao extrair áudio. Abortando.")
        return
    
    # 2.2 Transcreve com Faster-Whisper (GRATUITO)
    transcrição = transcrever_audio_whisper(caminho_audio)
    if not transcrição:
        print("⚠️ Erro na transcrição. Abortando.", flush=True)
        return
    
    print(f"  📊 Transcrição obtida: {len(transcrição.get('segmentos', []))} segmentos", flush=True)
    
    # 2.3 Analisa com Llama 2 (GRATUITO)
    print("\n  🧠 Enviando para Llama 2 (pode demorar 30-120s)...", flush=True)
    clipes_recomendados = analisar_com_ollama(transcrição)
    if not clipes_recomendados:
        print("⚠️ Erro na análise. Abortando.")
        return
    
    # 2.4 Salva a análise para usar no próximo módulo
    salvar_analise(clipes_recomendados)
    
    # ============================================
    # ETAPA 3: EDIÇÃO AUTOMÁTICA
    # ============================================
    print("\n--- ETAPA 3: EDIÇÃO AUTOMÁTICA ---")
    
    # Lê a análise de clipes
    clipes = ler_analise_clipes()
    if not clipes:
        print("⚠️ Erro ao ler análise de clipes. Abortando.")
        return
    
    # Edita os clipes (agora com legendas dinâmicas do Whisper!)
    segmentos_whisper = transcrição.get("segmentos", [])
    clipes_editados = editar_clipes(caminho_do_video, clipes, segmentos_whisper)
    
    if not clipes_editados:
        print("⚠️ Nenhum clipe foi editado com sucesso.")
        return
    
    # Salva a lista de clips para o próximo módulo (publicação)
    salvar_lista_clips(clipes_editados)
    
    print("\n✨ Edição concluída! Próxima etapa: Publicação automática em redes sociais")

if __name__ == "__main__":
    main()
