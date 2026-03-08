"""
MÓDULO PERSONAGEM AI — CLIPPY 3.0 (Ultra-Professional)

Personagem AI completa com corpo articulado (braços, pernas, mãos),
sistema de animações profissionais com easing, transições clean de
entrada/saída, e interações naturais e engraçadas.

Características:
  ✦ Corpo completo: cabeça clipe de papel + braços + pernas + mãos
  ✦ 6 expressões faciais (normal, sarcastico, surpreso, rindo, pensativo, chocado)
  ✦ 12+ animações: wave, bounce, slide_in, slide_out, dance, point, shrug,
    facepalm, lean_in, celebrate, peek, think
  ✦ Sistema de easing profissional (ease_in_out_cubic, bounce, elastic, etc.)
  ✦ Entrada/saída clean com animações fluidas
  ✦ Motor de frames para gerar sequências de animação suave
  ✦ Prompts AI otimizados para humor natural português
"""

import os
import math
import subprocess
import random
import json
import re
import asyncio
from PIL import Image, ImageDraw, ImageFont


# ════════════════════════════════════════════════════════════════════
#  EASING FUNCTIONS — Animações suaves e profissionais
# ════════════════════════════════════════════════════════════════════

def ease_in_out_cubic(t):
    """Aceleração suave no início e no fim."""
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2

def ease_out_bounce(t):
    """Efeito de bounce (quicar) no fim."""
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375

def ease_out_elastic(t):
    """Efeito elástico."""
    if t == 0 or t == 1:
        return t
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1

def ease_out_back(t):
    """Overshoot ligeiro (passa e volta)."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)

def ease_in_out_quad(t):
    """Easing quadrático suave."""
    if t < 0.5:
        return 2 * t * t
    return 1 - pow(-2 * t + 2, 2) / 2

def linear(t):
    return t


# ════════════════════════════════════════════════════════════════════
#  CORPO ARTICULADO — Desenho completo da Clippy
# ════════════════════════════════════════════════════════════════════

# Paleta de cores profissional
CORES = {
    'corpo_principal': (200, 210, 220, 255),      # Prateado azulado
    'corpo_highlight': (230, 235, 245, 255),       # Highlight
    'corpo_sombra': (150, 160, 175, 255),          # Sombra
    'corpo_borda': (120, 130, 145, 255),           # Borda escura
    'olho_branco': (255, 255, 255, 255),
    'pupila': (40, 45, 55, 255),                   # Quase preto
    'pupila_brilho': (255, 255, 255, 220),
    'boca': (100, 110, 125, 255),
    'sobrancelha': (100, 110, 125, 255),
    'mao': (200, 210, 220, 255),
    'mao_borda': (150, 160, 175, 255),
    'pe': (170, 180, 195, 255),
    'pe_borda': (130, 140, 155, 255),
    'blush': (255, 180, 180, 80),                  # Bochechas (quando ri)
    'brilho_metalico': (255, 255, 255, 100),       # Reflexo metálico
}


def _desenhar_corpo_clippy(draw, cx, cy, escala=1.0):
    """
    Desenha o corpo como clipe de papel autêntico — um arame metálico
    contínuo com loop exterior, ponte de ligação, e loop interior.
    """
    s = escala
    borda = CORES['corpo_borda']
    principal = CORES['corpo_principal']
    highlight = CORES['corpo_highlight']
    sombra = CORES['corpo_sombra']

    wire = int(22 * s)
    wire_in = int(16 * s)

    # Loop exterior
    out_w = int(130 * s)
    out_h = int(280 * s)
    out_r = int(55 * s)

    ox1, oy1 = cx - out_w // 2, cy - out_h // 2
    ox2, oy2 = cx + out_w // 2, cy + out_h // 2

    # Loop interior (começa perto do topo, mais curto que o exterior)
    in_margin = int(34 * s)
    in_w = out_w - 2 * in_margin
    in_top_gap = int(16 * s)
    in_h = int(180 * s)
    in_r = int(25 * s)

    ix1, iy1 = cx - in_w // 2, oy1 + in_top_gap
    ix2, iy2 = cx + in_w // 2, iy1 + in_h

    def _metal_rect(x1, y1, x2, y2, radius, thick):
        """Retângulo arredondado com gradiente metálico."""
        for i in range(thick):
            t = i / max(thick - 1, 1)
            if t < 0.08:
                c = borda
            elif t < 0.28:
                c = sombra
            elif t < 0.55:
                c = principal
            elif t < 0.82:
                c = highlight
            else:
                c = borda
            r = max(2, radius - i)
            draw.rounded_rectangle(
                [x1 + i, y1 + i, x2 - i, y2 - i],
                radius=r, outline=c, width=2)

    # 1. Loop exterior
    _metal_rect(ox1, oy1, ox2, oy2, out_r, wire)

    # 2. Loop interior
    _metal_rect(ix1, iy1, ix2, iy2, in_r, wire_in)

    # 3. Ponte topo-direito (liga os dois loops como um arame contínuo)
    br_y = iy1 + int(6 * s)
    br_h = wire
    br_x1 = ix2 - wire_in // 2 - int(2 * s)
    br_x2 = ox2 - wire // 2 + int(2 * s)
    for i in range(br_h):
        t = i / max(br_h - 1, 1)
        if t < 0.08:
            c = borda
        elif t < 0.28:
            c = sombra
        elif t < 0.55:
            c = principal
        elif t < 0.82:
            c = highlight
        else:
            c = borda
        draw.line([(br_x1, br_y + i), (br_x2, br_y + i)], fill=c, width=1)
    # Bordas superior/inferior da ponte
    draw.line([(br_x1, br_y), (br_x2, br_y)],
              fill=borda, width=int(2 * s))
    draw.line([(br_x1, br_y + br_h - 1), (br_x2, br_y + br_h - 1)],
              fill=borda, width=int(2 * s))

    # 4. Reflexo metálico (brilho na lateral esquerda)
    brilho = CORES['brilho_metalico']
    draw.line([ox1 + int(9 * s), oy1 + int(35 * s),
               ox1 + int(12 * s), oy1 + int(110 * s)],
              fill=brilho, width=int(5 * s))


def _desenhar_olhos(draw, cx, cy, escala=1.0, expressao="normal",
                    olhos_fechados=False, pupila_dx=0, pupila_dy=0):
    """Desenha os olhos com expressão — proporcionais ao corpo."""
    s = escala
    espacamento = int(50 * s)
    raio = int(22 * s)
    raio_pupila = int(10 * s)

    raio_mod = raio

    if expressao in ("surpreso", "chocado"):
        raio_mod = int(raio * 1.3)
        raio_pupila = int(raio_pupila * 0.75)
    elif expressao == "sarcastico":
        pupila_dy = pupila_dy - int(3 * s)
    elif expressao == "pensativo":
        pupila_dx = pupila_dx + int(6 * s)
        pupila_dy = pupila_dy - int(2 * s)

    for lado in (-1, 1):
        ox = cx + lado * espacamento // 2
        oy = cy

        if olhos_fechados or expressao == "rindo":
            # Arco feliz (olhos semicerrados)
            arc_r = int(raio * 0.85)
            draw.arc(
                [ox - arc_r, oy - int(3 * s), ox + arc_r, oy + int(10 * s)],
                start=200, end=340,
                fill=CORES['corpo_borda'], width=int(4 * s))
        else:
            # Fundo branco
            draw.ellipse(
                [ox - raio_mod, oy - raio_mod, ox + raio_mod, oy + raio_mod],
                fill=CORES['olho_branco'],
                outline=CORES['corpo_borda'],
                width=int(2 * s))
            # Pupila
            px = ox + pupila_dx
            py = oy + pupila_dy
            draw.ellipse(
                [px - raio_pupila, py - raio_pupila,
                 px + raio_pupila, py + raio_pupila],
                fill=CORES['pupila'])
            # Brilho (catchlight)
            br = int(4 * s)
            draw.ellipse(
                [px - int(4 * s) - br, py - int(5 * s) - br,
                 px - int(4 * s) + br, py - int(5 * s) + br],
                fill=CORES['pupila_brilho'])

        # Sobrancelhas (não desenhar quando rindo)
        if expressao != "rindo":
            sob_y = oy - raio_mod - int(8 * s)
            sob_w = int(18 * s)
            sob_h = int(3 * s)

            if expressao == "sarcastico":
                if lado == 1:
                    draw.line([ox - sob_w, sob_y + int(5 * s),
                               ox + sob_w, sob_y - int(5 * s)],
                              fill=CORES['sobrancelha'], width=sob_h)
                else:
                    draw.line([ox - sob_w, sob_y, ox + sob_w, sob_y],
                              fill=CORES['sobrancelha'], width=sob_h)
            elif expressao in ("surpreso", "chocado"):
                draw.line([ox - sob_w, sob_y - int(6 * s),
                           ox + sob_w, sob_y - int(6 * s)],
                          fill=CORES['sobrancelha'], width=sob_h)
            elif expressao == "pensativo":
                if lado == -1:
                    draw.line([ox - sob_w, sob_y - int(3 * s),
                               ox + sob_w, sob_y + int(3 * s)],
                              fill=CORES['sobrancelha'], width=sob_h)
                else:
                    draw.line([ox - sob_w, sob_y + int(3 * s),
                               ox + sob_w, sob_y - int(3 * s)],
                              fill=CORES['sobrancelha'], width=sob_h)
            else:
                draw.line([ox - sob_w, sob_y, ox + sob_w, sob_y],
                          fill=CORES['sobrancelha'], width=sob_h)


def _desenhar_boca(draw, cx, cy, escala=1.0, expressao="normal",
                   boca_aberta=False, boca_abertura=0.0):
    """Desenha a boca com expressão — proporcional ao corpo."""
    s = escala
    largura = int(32 * s)
    cor = CORES['boca']

    abertura = max(0.0, min(1.0, float(boca_abertura or 0.0)))
    if boca_aberta:
        abertura = max(abertura, 0.75)

    if abertura > 0.01:
        # Boca de fala contínua: abertura variável para parecer voz natural.
        raio_x = int((10 + 5 * abertura) * s)
        raio_y = int((3 + 11 * abertura) * s)
        draw.ellipse(
            [cx - raio_x, cy - raio_y, cx + raio_x, cy + raio_y],
            fill=(80, 85, 95, 255), outline=cor, width=int(3 * s))

        # Pequeno brilho superior para dar volume.
        hl_y = cy - int((raio_y * 0.45))
        draw.arc(
            [cx - int(raio_x * 0.7), hl_y - int(raio_y * 0.25),
             cx + int(raio_x * 0.7), hl_y + int(raio_y * 0.25)],
            start=200, end=340, fill=(150, 160, 175, 200), width=max(1, int(2 * s))
        )
        return

    if expressao == "normal":
        draw.arc(
            [cx - largura, cy - int(8 * s), cx + largura, cy + int(16 * s)],
            start=10, end=170, fill=cor, width=int(4 * s))

    elif expressao in ("surpreso", "chocado"):
        raio_x = int(14 * s) if expressao == "surpreso" else int(18 * s)
        raio_y = int(18 * s) if expressao == "surpreso" else int(22 * s)
        draw.ellipse(
            [cx - raio_x, cy - raio_y, cx + raio_x, cy + raio_y],
            outline=cor, width=int(3 * s))

    elif expressao == "sarcastico":
        pontos = [
            (cx - largura, cy + int(3 * s)),
            (cx - int(10 * s), cy),
            (cx + int(10 * s), cy - int(3 * s)),
            (cx + largura, cy - int(8 * s)),
        ]
        for i in range(len(pontos) - 1):
            draw.line([pontos[i], pontos[i + 1]], fill=cor, width=int(4 * s))

    elif expressao == "rindo":
        # Sorriso aberto — limpo, sem blush
        larg = int(largura * 1.15)
        draw.arc(
            [cx - larg, cy - int(10 * s), cx + larg, cy + int(20 * s)],
            start=0, end=180, fill=cor, width=int(4 * s))
        # Interior escuro da boca
        draw.pieslice(
            [cx - larg + int(3 * s), cy - int(3 * s),
             cx + larg - int(3 * s), cy + int(18 * s)],
            start=0, end=180, fill=(80, 85, 95, 255))

    elif expressao == "pensativo":
        draw.line([cx - int(16 * s), cy + int(2 * s),
                   cx + int(16 * s), cy - int(2 * s)],
                  fill=cor, width=int(4 * s))


def _desenhar_braco(draw, ombro_x, ombro_y, escala=1.0, angulo=0,
                    comprimento_rel=1.0, mao_aberta=True, lado=1):
    """
    Desenha braço articulado com cotovelo e mão.
    angulo: graus, 0=horizontal, 90=para baixo, -90=para cima
    lado: 1=direito, -1=esquerdo
    """
    s = escala
    comp = int(100 * s * comprimento_rel)
    rad = math.radians(angulo)

    # Ombro (articulação limpa)
    ombro_r = int(9 * s)
    draw.ellipse([ombro_x - ombro_r, ombro_y - ombro_r,
                  ombro_x + ombro_r, ombro_y + ombro_r],
                 fill=CORES['corpo_principal'], outline=CORES['corpo_borda'],
                 width=int(2 * s))
    # Highlight metálico
    hr = int(3 * s)
    draw.ellipse([ombro_x - hr - int(1 * s), ombro_y - hr - int(1 * s),
                  ombro_x + hr - int(1 * s), ombro_y + hr - int(1 * s)],
                 fill=CORES['corpo_highlight'])

    # Cotovelo
    cotovelo_x = ombro_x + lado * int(comp * 0.5 * math.cos(rad + lado * 0.3))
    cotovelo_y = ombro_y + int(comp * 0.5 * math.sin(rad))

    # Mão
    mao_x = ombro_x + lado * int(comp * math.cos(rad))
    mao_y = ombro_y + int(comp * math.sin(rad))

    espessura_braco = int(14 * s)

    # Braço superior (do ombro ao cotovelo)
    draw.line([ombro_x, ombro_y, cotovelo_x, cotovelo_y],
              fill=CORES['corpo_principal'], width=espessura_braco)
    draw.line([ombro_x, ombro_y, cotovelo_x, cotovelo_y],
              fill=CORES['corpo_borda'], width=int(3 * s))

    # Braço inferior
    draw.line([cotovelo_x, cotovelo_y, mao_x, mao_y],
              fill=CORES['corpo_principal'], width=espessura_braco)
    draw.line([cotovelo_x, cotovelo_y, mao_x, mao_y],
              fill=CORES['corpo_borda'], width=int(3 * s))

    # Cotovelo (articulação)
    cot_r = int(8 * s)
    draw.ellipse([cotovelo_x - cot_r, cotovelo_y - cot_r,
                  cotovelo_x + cot_r, cotovelo_y + cot_r],
                 fill=CORES['corpo_highlight'], outline=CORES['corpo_borda'],
                 width=int(2 * s))

    # Mão
    mao_r = int(16 * s) if mao_aberta else int(12 * s)
    draw.ellipse([mao_x - mao_r, mao_y - mao_r,
                  mao_x + mao_r, mao_y + mao_r],
                 fill=CORES['mao'], outline=CORES['mao_borda'],
                 width=int(3 * s))

    if mao_aberta:
        # Dedos
        dedo_comp = int(12 * s)
        for d_ang in [-25, 0, 25]:
            d_rad = math.radians(angulo + d_ang)
            dx = mao_x + lado * int(dedo_comp * math.cos(d_rad))
            dy = mao_y + int(dedo_comp * math.sin(d_rad))
            draw.line([mao_x, mao_y, dx, dy],
                      fill=CORES['mao_borda'], width=int(4 * s))

    return mao_x, mao_y


def _desenhar_pernas(draw, base_x, base_y, escala=1.0,
                     angulo_esq=10, angulo_dir=-10, step_offset=0):
    """
    Desenha pernas articuladas com pés.
    """
    s = escala
    comp_coxa = int(60 * s)
    comp_canela = int(50 * s)
    espessura = int(14 * s)

    for lado, angulo, offset_y in [(-1, angulo_esq, step_offset),
                                    (1, angulo_dir, -step_offset)]:
        hip_x = base_x + lado * int(25 * s)
        hip_y = base_y
        rad = math.radians(90 + angulo)

        joelho_x = hip_x + int(comp_coxa * math.cos(rad)) * lado
        joelho_y = hip_y + comp_coxa + offset_y

        pe_x = joelho_x + lado * int(10 * s)
        pe_y = joelho_y + comp_canela

        # Coxa
        draw.line([hip_x, hip_y, joelho_x, joelho_y],
                  fill=CORES['corpo_principal'], width=espessura)
        draw.line([hip_x, hip_y, joelho_x, joelho_y],
                  fill=CORES['corpo_borda'], width=int(3 * s))

        # Canela
        draw.line([joelho_x, joelho_y, pe_x, pe_y],
                  fill=CORES['corpo_principal'], width=espessura)
        draw.line([joelho_x, joelho_y, pe_x, pe_y],
                  fill=CORES['corpo_borda'], width=int(3 * s))

        # Joelho
        jr = int(7 * s)
        draw.ellipse([joelho_x - jr, joelho_y - jr,
                      joelho_x + jr, joelho_y + jr],
                     fill=CORES['corpo_highlight'], outline=CORES['corpo_borda'],
                     width=int(2 * s))

        # Pé
        pe_rx = int(22 * s)
        pe_ry = int(10 * s)
        draw.ellipse([pe_x - pe_rx, pe_y - pe_ry,
                      pe_x + pe_rx + lado * int(8 * s), pe_y + pe_ry],
                     fill=CORES['pe'], outline=CORES['pe_borda'],
                     width=int(3 * s))


# ════════════════════════════════════════════════════════════════════
#  ANIMAÇÕES — Poses predefinidas que variam por t ∈ [0, 1]
# ════════════════════════════════════════════════════════════════════

def _pose_idle(t):
    """Respiração natural."""
    breath = math.sin(t * 2 * math.pi) * 3
    return {
        'body_dy': breath, 'body_dx': 0,
        'braco_esq_angulo': 100 + math.sin(t * math.pi) * 5,
        'braco_dir_angulo': 100 - math.sin(t * math.pi) * 5,
        'mao_esq_aberta': False, 'mao_dir_aberta': False,
        'perna_esq': 5, 'perna_dir': -5,
        'step_offset': 0, 'pupila_dx': 0, 'pupila_dy': 0,
        'escala_extra': 1.0,
    }

def _pose_wave(t):
    """Acena com a mão."""
    wave = math.sin(t * 4 * math.pi) * 30
    return {
        'body_dy': 0, 'body_dx': 0,
        'braco_esq_angulo': 100,
        'braco_dir_angulo': -60 + wave,
        'mao_esq_aberta': False, 'mao_dir_aberta': True,
        'perna_esq': 5, 'perna_dir': -5,
        'step_offset': 0, 'pupila_dx': 0, 'pupila_dy': 0,
        'escala_extra': 1.0,
    }

def _pose_bounce(t):
    """Quica de excitação."""
    b = abs(math.sin(t * 3 * math.pi)) * 25
    return {
        'body_dy': -b, 'body_dx': 0,
        'braco_esq_angulo': 30 - b,
        'braco_dir_angulo': 30 - b,
        'mao_esq_aberta': True, 'mao_dir_aberta': True,
        'perna_esq': 15 + b * 0.5, 'perna_dir': -15 - b * 0.5,
        'step_offset': b * 0.3, 'pupila_dx': 0, 'pupila_dy': 0,
        'escala_extra': 1.0 + b * 0.002,
    }

def _pose_dance(t):
    """Dança festiva."""
    sway = math.sin(t * 4 * math.pi) * 20
    jump = abs(math.sin(t * 6 * math.pi)) * 10
    return {
        'body_dy': jump, 'body_dx': sway,
        'braco_esq_angulo': 20 + math.sin(t * 4 * math.pi + 1) * 60,
        'braco_dir_angulo': 20 - math.sin(t * 4 * math.pi) * 60,
        'mao_esq_aberta': True, 'mao_dir_aberta': True,
        'perna_esq': 10 + sway * 0.5, 'perna_dir': -10 + sway * 0.5,
        'step_offset': jump * 0.8, 'pupila_dx': int(sway * 0.2), 'pupila_dy': 0,
        'escala_extra': 1.0,
    }

def _pose_point(t):
    """Aponta para o espectador."""
    ext = ease_out_back(min(t * 2, 1.0))
    return {
        'body_dy': 0, 'body_dx': 0,
        'braco_esq_angulo': 100,
        'braco_dir_angulo': 10 - 90 * ext,
        'braco_dir_comp': 0.8 + 0.4 * ext,
        'mao_esq_aberta': False, 'mao_dir_aberta': True,
        'perna_esq': 5, 'perna_dir': -5,
        'step_offset': 0, 'pupila_dx': 0, 'pupila_dy': 0,
        'escala_extra': 1.0,
    }

def _pose_shrug(t):
    """Encolhe ombros — "sei lá"."""
    up = ease_out_elastic(min(t * 2, 1.0))
    hold = 1.0 if t > 0.3 else up
    drop = max(0, (t - 0.7) / 0.3) if t > 0.7 else 0
    val = hold * (1 - drop)
    return {
        'body_dy': -5 * val, 'body_dx': 0,
        'braco_esq_angulo': 60 - 80 * val,
        'braco_dir_angulo': 60 - 80 * val,
        'mao_esq_aberta': True, 'mao_dir_aberta': True,
        'perna_esq': 5, 'perna_dir': -5,
        'step_offset': 0, 'pupila_dx': int(8 * val), 'pupila_dy': int(-5 * val),
        'escala_extra': 1.0,
    }

def _pose_facepalm(t):
    """Facepalm."""
    reach = ease_in_out_cubic(min(t * 2.5, 1.0))
    hold = 1.0 if t < 0.8 else max(0, (1.0 - t) / 0.2)
    val = reach * hold
    return {
        'body_dy': 5 * val, 'body_dx': 0,
        'braco_esq_angulo': 100,
        'braco_dir_angulo': 100 - 200 * val,
        'mao_esq_aberta': False, 'mao_dir_aberta': False,
        'perna_esq': 5, 'perna_dir': -5,
        'step_offset': 0, 'pupila_dx': 0, 'pupila_dy': int(5 * val),
        'escala_extra': 1.0,
    }

def _pose_lean_in(t):
    """Inclina para a frente (contar segredo)."""
    lean = ease_in_out_cubic(min(t * 2, 1.0))
    hold = lean if t < 0.6 else lean * max(0, (1.0 - t) / 0.4)
    return {
        'body_dy': 10 * hold, 'body_dx': -15 * hold,
        'braco_esq_angulo': 80,
        'braco_dir_angulo': 80 - 30 * hold,
        'mao_esq_aberta': False, 'mao_dir_aberta': hold > 0.5,
        'perna_esq': 5 + 10 * hold, 'perna_dir': -5,
        'step_offset': 0, 'pupila_dx': int(-10 * hold), 'pupila_dy': 0,
        'escala_extra': 1.0 + 0.05 * hold,
    }

def _pose_celebrate(t):
    """Celebração (braços no ar)."""
    jump = abs(math.sin(t * 4 * math.pi)) * 30
    return {
        'body_dy': -jump, 'body_dx': 0,
        'braco_esq_angulo': -70 + math.sin(t * 6 * math.pi) * 20,
        'braco_dir_angulo': -70 - math.sin(t * 6 * math.pi) * 20,
        'mao_esq_aberta': True, 'mao_dir_aberta': True,
        'perna_esq': 20 + jump * 0.3, 'perna_dir': -20 - jump * 0.3,
        'step_offset': jump * 0.4, 'pupila_dx': 0, 'pupila_dy': 0,
        'escala_extra': 1.0,
    }

def _pose_think(t):
    """Pensativo (mão no queixo)."""
    reach = ease_in_out_cubic(min(t * 3, 1.0))
    return {
        'body_dy': 0, 'body_dx': 0,
        'braco_esq_angulo': 100,
        'braco_dir_angulo': 120 - 170 * reach,
        'braco_dir_comp': 0.6,
        'mao_esq_aberta': False, 'mao_dir_aberta': False,
        'perna_esq': 5, 'perna_dir': -5,
        'step_offset': 0, 'pupila_dx': int(10 * reach), 'pupila_dy': int(-12 * reach),
        'escala_extra': 1.0,
    }

def _pose_peek(t):
    """Espreita pelo canto."""
    slide = ease_out_back(min(t * 2, 1.0))
    hold = slide if t < 0.7 else slide * max(0, (1 - t) / 0.3)
    return {
        'body_dy': 0, 'body_dx': 200 * (1 - hold),
        'braco_esq_angulo': 80,
        'braco_dir_angulo': 40 - 30 * hold,
        'mao_esq_aberta': False, 'mao_dir_aberta': hold > 0.3,
        'perna_esq': 5, 'perna_dir': -5,
        'step_offset': 0, 'pupila_dx': int(-15 * hold), 'pupila_dy': 0,
        'escala_extra': 0.7 + 0.3 * hold,
    }

def _pose_nod(t):
    """Acena que sim (head nod)."""
    nod = math.sin(t * 6 * math.pi) * 8
    return {
        'body_dy': nod, 'body_dx': 0,
        'braco_esq_angulo': 100, 'braco_dir_angulo': 100,
        'mao_esq_aberta': False, 'mao_dir_aberta': False,
        'perna_esq': 5, 'perna_dir': -5,
        'step_offset': 0, 'pupila_dx': 0, 'pupila_dy': int(nod * 0.3),
        'escala_extra': 1.0,
    }

def _pose_headshake(t):
    """Abana a cabeça que não."""
    shake = math.sin(t * 8 * math.pi) * 15
    return {
        'body_dy': 0, 'body_dx': shake,
        'braco_esq_angulo': 100, 'braco_dir_angulo': 100,
        'mao_esq_aberta': False, 'mao_dir_aberta': False,
        'perna_esq': 5, 'perna_dir': -5,
        'step_offset': 0, 'pupila_dx': int(shake * 0.3), 'pupila_dy': 0,
        'escala_extra': 1.0,
    }


ANIMACOES = {
    'idle': _pose_idle,
    'wave': _pose_wave,
    'bounce': _pose_bounce,
    'dance': _pose_dance,
    'point': _pose_point,
    'shrug': _pose_shrug,
    'facepalm': _pose_facepalm,
    'lean_in': _pose_lean_in,
    'celebrate': _pose_celebrate,
    'think': _pose_think,
    'peek': _pose_peek,
    'nod': _pose_nod,
    'headshake': _pose_headshake,
}


# ════════════════════════════════════════════════════════════════════
#  TRANSIÇÕES — Entrada/saída clean
# ════════════════════════════════════════════════════════════════════

def _transicao_slide_in_right(t, target_x, target_y, canvas_w):
    progress = ease_out_back(t)
    start_x = canvas_w + 200
    return {
        'x': start_x + (target_x - start_x) * progress,
        'y': target_y,
        'alpha': min(1.0, t * 3),
        'escala': 0.5 + 0.5 * progress,
    }

def _transicao_slide_out_right(t, current_x, current_y, canvas_w):
    progress = ease_in_out_cubic(t)
    end_x = canvas_w + 200
    return {
        'x': current_x + (end_x - current_x) * progress,
        'y': current_y,
        'alpha': max(0, 1.0 - t * 2),
        'escala': 1.0 - 0.5 * progress,
    }

def _transicao_bounce_in(t, target_x, target_y):
    progress = ease_out_bounce(t)
    start_y = -300
    return {
        'x': target_x,
        'y': start_y + (target_y - start_y) * progress,
        'alpha': min(1.0, t * 2),
        'escala': 0.8 + 0.2 * ease_out_elastic(t),
    }

def _transicao_pop_in(t, target_x, target_y):
    progress = ease_out_elastic(t)
    return {
        'x': target_x,
        'y': target_y,
        'alpha': min(1.0, t * 4),
        'escala': progress,
    }

def _transicao_fade_out(t, current_x, current_y):
    progress = ease_in_out_cubic(t)
    return {
        'x': current_x,
        'y': current_y - 20 * progress,
        'alpha': 1.0 - progress,
        'escala': 1.0 - 0.3 * progress,
    }

def _transicao_slide_down_out(t, current_x, current_y, canvas_h):
    progress = ease_in_out_cubic(t)
    end_y = canvas_h + 200
    return {
        'x': current_x,
        'y': current_y + (end_y - current_y) * progress,
        'alpha': max(0, 1.0 - t * 1.5),
        'escala': 1.0 - 0.2 * progress,
    }


# ════════════════════════════════════════════════════════════════════
#  MOTOR DE RENDERIZAÇÃO — Frame a frame
# ════════════════════════════════════════════════════════════════════

def renderizar_clippy_frame(largura_canvas, altura_canvas, cx, cy,
                            escala=1.0, expressao="normal", pose=None,
                            alpha=1.0, olhos_fechados=False,
                            boca_aberta=False, boca_abertura=0.0):
    """
    Renderiza 1 frame completo da Clippy (corpo + braços + pernas + rosto).
    """
    if pose is None:
        pose = _pose_idle(0)

    img = Image.new('RGBA', (largura_canvas, altura_canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    s = escala * pose.get('escala_extra', 1.0)
    body_dx = pose.get('body_dx', 0)
    body_dy = pose.get('body_dy', 0)

    bcx = int(cx + body_dx)
    bcy = int(cy + body_dy)

    # Coordenadas (proporcionais ao corpo 130w × 280h)
    olho_cy = bcy - int(70 * s)
    boca_cy = bcy - int(15 * s)
    ombro_y = bcy + int(35 * s)
    base_y = bcy + int(140 * s)
    ombro_esq_x = bcx - int(63 * s)
    ombro_dir_x = bcx + int(63 * s)

    # 1. Pernas
    _desenhar_pernas(draw, bcx, base_y, s,
                     angulo_esq=pose.get('perna_esq', 5),
                     angulo_dir=pose.get('perna_dir', -5),
                     step_offset=int(pose.get('step_offset', 0)))

    # 2. Braço esquerdo (atrás)
    _desenhar_braco(draw, ombro_esq_x, ombro_y, s,
                    angulo=pose.get('braco_esq_angulo', 100),
                    comprimento_rel=pose.get('braco_esq_comp', 1.0),
                    mao_aberta=pose.get('mao_esq_aberta', False),
                    lado=-1)

    # 3. Corpo
    _desenhar_corpo_clippy(draw, bcx, bcy, s)

    # 4. Braço direito (frente)
    _desenhar_braco(draw, ombro_dir_x, ombro_y, s,
                    angulo=pose.get('braco_dir_angulo', 100),
                    comprimento_rel=pose.get('braco_dir_comp', 1.0),
                    mao_aberta=pose.get('mao_dir_aberta', False),
                    lado=1)

    # 5. Olhos
    _desenhar_olhos(draw, bcx, olho_cy, s, expressao,
                    olhos_fechados=olhos_fechados,
                    pupila_dx=int(pose.get('pupila_dx', 0) * s),
                    pupila_dy=int(pose.get('pupila_dy', 0) * s))

    # 6. Boca
    _desenhar_boca(
        draw, bcx, boca_cy, s, expressao,
        boca_aberta=boca_aberta, boca_abertura=boca_abertura
    )

    # Alpha global
    if alpha < 1.0:
        r, g, b, a = img.split()
        a = a.point(lambda x: int(x * alpha))
        img = Image.merge('RGBA', (r, g, b, a))

    return img


def criar_personagem_clippy(largura=1080, altura=1920, pasta_saida="data",
                            expressao="normal", frame=0, animacao="idle",
                            posicao="centro"):
    """
    API retro-compatível: cria PNG estático da Clippy 3.0 com corpo completo.
    """
    os.makedirs(pasta_saida, exist_ok=True)

    nome = f"clippy_{expressao}"
    if frame > 0:
        nome += f"_frame{frame}"
    if animacao != "idle":
        nome += f"_{animacao}"
    caminho_png = os.path.join(pasta_saida, f"{nome}.png")

    if os.path.exists(caminho_png):
        return caminho_png

    if posicao == "direita":
        cx = int(largura * 0.75)
    elif posicao == "esquerda":
        cx = int(largura * 0.25)
    else:
        cx = largura // 2
    cy = altura // 2 - 100

    olhos_fechados = frame in [2, 3]

    anim_func = ANIMACOES.get(animacao, _pose_idle)
    t = (frame % 30) / 30.0
    pose = anim_func(t)

    img = renderizar_clippy_frame(
        largura, altura, cx, cy,
        escala=1.2, expressao=expressao, pose=pose,
        alpha=1.0, olhos_fechados=olhos_fechados
    )

    img.save(caminho_png, 'PNG')
    return caminho_png


# ════════════════════════════════════════════════════════════════════
#  SEQUÊNCIAS DE ANIMAÇÃO — Gera frames para vídeo
# ════════════════════════════════════════════════════════════════════

def gerar_sequencia_animacao(animacao, expressao, duracao, fps=30,
                             largura=400, altura=700, pasta_saida="data",
                             entrada="slide_in", saida="fade_out",
                             duracao_entrada=0.5, duracao_saida=0.4,
                             posicao_x=None, posicao_y=None):
    """
    Gera sequência de frames PNG: entrada + animação + saída.
    """
    os.makedirs(pasta_saida, exist_ok=True)
    total = int(duracao * fps)

    target_x = posicao_x or largura // 2
    target_y = posicao_y or altura // 2 - 50

    f_in = int(duracao_entrada * fps)
    f_out = int(duracao_saida * fps)
    f_anim = total - f_in - f_out

    anim_func = ANIMACOES.get(animacao, _pose_idle)
    paths = []

    blink_interval = int(2.5 * fps)
    blink_dur = 4

    for i in range(total):
        blink_pos = i % blink_interval
        olhos_fechados = blink_pos >= (blink_interval - blink_dur)

        if i < f_in:
            # ENTRADA
            t_e = i / max(f_in, 1)
            if entrada == "bounce_in":
                trans = _transicao_bounce_in(t_e, target_x, target_y)
            elif entrada == "pop_in":
                trans = _transicao_pop_in(t_e, target_x, target_y)
            else:
                trans = _transicao_slide_in_right(t_e, target_x, target_y, largura)

            cx, cy = int(trans['x']), int(trans['y'])
            alpha, escala = trans['alpha'], trans['escala']
            pose = anim_func(0)

        elif i >= total - f_out:
            # SAÍDA
            t_s = (i - (total - f_out)) / max(f_out, 1)
            if saida == "slide_out":
                trans = _transicao_slide_out_right(t_s, target_x, target_y, largura)
            elif saida == "slide_down":
                trans = _transicao_slide_down_out(t_s, target_x, target_y, altura)
            else:
                trans = _transicao_fade_out(t_s, target_x, target_y)

            cx, cy = int(trans['x']), int(trans['y'])
            alpha, escala = trans['alpha'], trans['escala']
            pose = anim_func(1.0)

        else:
            # ANIMAÇÃO PRINCIPAL
            t_a = (i - f_in) / max(f_anim, 1)
            cx, cy = target_x, target_y
            alpha, escala = 1.0, 1.0
            pose = anim_func(t_a)

        frame_img = renderizar_clippy_frame(
            largura, altura, cx, cy,
            escala=escala * 0.9, expressao=expressao, pose=pose,
            alpha=alpha, olhos_fechados=olhos_fechados
        )

        fp = os.path.join(pasta_saida, f"clippy_seq_{i:04d}.png")
        frame_img.save(fp, 'PNG')
        paths.append(fp)

    return paths


def criar_clippy_animada(expressao="normal", pasta_saida="data", fps=30,
                         duracao=2.0, animacao="idle", entrada="slide_in",
                         saida="fade_out"):
    """
    Cria vídeo animado da Clippy com entrada/saída profissional.
    """
    frames = gerar_sequencia_animacao(
        animacao=animacao, expressao=expressao, duracao=duracao, fps=fps,
        largura=400, altura=700, pasta_saida=pasta_saida,
        entrada=entrada, saida=saida,
        duracao_entrada=0.5, duracao_saida=0.4
    )

    if not frames:
        return None

    caminho_video = os.path.join(pasta_saida, f"clippy_{expressao}_{animacao}_animado.mp4")

    lista_path = os.path.join(pasta_saida, "frames_list_temp.txt")
    with open(lista_path, 'w', encoding='utf-8') as f:
        for fp in frames:
            f.write(f"file '{os.path.abspath(fp)}'\n")
            f.write(f"duration {1 / fps}\n")
        f.write(f"file '{os.path.abspath(frames[-1])}'\n")

    try:
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', lista_path,
            '-pix_fmt', 'yuv420p', '-c:v', 'libx264',
            '-preset', 'fast', '-crf', '18', '-movflags', '+faststart',
            caminho_video
        ]
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        _limpar_temp(lista_path, frames)

        if resultado.returncode == 0 and os.path.exists(caminho_video):
            return caminho_video
        else:
            print(f"⚠️ Erro animação: {resultado.stderr[:300]}")
            return None
    except Exception as e:
        print(f"⚠️ Erro animação: {e}")
        _limpar_temp(lista_path, frames)
        return None


def _limpar_temp(lista_path, frames):
    for f in [lista_path] + (frames or []):
        if f and os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass


def _escape_drawtext_text(texto):
    """Escapa texto para uso seguro em drawtext=text='...' do FFmpeg."""
    if texto is None:
        return ""
    out = str(texto)
    out = out.replace('\\', '\\\\')
    out = out.replace("'", "'\\''")
    out = out.replace(':', '\\:')
    out = out.replace('[', '\\[').replace(']', '\\]')
    out = out.replace('%', '\\%').replace(',', '\\,')
    out = out.replace('\n', ' ')
    return out


# ════════════════════════════════════════════════════════════════════
#  AI — Hooks e Intervenções (prompts otimizados)
# ════════════════════════════════════════════════════════════════════

def _chamar_ollama(prompt, temperature=0.9, max_tokens=80):
    """Tenta vários modelos Ollama."""
    import ollama
    modelos = ['llama3.2', 'llama3.1', 'llama3', 'llama2', 'mistral',
               'gemma2', 'phi3', 'qwen2']
    for modelo in modelos:
        try:
            resp = ollama.chat(
                model=modelo,
                messages=[{'role': 'user', 'content': prompt}],
                options={'temperature': temperature, 'num_predict': max_tokens}
            )
            return resp['message']['content'].strip()
        except Exception as e:
            if "not found" in str(e).lower():
                continue
            raise
    raise RuntimeError("Nenhum modelo Ollama disponível")


def gerar_hook_com_ai(titulo_clip, razao_clip, transcricao_preview=""):
    """Gera hook viral curto com personalidade da Clippy."""
    prompt = f"""Tu és a Clippy — um clipe de papel animado, sarcástico mas simpático, que apresenta vídeos virais. A tua personalidade é:
- Direta e confiante (nunca hesitas)
- Um bocadinho atrevida e provocadora
- Fazes as pessoas querer ver o vídeo TODO
- Usas linguagem informal portuguesa (PT-PT natural, como se falasses com um amigo)

Cria UM hook curtíssimo (máximo 100 caracteres) para este vídeo:

TÍTULO: {titulo_clip}
RAZÃO VIRAL: {razao_clip}
PRIMEIRAS PALAVRAS: {transcricao_preview[:100] if transcricao_preview else "N/A"}

ESTILOS que funcionam (escolhe o melhor para o conteúdo):
1. CURIOSIDADE: "Espera até veres o que acontece aos 0:42..."
2. DESAFIO: "Aposto que não aguentas ver até ao fim"
3. CHOQUE: "Isto devia ser ilegal, mas não é"
4. SEGREDO: "Ninguém devia saber disto, mas..."
5. PROVOCAÇÃO: "Se achas que sabes tudo sobre X, vê isto"
6. RELATABLE: "Quando tu fazes [coisa] e dá nisto..."

REGRAS:
- Máximo 100 caracteres (conta cada letra!)
- 1 frase só, sem emojis, sem aspas
- TEM de criar vontade irresistível de ver o vídeo
- Português europeu natural (não brasileiro)
- Evita clichés como "não vais acreditar"

Escreve APENAS o hook:"""

    try:
        hook = _chamar_ollama(prompt, temperature=0.95, max_tokens=60)
        hook = hook.strip('"\'').split('\n')[0].strip()
        if len(hook) > 120:
            hook = hook[:117] + "..."
        if len(hook) < 10:
            raise ValueError("Hook muito curto")
        return hook
    except Exception as e:
        print(f"⚠️ Erro hook: {e}")
        return random.choice([
            "Prepara-te, isto vai ser diferente",
            "Atenção ao que vem a seguir...",
            "Vê isto até ao fim, confia",
            "Nunca vi nada assim, a sério",
            "Isto muda tudo o que pensavas",
        ])


def gerar_intervencoes_satiricas(titulo_clip, transcricao_completa, razao_clip):
    """
    Gera intervenções satíricas com animação adequada.
    """
    prompt = f"""Tu és a Clippy — um clipe de papel animado que comenta vídeos com humor. A tua personalidade:
- Sarcástica tipo best friend que goza contigo mas com carinho
- Dizes o que toda a gente pensa mas ninguém diz
- Reages de forma exagerada a coisas óbvias
- Usas expressões portuguesas (PT-PT): "fogo", "ó meu", "ya claro", "tá bom tá"

Analisa esta transcrição e encontra 1-3 momentos perfeitos para intervir:

TÍTULO: {titulo_clip}
RAZÃO VIRAL: {razao_clip}
TRANSCRIÇÃO:
{transcricao_completa[:2000]}

TIPOS DE INTERVENÇÃO (escolhe o melhor para cada momento):
1. REAÇÃO — responde ao que foi dito ("Ya, porque isso é super fácil...")
2. PENSAMENTO — diz o que o espectador pensa ("Estás a pensar o mesmo que eu?")
3. CORREÇÃO — corrige com humor ("Tecnicamente isso não é bem assim mas ok")
4. ALERTA — avisa sobre algo ("Atenção que isto vai ficar bom")
5. GOZO — goza levemente ("Ah sim, conta-me mais...")

FORMATO JSON obrigatório:
[
  {{
    "timestamp_frase": "frase exata da transcrição onde intervir",
    "comentario": "texto curto que a Clippy diz (máx 70 chars)",
    "expressao": "sarcastico|rindo|surpreso|pensativo|chocado",
    "animacao": "shrug|facepalm|point|lean_in|wave|bounce|think|nod|headshake"
  }}
]

REGRAS:
- Máximo 70 caracteres por comentário
- Tem de ser ENGRAÇADO mas nunca ofensivo
- Cada intervenção deve ter animação diferente
- Escolhe momentos que realmente merecem reação
- Humor português natural (gozo entre amigos)

Retorna APENAS o JSON:"""

    try:
        resposta = _chamar_ollama(prompt, temperature=0.85, max_tokens=400)
        json_match = re.search(r'\[.*\]', resposta, re.DOTALL)
        if not json_match:
            return []

        intervencoes = json.loads(json_match.group(0))[:3]

        validas = []
        for interv in intervencoes:
            comentario = interv.get('comentario', '')
            if not comentario or not interv.get('timestamp_frase'):
                continue
            comentario = re.sub(r'[^\w\s\.,!?\-\'\"]', '', comentario)
            if len(comentario) > 70:
                comentario = comentario[:67] + "..."
            interv['comentario'] = comentario
            if interv.get('expressao') not in ('sarcastico', 'rindo', 'surpreso',
                                                'pensativo', 'chocado', 'normal'):
                interv['expressao'] = 'sarcastico'
            if interv.get('animacao') not in ANIMACOES:
                interv['animacao'] = random.choice(['shrug', 'point', 'lean_in', 'facepalm'])
            validas.append(interv)

        return validas
    except Exception as e:
        print(f"⚠️ Erro intervenções: {e}")
        return []


# ════════════════════════════════════════════════════════════════════
#  SÍNTESE DE VOZ — edge-tts com perfis por expressão
# ════════════════════════════════════════════════════════════════════

VOZ_PERFIS = {
    'normal':     {'rate': '+10%',  'pitch': '+3Hz',  'voz': 'pt-BR-FranciscaNeural'},
    'sarcastico': {'rate': '+5%',   'pitch': '-2Hz',  'voz': 'pt-BR-FranciscaNeural'},
    'surpreso':   {'rate': '+20%',  'pitch': '+10Hz', 'voz': 'pt-BR-FranciscaNeural'},
    'rindo':      {'rate': '+15%',  'pitch': '+8Hz',  'voz': 'pt-BR-FranciscaNeural'},
    'pensativo':  {'rate': '-5%',   'pitch': '-3Hz',  'voz': 'pt-BR-FranciscaNeural'},
    'chocado':    {'rate': '+25%',  'pitch': '+12Hz', 'voz': 'pt-BR-FranciscaNeural'},
}


def sintetizar_voz_hook(texto_hook, caminho_saida="data/clippy_voz.mp3",
                        expressao="normal"):
    """Sintetiza voz com edge-tts, ajuste por expressão."""
    os.makedirs(os.path.dirname(caminho_saida) or ".", exist_ok=True)
    try:
        import edge_tts
        perfil = VOZ_PERFIS.get(expressao, VOZ_PERFIS['normal'])

        async def _synth():
            comm = edge_tts.Communicate(
                texto_hook, perfil['voz'],
                rate=perfil['rate'], pitch=perfil['pitch']
            )
            await comm.save(caminho_saida)

        asyncio.run(_synth())
        if os.path.exists(caminho_saida) and os.path.getsize(caminho_saida) > 500:
            return caminho_saida
        return None
    except ImportError:
        print("⚠️ edge-tts não instalado. pip install edge-tts")
        return None
    except Exception as e:
        print(f"⚠️ Erro TTS: {e}")
        return None


# ════════════════════════════════════════════════════════════════════
#  INTRO — Entrada profissional com animação
# ════════════════════════════════════════════════════════════════════

def obter_duracao_audio(caminho_audio):
    try:
        cmd = ['ffprobe', '-v', 'error',
               '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1',
               caminho_audio]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            return float(res.stdout.strip())
    except Exception:
        pass
    return 3.0


def _obter_video_props(caminho):
    """Retorna (fps, width, height) do vídeo via ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate',
            '-of', 'json', caminho
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            info = json.loads(res.stdout)
            stream = info['streams'][0]
            w = int(stream['width'])
            h = int(stream['height'])
            rfr = stream['r_frame_rate']
            num, den = rfr.split('/')
            fps = round(int(num) / int(den))
            return fps, w, h
    except Exception:
        pass
    return 30, 1080, 1920


def _gerar_frames_clippy_falando(duracao, fps, duracao_audio,
                                 largura=400, altura=700,
                                 pasta_saida="data"):
    """
    Gera frames com Clippy: entrada bounce → boca a mexer → saída fade.
    Retorna lista de paths PNG.
    """
    total = int(duracao * fps)
    paths = []

    f_entrada = int(0.6 * fps)
    f_audio_start = int(0.4 * fps)
    f_audio_end = int((0.4 + duracao_audio) * fps)
    f_saida = int((duracao - 0.5) * fps)

    anim_func = ANIMACOES.get('idle', _pose_idle)
    blink_interval = int(2.5 * fps)
    blink_dur = 4

    cx = largura // 2
    cy = altura // 2 - 50

    for i in range(total):
        olhos_fechados = (i % blink_interval) >= (blink_interval - blink_dur)

        # Boca: abertura contínua (evita efeito robótico abre/fecha).
        boca_aberta = False
        boca_abertura = 0.0
        if f_audio_start <= i <= f_audio_end:
            boca_aberta = True
            fase = (i - f_audio_start)
            onda = 0.5 + 0.5 * math.sin(fase * 0.85)
            boca_abertura = 0.22 + 0.78 * onda

            # Micro-pauses periódicas para ritmo de fala natural.
            if (fase // max(1, int(0.33 * fps))) % 3 == 2:
                boca_abertura *= 0.4

        # Animação de entrada/saída
        if i < f_entrada:
            t_e = i / max(f_entrada, 1)
            progress = ease_out_back(t_e)
            alpha = min(1.0, t_e * 3)
            escala = 0.5 + 0.5 * progress
            offset_x = int((1.0 - progress) * largura * 0.5)
        elif i >= f_saida:
            t_s = (i - f_saida) / max(total - f_saida, 1)
            alpha = max(0, 1.0 - t_s * 2)
            escala = 1.0 - 0.3 * t_s
            offset_x = int(t_s * largura * 0.3)
        else:
            alpha = 1.0
            escala = 1.0
            offset_x = 0

        t_a = i / max(total, 1)
        pose = anim_func(t_a)

        img = renderizar_clippy_frame(
            largura, altura, cx + offset_x, cy,
            escala=0.9 * escala, expressao="normal", pose=pose,
            alpha=alpha, olhos_fechados=olhos_fechados,
            boca_aberta=boca_aberta,
            boca_abertura=boca_abertura
        )

        fp = os.path.join(pasta_saida, f"clippy_seq_{i:04d}.png")
        img.save(fp, 'PNG')
        paths.append(fp)

    return paths


def criar_intro_clippy(caminho_video_base, texto_hook, caminho_saida,
                       duracao_intro=4.0, fade_out_duracao=0.5):
    """
    Intro clean:
      • Fundo = primeiro frame do vídeo blurrado (paused)
      • Clippy no canto inferior direito com boca a mexer
      • Hook texto + áudio TTS
      • Saída smooth + output fps/resolução igual ao vídeo original
    """
    try:
        # Probe vídeo para matching perfeito
        v_fps, v_w, v_h = _obter_video_props(caminho_video_base)

        audio_hook = sintetizar_voz_hook(texto_hook, "data/clippy_voz_temp.mp3")
        if not audio_hook:
            print("⚠️ TTS falhou, intro cancelada")
            return None

        duracao_audio = obter_duracao_audio(audio_hook)
        duracao_intro = max(duracao_intro, duracao_audio + 1.0)
        total_frames = int(duracao_intro * v_fps)
        dur_video = max(0.2, obter_duracao_audio(caminho_video_base))
        t_bg = max(0.20, min(1.80, dur_video * 0.35))
        t_bg = min(t_bg, max(0.20, dur_video - 0.08))
        t_bg_end = min(dur_video, t_bg + 0.04)

        # Gera Clippy frames com boca a mexer
        print(f"     Gerando {total_frames} frames de animação (fala)...")
        frames = _gerar_frames_clippy_falando(
            duracao=duracao_intro, fps=v_fps,
            duracao_audio=duracao_audio,
            largura=400, altura=700, pasta_saida="data"
        )

        if not frames:
            print("⚠️ Falha ao gerar frames Clippy")
            return None

        # Texto no mesmo estilo visual das legendas ASS principais.
        texto_escapado = _escape_drawtext_text((texto_hook or '').upper())
        hook_fontsize = max(52, int(v_h * (100 / 1920.0)))

        t_text_in = 0.5
        t_text_out = duracao_intro - fade_out_duracao - 0.3

        # ── FILTER COMPLEX ─────────────────────────────────────────
        filtro = (
            # BG: frame após alguns instantes (evita primeiros frames pretos).
            f"[0:v]trim=start={t_bg:.2f}:end={t_bg_end:.2f},setpts=0,"
            f"scale={v_w}:{v_h}:force_original_aspect_ratio=decrease,"
            f"pad={v_w}:{v_h}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"boxblur=20:5,"
            f"eq=brightness=-0.12:saturation=0.7,"
            f"loop=loop={total_frames + 10}:size=1:start=0,"
            f"setpts=N/{v_fps}/TB,"
            f"trim=duration={duracao_intro:.3f},setpts=PTS-STARTPTS[bg];"

            # Clippy PNG (alpha preservado), escala para caber no canto
            f"[1:v]format=rgba,"
            f"scale=430:-1:flags=lanczos[clippy];"

            # Overlay Clippy no canto inferior direito
            f"[bg][clippy]overlay="
            f"W-w-30:H-h-40:"
            f"format=auto:eof_action=pass:shortest=0[com_c];"

            # Texto hook acima da Clippy + fades
            f"[com_c]drawtext=text='{texto_escapado}':"
            f"fontcolor=white:fontsize={hook_fontsize}:"
            f"borderw=5:bordercolor=black@1.0:"
            f"x=(w-text_w)/2:y=h*0.78:"
            f"shadowcolor=black@0.85:shadowx=3:shadowy=3:"
            f"enable='between(t,{t_text_in:.2f},{t_text_out:.2f})':"
            f"alpha='if(lt(t,{t_text_in + 0.3:.2f}),(t-{t_text_in:.2f})/0.3,"
            f"if(gt(t,{t_text_out - 0.3:.2f}),({t_text_out:.2f}-t)/0.3,1))',"
            f"fade=t=in:st=0:d=0.4,"
            f"fade=t=out:st={duracao_intro - fade_out_duracao:.3f}:"
            f"d={fade_out_duracao:.3f}[vfinal]"
        )

        seq_pattern = os.path.join("data", "clippy_seq_%04d.png")

        cmd = [
            'ffmpeg', '-y',
            '-i', caminho_video_base,
            '-framerate', str(v_fps), '-i', seq_pattern,
            '-i', audio_hook,
            '-filter_complex', filtro,
            '-map', '[vfinal]', '-map', '2:a',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-pix_fmt', 'yuv420p', '-r', str(v_fps),
            '-c:a', 'aac', '-b:a', '192k',
            '-t', f'{duracao_intro:.3f}',
            '-movflags', '+faststart',
            caminho_saida
        ]

        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        _limpar_temp(None, frames)
        for tmp in [audio_hook]:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

        if resultado.returncode == 0 and os.path.exists(caminho_saida):
            print(f"✅ Intro Clippy criada: {caminho_saida}")
            return caminho_saida
        else:
            print(f"⚠️ Erro intro: {resultado.stderr[:400]}")
            return None

    except Exception as e:
        print(f"⚠️ Erro intro: {e}")
        return None


# ════════════════════════════════════════════════════════════════════
#  INTERVENÇÕES — Overlay animado durante o vídeo
# ════════════════════════════════════════════════════════════════════

def inserir_intervencoes_clippy(caminho_video, intervencoes, segmentos_whisper,
                                caminho_saida, inicio_clip=0):
    """
    Insere intervenções animadas da Clippy durante o vídeo com
    entradas/saídas clean e áudio por expressão.
    """
    if not intervencoes or not segmentos_whisper:
        return caminho_video

    try:
        print(f"  🎭 Inserindo {len(intervencoes)} intervenções satíricas...")

        overlays = []
        for idx, interv in enumerate(intervencoes):
            timestamp_frase = interv.get('timestamp_frase', '').lower()
            comentario = interv.get('comentario', '')
            expressao = interv.get('expressao', 'sarcastico')
            animacao = interv.get('animacao', 'shrug')

            if not timestamp_frase or not comentario:
                continue

            ts = None
            for seg in segmentos_whisper:
                if timestamp_frase[:30] in seg.get('texto', '').lower():
                    ts = seg.get('inicio', 0) - inicio_clip
                    break

            if ts is None or ts < 0:
                continue

            img = criar_personagem_clippy(
                expressao=expressao, animacao=animacao, posicao="direita",
                largura=400, altura=700
            )

            audio_path = f"data/clippy_interv_{idx}.mp3"
            audio = sintetizar_voz_hook(comentario, audio_path, expressao=expressao)
            dur = obter_duracao_audio(audio) if audio else 2.5

            overlays.append({
                'timestamp': ts, 'duracao': dur + 0.8,
                'imagem': img, 'audio': audio, 'texto': comentario, 'idx': idx,
            })

        if not overlays:
            print("     Nenhuma intervenção válida")
            return caminho_video

        overlays.sort(key=lambda x: x['timestamp'])

        # FFmpeg filter
        filtros = []
        corrente = "0:v"
        input_idx = 1

        for idx, ov in enumerate(overlays):
            inicio = ov['timestamp']
            fim = inicio + ov['duracao']
            texto_esc = _escape_drawtext_text(str(ov['texto']).upper())

            fade_in = 0.3
            fade_out_st = ov['duracao'] - 0.3

            filtros.append(
                f"[{input_idx}:v]format=rgba,"
                f"scale=380:665:force_original_aspect_ratio=decrease,"
                f"pad=380:665:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
                f"fade=t=in:st=0:d={fade_in}:alpha=1,"
                f"fade=t=out:st={fade_out_st}:d=0.3:alpha=1"
                f"[ov{idx}]"
            )

            filtros.append(
                f"[{corrente}][ov{idx}]overlay="
                f"x=W-w-20:y=H-h-30:"
                f"format=auto:"
                f"enable='between(t,{inicio:.2f},{fim:.2f})':"
                f"eof_action=pass[v{idx}]"
            )

            t_inicio = inicio + 0.3
            t_fim = fim - 0.3
            filtros.append(
                f"[v{idx}]drawtext=text='{texto_esc}':"
                f"fontcolor=white:fontsize=90:"
                f"borderw=5:bordercolor=black@1.0:"
                f"x=(W-text_w)/2:y=H-280:"
                f"shadowcolor=black@0.85:shadowx=3:shadowy=3:"
                f"enable='between(t,{t_inicio:.2f},{t_fim:.2f})'"
                f"[vt{idx}]"
            )

            corrente = f"vt{idx}"
            input_idx += 1

        # Mistura áudio base + vozes das intervenções no timestamp correto.
        filtros.append(
            "[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            "aresample=48000[abase]"
        )

        labels_audio = []
        audio_input_start = 1 + len(overlays)
        audio_cursor = 0
        for idx, ov in enumerate(overlays):
            if not ov.get('audio'):
                continue
            aidx = audio_input_start + audio_cursor
            audio_cursor += 1
            delay_ms = int(max(0.0, ov['timestamp']) * 1000)
            label = f"ac{idx}"
            filtros.append(
                f"[{aidx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                f"aresample=48000,adelay={delay_ms}|{delay_ms},volume=1.25[{label}]"
            )
            labels_audio.append(label)

        if labels_audio:
            chain = "[abase]" + "".join(f"[{lb}]" for lb in labels_audio)
            filtros.append(
                f"{chain}amix=inputs={1 + len(labels_audio)}:normalize=0:dropout_transition=0,"
                f"alimiter=limit=0.95[aout]"
            )

        filtro_complexo = ";".join(filtros)

        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', caminho_video]
        for ov in overlays:
            cmd.extend(['-loop', '1', '-i', ov['imagem']])

        audios = [ov['audio'] for ov in overlays if ov['audio']]
        for a in audios:
            cmd.extend(['-i', a])

        cmd.extend(['-filter_complex', filtro_complexo])
        if labels_audio:
            cmd.extend(['-map', f'[{corrente}]', '-map', '[aout]'])
        else:
            cmd.extend(['-map', f'[{corrente}]', '-map', '0:a'])

        cmd.extend([
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            caminho_saida
        ])

        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        for ov in overlays:
            if ov.get('audio') and os.path.exists(ov['audio']):
                try:
                    os.remove(ov['audio'])
                except OSError:
                    pass

        if resultado.returncode == 0 and os.path.exists(caminho_saida):
            print(f"     ✅ Intervenções inseridas!")
            return caminho_saida
        else:
            print(f"     ⚠️ Falha: {resultado.stderr[:1200]}")
            return caminho_video

    except Exception as e:
        print(f"     ⚠️ Erro: {e}")
        return caminho_video


# ════════════════════════════════════════════════════════════════════
#  CONCATENAÇÃO
# ════════════════════════════════════════════════════════════════════

def concatenar_intro_com_video(caminho_intro, caminho_video, caminho_saida,
                               xfade_dur=0.6):
    """
    Concatena intro + vídeo com xfade suave (blur → vídeo nítido).
    Fallback: concat demuxer se xfade falhar.
    """
    try:
        # Alinha props para reduzir falhas no xfade/acrossfade.
        v_fps, v_w, v_h = _obter_video_props(caminho_video)

        # Obter duração da intro para calcular offset do xfade
        dur_intro = obter_duracao_audio(caminho_intro)  # funciona para vídeo também
        if not dur_intro or dur_intro < 1:
            dur_intro = 4.5
        offset = max(0.1, dur_intro - xfade_dur)

        # Método 1: xfade com transição suave (com normalização AV)
        filtro = (
            f"[0:v]fps={v_fps},scale={v_w}:{v_h}:flags=lanczos,"
            f"format=yuv420p,setsar=1,settb=AVTB,setpts=PTS-STARTPTS[v0];"
            f"[1:v]fps={v_fps},scale={v_w}:{v_h}:flags=lanczos,"
            f"format=yuv420p,setsar=1,settb=AVTB,setpts=PTS-STARTPTS[v1];"
            f"[v0][v1]xfade=transition=fade:duration={xfade_dur:.2f}"
            f":offset={offset:.2f}[v];"
            f"[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"aresample=48000,asetpts=PTS-STARTPTS[a0];"
            f"[1:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
            f"aresample=48000,asetpts=PTS-STARTPTS[a1];"
            f"[a0][a1]acrossfade=d={xfade_dur:.2f}:c1=tri:c2=tri[a]"
        )

        cmd_xfade = [
            'ffmpeg', '-y',
            '-i', caminho_intro, '-i', caminho_video,
            '-filter_complex', filtro,
            '-map', '[v]', '-map', '[a]',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-r', str(v_fps),
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart', caminho_saida
        ]
        resultado = subprocess.run(cmd_xfade, capture_output=True, text=True, timeout=180)

        if resultado.returncode == 0 and os.path.exists(caminho_saida) \
                and os.path.getsize(caminho_saida) > 5000:
            print(f"✅ Vídeo concatenado (xfade {xfade_dur:.1f}s): {caminho_saida}")
            return True
        else:
            print(f"     ⚠️ xfade stderr: {resultado.stderr[:350]}")

        # Método 2: fallback concat com re-encode (evita mismatch fps/codec)
        print(f"     ⚠️ xfade falhou, usando concat com re-encode...")
        lista_path = "data/concat_list_temp.txt"
        with open(lista_path, 'w', encoding='utf-8') as f:
            f.write(f"file '{os.path.abspath(caminho_intro)}'\n")
            f.write(f"file '{os.path.abspath(caminho_video)}'\n")

        cmd_concat = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', lista_path,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart', caminho_saida
        ]
        resultado2 = subprocess.run(cmd_concat, capture_output=True, text=True, timeout=180)

        if os.path.exists(lista_path):
            try:
                os.remove(lista_path)
            except OSError:
                pass

        if resultado2.returncode == 0 and os.path.exists(caminho_saida):
            print(f"✅ Vídeo concatenado (concat): {caminho_saida}")
            return True
        else:
            print(f"⚠️ Erro concat: {resultado2.stderr[:200]}")
            return False
    except Exception as e:
        print(f"⚠️ Erro concat: {e}")
        return False


# ════════════════════════════════════════════════════════════════════
#  MAIN — Teste standalone
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 Teste Clippy 3.0 — Ultra-Professional")
    print("=" * 50)

    # 1: Todas as expressões
    print("\n1. Expressões faciais (corpo completo)...")
    for expr in ("normal", "sarcastico", "surpreso", "rindo", "pensativo", "chocado"):
        path = criar_personagem_clippy(expressao=expr)
        size = os.path.getsize(path) / 1024
        print(f"   ✅ {expr}: {size:.1f} KB")

    # 2: Animação
    print("\n2. Animação wave com bounce_in...")
    vid = criar_clippy_animada(expressao="normal", animacao="wave", duracao=2.0,
                                entrada="slide_in", saida="fade_out")
    if vid:
        size = os.path.getsize(vid) / 1024 / 1024
        print(f"   ✅ {vid} ({size:.2f} MB)")

    # 3: Hook
    print("\n3. Hook AI...")
    hook = gerar_hook_com_ai("Segredo de produtividade", "Técnica revolucionária")
    print(f"   💬 '{hook}'")

    # 4: Voz
    print("\n4. Síntese de voz...")
    audio = sintetizar_voz_hook(hook, "data/teste_voz.mp3")
    if audio:
        print(f"   🔊 {audio}")

    print("\n✅ Clippy 3.0 operacional!")
