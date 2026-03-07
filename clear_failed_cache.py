#!/usr/bin/env python3
"""
Utilitário para limpar o cache de vídeos que falharam (bot-detection, etc)
Útil quando você quer tentar fazer download de vídeos que foram skipados antes.
"""

import os
import json

_FAILED_VIDEOS_TRACKER = os.path.join("data", "auto_failed_videos.json")


def clear_cache():
    """Remove o arquivo de vídeos falhados."""
    if os.path.exists(_FAILED_VIDEOS_TRACKER):
        try:
            os.remove(_FAILED_VIDEOS_TRACKER)
            print("✅ Cache de vídeos falhados removido com sucesso!")
            print("   Os vídeos que falharam por bot-detection serão retentados na próxima vez.")
            return True
        except Exception as e:
            print(f"❌ Erro ao remover cache: {e}")
            return False
    else:
        print("ℹ️  Cache de vídeos falhados não encontrado (já está vazio)")
        return True


def show_failed_videos():
    """Mostra lista de vídeos que falharam."""
    if not os.path.exists(_FAILED_VIDEOS_TRACKER):
        print("✅ Nenhum vídeo falhado no cache")
        return
    
    try:
        with open(_FAILED_VIDEOS_TRACKER, "r", encoding="utf-8") as f:
            failed = json.load(f)
        
        if not failed:
            print("✅ Nenhum vídeo falhado no cache")
            return
        
        print(f"📋 {len(failed)} vídeos com falha anterior:\n")
        for vid_id, reason in failed.items():
            print(f"  • {vid_id}: {reason}")
        
    except Exception as e:
        print(f"❌ Erro ao ler cache: {e}")


def clear_specific_video(vid_id):
    """Remove um vídeo específico do cache de erros."""
    if not os.path.exists(_FAILED_VIDEOS_TRACKER):
        print(f"ℹ️  Cache vazio - nada a remover")
        return False
    
    try:
        with open(_FAILED_VIDEOS_TRACKER, "r", encoding="utf-8") as f:
            failed = json.load(f)
        
        if vid_id in failed:
            del failed[vid_id]
            with open(_FAILED_VIDEOS_TRACKER, "w", encoding="utf-8") as f:
                json.dump(failed, f)
            print(f"✅ Vídeo {vid_id} removido do cache de erros")
            print(f"   Será retentado na próxima verificação da playlist")
            return True
        else:
            print(f"ℹ️  Vídeo {vid_id} não está no cache de erros")
            return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "show":
            show_failed_videos()
        elif cmd == "clear":
            clear_cache()
        elif cmd == "remove" and len(sys.argv) > 2:
            clear_specific_video(sys.argv[2])
        else:
            print("Uso:")
            print("  python clear_failed_cache.py show              # Mostra vídeos falhados")
            print("  python clear_failed_cache.py clear             # Limpa tudo o cache")
            print("  python clear_failed_cache.py remove <video_id> # Remove 1 vídeo específico")
    else:
        # Default: mostrar cache
        show_failed_videos()
