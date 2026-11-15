"""트리 본체: 눈, 줄기, 잎 글자 3,000개, 금색 나선 장식, 전구, 별, 좌하단 수치 표시.

핵심 원리: 글자마다 원뿔 위의 3D 좌표를 하나씩 갖고 있고, 매 프레임
(1) Y축으로 회전 -> (2) 화면 좌표로 투영 -> (3) 앞뒤 깊이에 따라 밝기를 정해 글자를 찍는다.
"""

import numpy as np
from PIL import Image, ImageDraw

from core import (CX, DIM, GOLD, PALETTE, R_BASE, SCENE_H, T_BUILD, T_STAR, TAU, TREE_H, W,
                  WHITE, Y_TOP, clamp01, ease, font, rng, shade)

N_LEAF, N_LIGHT, N_GARLAND, N_SNOW = 3000, 100, 420, 230
ROT_SPEED = 0.55   # 회전 속도(rad/s)
TILT = 0.16        # 위에서 살짝 내려다보는 정도: 앞쪽 글자를 아래로 내린다
_r = rng(7)


def profile(f):
    """높이 f(0=꼭대기, 1=바닥)에서의 반지름(0~1). 톱니 모양을 섞어 나무의 층을 만든다."""
    return f * (0.78 + 0.22 * ((f * 6) % 1))


def project(f, radius, phi, rot):
    """원뿔 위의 점(높이 f, 반지름, 각도 phi)을 rot만큼 돌려 화면 좌표와 깊이(앞=+1)로 바꾼다."""
    x = radius * np.cos(phi + rot)
    depth = radius * np.sin(phi + rot)
    return CX + x * R_BASE, Y_TOP + f * TREE_H + depth * R_BASE * TILT, depth


# ---- 잎 ----
leaf_f = np.sqrt(_r.uniform(0.001, 1, N_LEAF))          # sqrt: 넓은 아래쪽에 글자가 더 많이 깔린다
leaf_r = profile(leaf_f) * _r.uniform(0.5, 1, N_LEAF)   # 표면 안쪽까지 조금 채운다
leaf_phi = _r.uniform(0, TAU, N_LEAF)
leaf_ch = np.array(list("xo*#%&WM@+=-~^v"))[_r.integers(0, 15, N_LEAF)]
_mix = _r.uniform(0, 1, (N_LEAF, 1))
leaf_rgb = _mix * np.array([70, 215, 120]) + (1 - _mix) * np.array([20, 130, 95])
# 아래 글자부터 먼저 나타난다 (약간의 흔들림을 줘서 경계가 자연스럽게)
leaf_born = T_BUILD * 0.93 * (1 - leaf_f) + _r.uniform(0, 0.3, N_LEAF)

# ---- 전구 ----
light_f = np.sqrt(_r.uniform(0.03, 1, N_LIGHT))
light_r = profile(light_f) * 1.02
light_phi = _r.uniform(0, TAU, N_LIGHT)
light_ch = np.array(list("o0@O"))[_r.integers(0, 4, N_LIGHT)]
light_rgb = np.array(PALETTE)[_r.integers(0, len(PALETTE), N_LIGHT)]
light_on = T_BUILD - 1.0 + _r.uniform(0, 2.0, N_LIGHT)
light_spd, light_ph = _r.uniform(2, 6, N_LIGHT), _r.uniform(0, TAU, N_LIGHT)

# ---- 금색 나선 장식 ----
gar_f = np.linspace(0.08, 1.0, N_GARLAND)
gar_r = profile(gar_f) * 1.04
gar_phi = gar_f * 5 * TAU                                # 꼭대기에서 바닥까지 다섯 바퀴
gar_ch = np.array(list("~=*"))[_r.integers(0, 3, N_GARLAND)]

# ---- 눈 ----
snow_x, snow_y = _r.uniform(0, W, N_SNOW), _r.uniform(0, SCENE_H, N_SNOW)
snow_v, snow_k = _r.uniform(25, 90, N_SNOW), _r.uniform(0.35, 1.0, N_SNOW)
snow_ch = np.array(list("*+.·"))[_r.integers(0, 4, N_SNOW)]


def _star_cells(cols=17, rows=11, cw=8.4, lh=12):
    """별 모양을 작은 이미지에 그린 뒤 격자로 줄여, 칸마다 글자 하나로 바꾼다."""
    s = 8
    img = Image.new("L", (cols * s, rows * s), 0)
    cx, cy, ro, ri = cols * s / 2, rows * s * 0.54, 66, 27   # 바깥/안쪽 꼭짓점 반지름(px)
    pts = []
    for k in range(10):
        a, rad = -np.pi / 2 + k * TAU / 10, (ro if k % 2 == 0 else ri)
        # 글자 칸은 세로로 길쭉하므로(cw x lh) 칸 단위로 환산해서 그려야 화면에서 정비례한 별이 된다
        pts.append((cx + rad * np.cos(a) * s / cw, cy + rad * np.sin(a) * s / lh))
    ImageDraw.Draw(img).polygon(pts, fill=255)
    a = np.asarray(img.resize((cols, rows), Image.BOX), float) / 255
    cells = []
    for r in range(rows):
        for c in range(cols):
            if a[r, c] > 0.35:
                dx, dy = (c - cols / 2 + 0.5) * cw, (r - rows * 0.54 + 0.5) * lh
                dist = float(np.hypot(dx, dy))
                cells.append((dx, dy, "@" if dist < 22 else "*", dist))
    return cells


STAR = _star_cells()
STAR_Y = Y_TOP - 68


def counts(t):
    """화면에 표시할 숫자: (지금 보이는 글자 수, 켜진 전구 수)."""
    return int((leaf_born < t).sum()), int((light_on < t).sum())


def draw_snow(d, t):
    f14 = font(14)
    y = (snow_y + snow_v * t) % SCENE_H
    for x, yy, ch, k in zip(snow_x.tolist(), y.tolist(), snow_ch.tolist(), snow_k.tolist()):
        d.text((x, yy), ch, font=f14, fill=shade(WHITE, k), anchor="mm")


def draw_tree(d, t):
    rot = t * ROT_SPEED
    f15, f14, f18 = font(15), font(14), font(18)

    # 줄기
    if t > 0.2:
        for r in range(5):
            d.text((CX, Y_TOP + TREE_H + 20 + r * 14), "#|H|#", font=f15, fill=(150, 100, 60), anchor="mm")

    # 잎: 뒤쪽 글자부터 찍어서 앞쪽 글자가 덮게 한다
    x, y, depth = project(leaf_f, leaf_r, leaf_phi, rot)
    age = t - leaf_born
    bright = 0.30 + 0.70 * (depth + 1) / 2                      # 뒤는 어둡게, 앞은 밝게
    fresh = np.clip(1 - age / 0.5, 0, 1)[:, None]               # 갓 나온 글자는 흰색에서 초록으로
    rgb = (leaf_rgb * bright[:, None] * (1 - fresh) + np.array(WHITE) * fresh).astype(int)
    order = np.argsort(depth)
    order = order[age[order] > 0]
    for px, py, ch, col in zip(x[order].tolist(), y[order].tolist(), leaf_ch[order].tolist(), rgb[order].tolist()):
        d.text((px, py), ch, font=f15, fill=tuple(col), anchor="mm")

    # 나선 장식: 꼭대기부터 차례로 나타나고, 앞쪽 절반만 보인다
    x, y, depth = project(gar_f, gar_r, gar_phi, rot)
    vis = (depth > -0.05) & (t > 4.0 + gar_f * 1.6)
    shimmer = 0.75 + 0.25 * np.sin(t * 6 + gar_f * 60)
    for px, py, ch, k in zip(x[vis].tolist(), y[vis].tolist(), gar_ch[vis].tolist(), shimmer[vis].tolist()):
        d.text((px, py), ch, font=f14, fill=shade(GOLD, k), anchor="mm")

    # 전구: 하나씩 켜지고 각자 다른 박자로 깜빡인다
    x, y, depth = project(light_f, light_r, light_phi, rot)
    vis = (depth > -0.15) & (light_on < t)
    blink = 0.55 + 0.45 * np.sin(t * light_spd + light_ph)
    for px, py, ch, col, k in zip(x[vis].tolist(), y[vis].tolist(), light_ch[vis].tolist(),
                                  light_rgb[vis].tolist(), blink[vis].tolist()):
        d.text((px, py), ch, font=f18, fill=shade(col, k), anchor="mm")

    # 별: 가운데에서 바깥으로 퍼지며 나타난다
    if t > T_STAR:
        reach = ease((t - T_STAR) / 0.6) * 80
        for dx, dy, ch, dist in STAR:
            if dist <= reach:
                k = 0.8 + 0.2 * np.sin(t * 5 + dist * 0.3)
                d.text((CX + dx, STAR_Y + dy), ch, font=f14, fill=shade(GOLD, k), anchor="mm")


def draw_hud(d, t):
    letters, lights = counts(t)
    rows = [f"rotation {np.degrees(t * ROT_SPEED) % 360:6.2f}°", f"lights   {lights:>3}", f"letters  {letters:,}"]
    for i, s in enumerate(rows):
        d.text((67, 1204 + i * 20), s, font=font(16), fill=DIM)
    d.text((864, 258), f"t {t:5.2f}s", font=font(16), fill=shade(GOLD, 0.8))
