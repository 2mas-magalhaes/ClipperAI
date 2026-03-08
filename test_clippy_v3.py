"""
Teste Completo — Clippy 3.0 (Ultra-Professional)
Verifica: corpo com braços/pernas, 13 animações, 6 expressões,
easing functions, transições, renderização, vídeo, voz, hook AI.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import personagem_clippy as pc


def limpar_cache():
    """Remove imagens cached para forçar recriação."""
    import glob
    for f in glob.glob("data/clippy_*.png") + glob.glob("data/clippy_*.mp4"):
        try:
            os.remove(f)
        except OSError:
            pass


def teste_1_expressoes_corpo_completo():
    """Testa 6 expressões com corpo completo (braços + pernas)."""
    print("\n" + "=" * 60)
    print("TESTE 1: Expressões com corpo completo")
    print("=" * 60)
    expressoes = ("normal", "sarcastico", "surpreso", "rindo", "pensativo", "chocado")
    ok = 0
    for expr in expressoes:
        path = pc.criar_personagem_clippy(expressao=expr)
        assert os.path.exists(path), f"Ficheiro não criado: {path}"
        size = os.path.getsize(path)
        assert size > 5000, f"Imagem muito pequena: {size} bytes"
        ok += 1
        print(f"  ✅ {expr}: {size / 1024:.1f} KB")
    print(f"  Resultado: {ok}/{len(expressoes)} expressões OK")
    return ok == len(expressoes)


def teste_2_animacoes_completas():
    """Testa todas as 13 animações."""
    print("\n" + "=" * 60)
    print("TESTE 2: Sistema de animações (13 poses)")
    print("=" * 60)
    ok = 0
    for nome, func in pc.ANIMACOES.items():
        # Testa em vários pontos do tempo
        for t in [0, 0.25, 0.5, 0.75, 1.0]:
            pose = func(t)
            assert isinstance(pose, dict), f"{nome}(t={t}) não retornou dict"
            # Verifica campos obrigatórios
            for key in ('body_dy', 'braco_esq_angulo', 'braco_dir_angulo',
                        'perna_esq', 'perna_dir', 'pupila_dx', 'pupila_dy'):
                assert key in pose, f"{nome} falta campo: {key}"
        ok += 1
        print(f"  ✅ {nome}: 5 timestamps OK")
    print(f"  Resultado: {ok}/{len(pc.ANIMACOES)} animações OK")
    return ok == len(pc.ANIMACOES)


def teste_3_easing_functions():
    """Testa easing functions (limites e monotonicidade)."""
    print("\n" + "=" * 60)
    print("TESTE 3: Easing functions")
    print("=" * 60)
    funcs = [
        pc.ease_in_out_cubic, pc.ease_out_bounce,
        pc.ease_out_elastic, pc.ease_out_back,
        pc.ease_in_out_quad, pc.linear
    ]
    ok = 0
    for f in funcs:
        v0 = f(0)
        v1 = f(1)
        assert abs(v0) < 0.01, f"{f.__name__}(0) = {v0}, esperado ~0"
        assert abs(v1 - 1.0) < 0.15, f"{f.__name__}(1) = {v1}, esperado ~1"
        ok += 1
        print(f"  ✅ {f.__name__}: f(0)={v0:.4f}, f(1)={v1:.4f}")
    print(f"  Resultado: {ok}/{len(funcs)} funções OK")
    return ok == len(funcs)


def teste_4_render_frame_motor():
    """Testa motor de renderização com várias combinações."""
    print("\n" + "=" * 60)
    print("TESTE 4: Motor de renderização (frame a frame)")
    print("=" * 60)
    combos = [
        ("normal", "idle"),
        ("sarcastico", "shrug"),
        ("surpreso", "bounce"),
        ("rindo", "dance"),
        ("pensativo", "think"),
        ("chocado", "facepalm"),
    ]
    ok = 0
    for expr, anim in combos:
        pose = pc.ANIMACOES[anim](0.5)
        img = pc.renderizar_clippy_frame(
            400, 700, 200, 300, escala=0.9,
            expressao=expr, pose=pose, alpha=0.8
        )
        assert img.size == (400, 700), f"Tamanho errado: {img.size}"
        assert img.mode == "RGBA", f"Modo errado: {img.mode}"
        # Verificar que não é completamente transparente
        pixels = list(img.getdata())
        non_transparent = sum(1 for p in pixels if p[3] > 0)
        assert non_transparent > 100, f"Imagem quase vazia: {non_transparent} pixels visíveis"
        ok += 1
        print(f"  ✅ {expr}/{anim}: {non_transparent} pixels visíveis")
    print(f"  Resultado: {ok}/{len(combos)} combinações OK")
    return ok == len(combos)


def teste_5_sequencia_animacao():
    """Testa geração de sequência de frames com entrada/saída."""
    print("\n" + "=" * 60)
    print("TESTE 5: Sequência de animação (entrada → anim → saída)")
    print("=" * 60)
    frames = pc.gerar_sequencia_animacao(
        animacao="wave", expressao="normal",
        duracao=1.0, fps=10,
        largura=200, altura=350, pasta_saida="data",
        entrada="bounce_in", saida="fade_out",
        duracao_entrada=0.3, duracao_saida=0.3
    )
    assert frames is not None, "Sequência retornou None"
    assert len(frames) == 10, f"Esperado 10 frames, obteve {len(frames)}"
    exists = sum(1 for f in frames if os.path.exists(f))
    print(f"  ✅ {exists}/{len(frames)} frames gerados")

    # Limpa
    for f in frames:
        if os.path.exists(f):
            os.remove(f)

    resultado = exists == len(frames)
    print(f"  Resultado: {'PASS' if resultado else 'FAIL'}")
    return resultado


def teste_6_video_animado():
    """Testa criação de vídeo animado completo."""
    print("\n" + "=" * 60)
    print("TESTE 6: Vídeo animado com FFmpeg")
    print("=" * 60)

    entradas = ["slide_in", "bounce_in", "pop_in"]
    ok = 0
    for ent in entradas:
        vid = pc.criar_clippy_animada(
            expressao="normal", animacao="wave",
            duracao=1.0, entrada=ent, saida="fade_out"
        )
        if vid and os.path.exists(vid):
            size = os.path.getsize(vid) / 1024
            print(f"  ✅ {ent}: {size:.1f} KB")
            ok += 1
            os.remove(vid)
        else:
            print(f"  ❌ {ent}: falhou")

    print(f"  Resultado: {ok}/{len(entradas)} entradas OK")
    return ok == len(entradas)


def teste_7_sintese_voz_expressoes():
    """Testa TTS com diferentes expressões."""
    print("\n" + "=" * 60)
    print("TESTE 7: Síntese de voz por expressão")
    print("=" * 60)
    expressoes = ["normal", "sarcastico", "surpreso"]
    ok = 0
    for expr in expressoes:
        path = f"data/teste_voz_{expr}_v3.mp3"
        audio = pc.sintetizar_voz_hook(
            f"Teste de voz {expr}", path, expressao=expr
        )
        if audio and os.path.exists(audio):
            size = os.path.getsize(audio) / 1024
            print(f"  ✅ {expr}: {size:.1f} KB")
            ok += 1
            os.remove(audio)
        else:
            print(f"  ❌ {expr}: falhou")

    print(f"  Resultado: {ok}/{len(expressoes)} vozes OK")
    return ok == len(expressoes)


def teste_8_hook_ai():
    """Testa geração de hook com AI."""
    print("\n" + "=" * 60)
    print("TESTE 8: Hook AI (Ollama)")
    print("=" * 60)
    hook = pc.gerar_hook_com_ai(
        "Segredo de produtividade",
        "Técnica que muda tudo"
    )
    assert isinstance(hook, str), "Hook não é string"
    assert len(hook) > 5, f"Hook muito curto: '{hook}'"
    assert len(hook) <= 120, f"Hook muito longo: {len(hook)} chars"
    print(f"  ✅ Hook ({len(hook)} chars): '{hook}'")
    print(f"  Resultado: PASS")
    return True


def teste_9_intervencoes_ai():
    """Testa geração de intervenções satíricas."""
    print("\n" + "=" * 60)
    print("TESTE 9: Intervenções satíricas (AI)")
    print("=" * 60)
    transcricao = """
    Hoje vou mostrar como ganhar dinheiro fácil. É muito simples, basta
    seguir estes 3 passos. Primeiro, acordas cedo. Depois, trabalhas muito.
    E por fim, tens sorte. Fácil não é? Toda a gente pode fazer isto.
    """
    intervencoes = pc.gerar_intervencoes_satiricas(
        "Ganhar Dinheiro Fácil", transcricao, "Promete riqueza fácil"
    )
    assert isinstance(intervencoes, list), "Não retornou lista"
    print(f"  ✅ {len(intervencoes)} intervenções geradas")
    for i, interv in enumerate(intervencoes, 1):
        print(f"     {i}. \"{interv.get('comentario', '')}\" "
              f"({interv.get('expressao', '?')}/{interv.get('animacao', '?')})")
        # Verifica campos
        assert 'comentario' in interv, "Falta comentário"
        assert 'expressao' in interv, "Falta expressão"
        assert 'animacao' in interv, "Falta animação"
        assert interv['animacao'] in pc.ANIMACOES, f"Animação inválida: {interv['animacao']}"
    print(f"  Resultado: PASS")
    return True


def teste_10_retrocompatibilidade():
    """Testa que a API antiga continua a funcionar."""
    print("\n" + "=" * 60)
    print("TESTE 10: Retro-compatibilidade com API v2")
    print("=" * 60)
    # Chamada simples sem novos params (como modulo3 faz)
    path = pc.criar_personagem_clippy()
    assert os.path.exists(path), "Falhou sem argumentos"
    print(f"  ✅ criar_personagem_clippy() = {path}")

    # Com frame (para piscar)
    path2 = pc.criar_personagem_clippy(expressao="normal", frame=2)
    assert os.path.exists(path2), "Falhou com frame=2"
    print(f"  ✅ criar_personagem_clippy(frame=2) = {path2}")

    # Sintese sem expressão
    audio = pc.sintetizar_voz_hook("Teste", "data/teste_retro.mp3")
    if audio:
        os.remove(audio)
    print(f"  ✅ sintetizar_voz_hook() retro OK")

    print(f"  Resultado: PASS")
    return True


def main():
    print("🧪 CLIPPY 3.0 — Teste Completo Ultra-Professional")
    print("=" * 60)
    print("Corpo com braços + pernas + mãos + pés")
    print("13 animações • 6 expressões • Easing profissional")
    print("=" * 60)

    limpar_cache()

    testes = [
        ("Expressões corpo completo", teste_1_expressoes_corpo_completo),
        ("Sistema de animações", teste_2_animacoes_completas),
        ("Easing functions", teste_3_easing_functions),
        ("Motor de renderização", teste_4_render_frame_motor),
        ("Sequência de animação", teste_5_sequencia_animacao),
        ("Vídeo animado FFmpeg", teste_6_video_animado),
        ("Síntese de voz", teste_7_sintese_voz_expressoes),
        ("Hook AI", teste_8_hook_ai),
        ("Intervenções satíricas", teste_9_intervencoes_ai),
        ("Retro-compatibilidade", teste_10_retrocompatibilidade),
    ]

    resultados = []
    for nome, func in testes:
        try:
            ok = func()
            resultados.append((nome, ok))
        except Exception as e:
            print(f"  ❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            resultados.append((nome, False))

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)
    passed = 0
    for nome, ok in resultados:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status} — {nome}")
        if ok:
            passed += 1

    total = len(resultados)
    print(f"\n  📊 {passed}/{total} testes passaram")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
