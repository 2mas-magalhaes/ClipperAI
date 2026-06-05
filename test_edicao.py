#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de teste do loop infinito com um clip existente.
Faz APENAS o passo do loop (sem re-editar tudo) para validar rapidamente.
"""

import os
import subprocess
from modulo3_edicao import aplicar_loop_infinito, obter_duracao_video

# ── Encontra um clip já editado ou usa qualquer mp4 ──────────────────────────
pasta_editados = "downloads/clips_editados"
video_teste = None

# Prefere um clip já editado (pré-loop)
for f in sorted(os.listdir(pasta_editados)) if os.path.exists(pasta_editados) else []:
    if f.endswith("_preloop.mp4") or f.endswith("_final.mp4"):
        video_teste = os.path.join(pasta_editados, f)
        break

# Fallback: qualquer mp4 em downloads
if not video_teste:
    for f in sorted(os.listdir("downloads")):
        if f.endswith(".mp4") and not f.endswith(".part") and "test" not in f:
            video_teste = os.path.join("downloads", f)
            break

if not video_teste or not os.path.exists(video_teste):
    print("❌ Nenhum vídeo encontrado para testar")
    exit(1)

saida = "downloads/test_loop_perfeito.mp4"
duracao = obter_duracao_video(video_teste)

print(f"\n{'='*60}")
print(f"🔁 TESTE LOOP INFINITO PERFEITO")
print(f"{'='*60}")
print(f"Entrada : {video_teste}")
print(f"Duração : {duracao:.2f}s")
print(f"Saída   : {saida}")
print()

ok = aplicar_loop_infinito(video_teste, saida, duracao, xfade_dur=2.0)

if ok and os.path.exists(saida):
    dur_out = obter_duracao_video(saida)
    tam_mb  = os.path.getsize(saida) / (1024 * 1024)
    print(f"\n✅ SUCESSO")
    print(f"   Input  : {duracao:.2f}s")
    print(f"   Output : {dur_out:.2f}s  (esperado ≈ {duracao - 2.0:.2f}s)")
    print(f"   Tamanho: {tam_mb:.1f}MB")
    print(f"\n👁️  Verifica manualmente: último frame == primeiro frame")
    print(f"   ffplay \"{saida}\"")
    # Abre com o player padrão do Windows
    os.startfile(os.path.abspath(saida))
else:
    print(f"\n❌ Loop falhou")

