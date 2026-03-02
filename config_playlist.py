"""
Script para configurar rapidamente uma playlist satisfatória para o AutoManager
"""

import database as db

# URL da playlist de vídeos satisfatórios (exemplo)
# Você pode trocar por qualquer playlist do YouTube
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLzvRQMJ9HDiSH0UWS9Y3Q9TvCkY_e_EYq"  # Oddly Satisfying

def configurar_auto_manager():
    """Configura o AutoManager com uma playlist."""
    
    print("🤖 Configurando AutoManager...")
    
    settings = db.get_settings()
    settings["auto_manager"] = {
        "enabled": True,
        "playlist_url": PLAYLIST_URL,
        "max_storage_mb": 5000,  # 5GB
        "check_interval_minutes": 15  # Verificar a cada 15 minutos
    }
    db.save_settings(settings)
    
    print(f"✅ AutoManager configurado!")
    print(f"   📺 Playlist: {PLAYLIST_URL}")
    print(f"   💾 Limite: 5GB")
    print(f"   ⏱️  Intervalo: 15 minutos")
    print("\n🚀 Inicie o servidor com: python app.py")

if __name__ == "__main__":
    configurar_auto_manager()
