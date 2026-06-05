"""
Script para limpar vídeos antigos e baixar vídeos satisfatórios.
"""
import os
import glob
from modulo1_download import baixar_playlist_satisfatoria


def limpar_videos_queue():
    """Remove todos os vídeos queue_*.mp4 da pasta downloads."""
    pasta = "downloads"
    padroes = ["queue_*.mp4", "queue_*.mp4.part"]
    
    total_apagado = 0
    tamanho_liberado = 0
    
    print("🗑️  A limpar vídeos antigos...")
    
    for padrao in padroes:
        arquivos = glob.glob(os.path.join(pasta, padrao))
        for arquivo in arquivos:
            try:
                tamanho = os.path.getsize(arquivo)
                os.remove(arquivo)
                total_apagado += 1
                tamanho_liberado += tamanho
                print(f"  ✅ Apagado: {os.path.basename(arquivo)} ({tamanho / (1024*1024):.1f} MB)")
            except Exception as e:
                print(f"  ❌ Erro ao apagar {arquivo}: {e}")
    
    tamanho_gb = tamanho_liberado / (1024 * 1024 * 1024)
    print(f"\n✅ {total_apagado} arquivos apagados, {tamanho_gb:.2f} GB liberados\n")
    return total_apagado, tamanho_liberado


def baixar_satisfatorios(url_playlist, n_videos=10):
    """
    Baixa vídeos satisfatórios de uma playlist.
    
    Args:
        url_playlist: URL da playlist do YouTube
        n_videos: Quantidade de vídeos para baixar (padrão: 10)
    """
    print(f"📥 A baixar {n_videos} vídeos satisfatórios...")
    print(f"📋 Playlist: {url_playlist}\n")
    
    videos = baixar_playlist_satisfatoria(url_playlist, n_videos=n_videos)
    
    print(f"\n✅ Download concluído! {len(videos)} vídeos prontos na pasta downloads/satisfying/")
    return videos


if __name__ == "__main__":
    # 1. Limpar vídeos antigos
    limpar_videos_queue()
    
    # 2. Baixar vídeos satisfatórios
    # IMPORTANTE: Substitua a URL abaixo pela sua playlist de vídeos satisfatórios
    URL_PLAYLIST = input("Cole a URL da playlist de vídeos satisfatórios: ").strip()
    
    if URL_PLAYLIST:
        QUANTIDADE = input("Quantos vídeos baixar? (padrão: 10): ").strip()
        try:
            n = int(QUANTIDADE) if QUANTIDADE else 10
        except ValueError:
            n = 10
        
        baixar_satisfatorios(URL_PLAYLIST, n_videos=n)
    else:
        print("⚠️  Nenhuma URL fornecida, apenas limpei os vídeos antigos.")
