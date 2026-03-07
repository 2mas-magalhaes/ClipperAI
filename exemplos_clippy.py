"""
Exemplos de uso da funcionalidade Clippy
"""

# ═══════════════════════════════════════════════════════════════
# EXEMPLO 1: Uso no Pipeline Completo (main.py)
# ═══════════════════════════════════════════════════════════════

# Nada muda! A funcionalidade Clippy está ativada por padrão.
# Apenas execute:
# 
# python main.py
#
# Os vídeos editados terão automaticamente a intro do Clippy.


# ═══════════════════════════════════════════════════════════════
# EXEMPLO 2: Desativar o Clippy (se não quiser usar)
# ═══════════════════════════════════════════════════════════════

from modulo3_edicao import editar_clipes

clipes_editados = editar_clipes(
    caminho_video="meu_video.mp4",
    clipes=[...],
    segmentos_whisper=[...],
    adicionar_intro_clippy=False  # <-- Desativa o Clippy
)


# ═══════════════════════════════════════════════════════════════
# EXEMPLO 3: Gerar apenas um hook (sem criar vídeo)
# ═══════════════════════════════════════════════════════════════

from personagem_clippy import gerar_hook_com_ai

hook = gerar_hook_com_ai(
    titulo_clip="10 Truques de Python que Você Não Conhece",
    razao_clip="Mostra técnicas avançadas e pouco conhecidas",
    transcricao_preview="Hoje vou mostrar truques que vão mudar sua vida..."
)

print(f"Hook gerado: {hook}")
# Saída: "Espera até veres o que estes truques podem fazer!"


# ═══════════════════════════════════════════════════════════════
# EXEMPLO 4: Criar apenas a imagem do Clippy
# ═══════════════════════════════════════════════════════════════

from personagem_clippy import criar_personagem_clippy

caminho_imagem = criar_personagem_clippy()
print(f"Imagem criada: {caminho_imagem}")
# Agora você pode usar a imagem em outros projetos!


# ═══════════════════════════════════════════════════════════════
# EXEMPLO 5: Sintetizar uma mensagem customizada
# ═══════════════════════════════════════════════════════════════

from personagem_clippy import sintetizar_voz_hook

audio = sintetizar_voz_hook(
    texto_hook="Bem-vindo ao meu canal! Prepara-te para uma jornada incrível!",
    caminho_saida="minha_mensagem.mp3"
)

print(f"Áudio criado: {audio}")
# Use este áudio em qualquer lugar!


# ═══════════════════════════════════════════════════════════════
# EXEMPLO 6: Criar intro customizada para um vídeo específico
# ═══════════════════════════════════════════════════════════════

from personagem_clippy import criar_intro_clippy

intro = criar_intro_clippy(
    caminho_video_base="meu_video.mp4",
    texto_hook="Este vídeo vai mudar a tua perspectiva!",
    caminho_saida="intro_customizada.mp4",
    duracao_intro=5.0,  # 5 segundos
    fade_out_duracao=0.8
)

print(f"Intro criada: {intro}")


# ═══════════════════════════════════════════════════════════════
# EXEMPLO 7: Concatenar intro customizada com vídeo
# ═══════════════════════════════════════════════════════════════

from personagem_clippy import concatenar_intro_com_video

sucesso = concatenar_intro_com_video(
    caminho_intro="intro_customizada.mp4",
    caminho_video="meu_video.mp4",
    caminho_saida="video_final_com_intro.mp4"
)

if sucesso:
    print("Vídeo final criado com sucesso!")


# ═══════════════════════════════════════════════════════════════
# EXEMPLO 8: Gerar múltiplos hooks e escolher o melhor
# ═══════════════════════════════════════════════════════════════

from personagem_clippy import gerar_hook_com_ai

titulo = "Segredos de Produtividade"
razao = "Mostra técnicas revolucionárias"

# Gerar 3 versões
hooks = []
for i in range(3):
    hook = gerar_hook_com_ai(titulo, razao)
    hooks.append(hook)
    print(f"Hook {i+1}: {hook}")

# Escolher o melhor manualmente ou com critérios automáticos
melhor_hook = min(hooks, key=len)  # Exemplo: escolhe o mais curto
print(f"\nMelhor hook: {melhor_hook}")


# ═══════════════════════════════════════════════════════════════
# EXEMPLO 9: Pipeline completo personalizado
# ═══════════════════════════════════════════════════════════════

from personagem_clippy import (
    gerar_hook_com_ai,
    sintetizar_voz_hook,
    criar_intro_clippy,
    concatenar_intro_com_video
)

# 1. Gerar hook
hook = gerar_hook_com_ai(
    titulo_clip="Meu Vídeo Viral",
    razao_clip="Conteúdo incrível e surpreendente"
)

# 2. Criar introdução
intro = criar_intro_clippy(
    caminho_video_base="meu_video.mp4",
    texto_hook=hook,
    caminho_saida="intro.mp4",
    duracao_intro=4.0
)

# 3. Concatenar com vídeo principal
if intro:
    concatenar_intro_com_video(
        caminho_intro=intro,
        caminho_video="meu_video.mp4",
        caminho_saida="video_final.mp4"
    )


# ═══════════════════════════════════════════════════════════════
# EXEMPLO 10: Integração com worker automático
# ═══════════════════════════════════════════════════════════════

# Se você usar o worker.py ou auto_manager.py, a funcionalidade
# Clippy já está integrada automaticamente!
#
# Os vídeos processados pela fila terão a intro do Clippy.
#
# Para desativar globalmente, edite modulo3_edicao.py e mude:
# adicionar_intro_clippy=True  para  adicionar_intro_clippy=False


# ═══════════════════════════════════════════════════════════════
# DICAS E TRUQUES
# ═══════════════════════════════════════════════════════════════

"""
💡 DICA 1: Personalizar voz
   Edite personagem_clippy.py, função sintetizar_voz_hook()
   Troque: voz = "pt-BR-FranciscaNeural"
   Para: voz = "pt-PT-RaquelNeural" (PT-PT)
   Ou: voz = "pt-BR-AntonioNeural" (masculino)

💡 DICA 2: Ajustar duração da intro
   Por padrão: 4.5 segundos
   Edite: duracao_intro=4.5 para o valor desejado

💡 DICA 3: Hooks mais criativos
   O modelo Llama 3.2 gera hooks diferentes a cada vez
   Para hooks mais criativos, execute múltiplas vezes

💡 DICA 4: Cache de hooks
   Para economizar tempo, você pode criar um cache:
   
   cache_hooks = {}
   tema = "produtividade"
   
   if tema not in cache_hooks:
       cache_hooks[tema] = gerar_hook_com_ai(...)
   
   hook = cache_hooks[tema]

💡 DICA 5: Testar antes de processar lote
   Execute test_clippy.py antes de processar vários vídeos:
   
   python test_clippy.py
   
   Isso garante que tudo está funcionando!

💡 DICA 6: Personalizar aparência do Clippy
   Edite personagem_clippy.py, função criar_personagem_clippy()
   Mude cores, tamanho, expressões, etc.

💡 DICA 7: Múltiplas expressões
   Futuramente você pode criar:
   - Clippy feliz
   - Clippy surpreso
   - Clippy pensativo
   - Clippy animado
   
   E escolher baseado no tom do vídeo!

💡 DICA 8: Métricas de engajamento
   Após publicar vídeos com Clippy, compare:
   - Retenção nos primeiros 3 segundos
   - Taxa de visualização completa
   - Engajamento (likes/comentários)
   
   Para medir o impacto real dos hooks!
"""
