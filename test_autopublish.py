"""
Script de teste para verificar o sistema de auto-publicação com logs
"""

import database as db

def verificar_configuracao():
    """Verifica se o sistema está configurado corretamente para auto-publicação."""
    
    print("\n" + "="*60)
    print("🔍 VERIFICAÇÃO DO SISTEMA DE AUTO-PUBLICAÇÃO")
    print("="*60 + "\n")
    
    # 1. Verificar definições globais
    settings = db.get_settings()
    auto_pub_global = settings.get("auto_publish", False)
    default_channel = settings.get("default_channel_id")
    
    print("1️⃣  DEFINIÇÕES GLOBAIS:")
    print(f"   Auto-publicação global: {'✅ ATIVADA' if auto_pub_global else '❌ DESATIVADA'}")
    print(f"   Canal padrão: {default_channel or '⚠️ Nenhum configurado'}")
    print()
    
    # 2. Verificar canais
    channels = db.get_channels()
    print("2️⃣  CANAIS CONFIGURADOS:")
    if not channels:
        print("   ⚠️ Nenhum canal configurado")
    else:
        for ch in channels:
            creds = ch.get("credentials_path", "")
            has_oauth = "✅" if creds and creds.strip() else "❌"
            print(f"   {has_oauth} {ch['name']} (ID: {ch['id']})")
            if creds:
                print(f"      OAuth: {creds}")
    print()
    
    # 3. Verificar queue
    queue = db.get_queue()
    print("3️⃣  ITENS NA QUEUE:")
    if not queue:
        print("   ℹ️ Queue vazia")
    else:
        for item in queue[:5]:  # Mostrar até 5
            status = item.get("status", "unknown")
            auto_pub = item.get("auto_publish")
            channel_id = item.get("channel_id")
            
            # Determinar o ícone do status
            status_icons = {
                "queued": "⏳",
                "downloading": "⬇️",
                "analyzing": "🧠",
                "editing": "✂️",
                "done": "✅",
                "error": "❌"
            }
            icon = status_icons.get(status, "❓")
            
            print(f"   {icon} {item['title'][:40]}")
            print(f"      Status: {status}")
            print(f"      Auto-pub: {'✅ SIM' if auto_pub else ('❌ NÃO' if auto_pub is False else '⚙️ Global')}")
            print(f"      Canal: {channel_id or '⚙️ Padrão'}")
            print()
    
    # 4. Verificar clips em revisão
    review = db.get_review_clips()
    pending = [c for c in review if c.get("status") == "pending"]
    uploading = [c for c in review if c.get("status") == "uploading"]
    
    print("4️⃣  CLIPS EM REVISÃO:")
    print(f"   📋 Pendentes: {len(pending)}")
    print(f"   📤 Em upload: {len(uploading)}")
    print()
    
    # 5. Verificar vídeos publicados
    posted = db.get_posted_videos()
    print("5️⃣  VÍDEOS PUBLICADOS:")
    print(f"   ✅ Total: {len(posted)}")
    if posted:
        recent = posted[-3:]  # Últimos 3
        print("   Últimos:")
        for v in recent:
            youtube_url = v.get("youtube_url", "")
            icon = "🌐" if youtube_url else "📁"
            print(f"   {icon} {v['title'][:40]}")
            if youtube_url:
                print(f"      {youtube_url}")
    print()
    
    # 6. Resumo e recomendações
    print("="*60)
    print("📊 RESUMO:")
    print("="*60)
    
    issues = []
    
    if not channels:
        issues.append("❌ Nenhum canal configurado")
    else:
        oauth_channels = [ch for ch in channels if ch.get("credentials_path", "").strip()]
        if not oauth_channels:
            issues.append("⚠️ Nenhum canal com OAuth configurado")
    
    if not default_channel and not auto_pub_global:
        issues.append("ℹ️ Auto-publicação desativada globalmente")
    
    if issues:
        print("\n⚠️  PROBLEMAS ENCONTRADOS:\n")
        for issue in issues:
            print(f"   {issue}")
        print()
        print("📝 RECOMENDAÇÕES:")
        print("   1. Configure um canal em: Canais → Adicionar Canal")
        print("   2. Adicione credenciais OAuth ao canal")
        print("   3. Ative auto-publicação em: Definições → Auto-publicação")
        print("   4. Ou ative por vídeo: Queue → ✓ Publicar automaticamente")
    else:
        print("\n✅ SISTEMA CONFIGURADO CORRETAMENTE!")
        print("   O sistema está pronto para auto-publicação com upload real.")
        print()
        print("🚀 PRÓXIMOS PASSOS:")
        print("   1. Inicie o servidor: python app.py")
        print("   2. Adicione vídeos à queue")
        print("   3. Inicie o Worker")
        print("   4. Observe os logs detalhados no terminal!")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    verificar_configuracao()
