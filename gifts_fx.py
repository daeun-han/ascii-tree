"""선물 상자 낙하 + MERRY CHRISTMAS 배너 타이핑 + 불꽃놀이.

모든 요소를 문자로 그린다(배너 배경 사각형만 예외). draw(d, t)는 t의 순수 함수라
같은 t면 항상 같은 그림이 나온다. 무작위 값은 import 시점에 한 번만 뽑아 둔다.
"""

import math

from core import (BG, FIREWORKS_C, GOLD, GREEN, GROUND, H, PALETTE, RED, W, WHITE,
                  BANNER_Y, T_BANNER, T_FIREWORKS, T_GIFTS, bounce, clamp01, font, rng, shade)

# ---------------------------------------------------------------- 1. 선물 상자
# 상자 = 작은 글자를 격자로 채운 것. 가운데 열/행은 다른 색으로 칠해 '리본'처럼 보이게 한다.
GIFT_FONT = font(14)
CELL_W = GIFT_FONT.getlength("x")   # 고정폭이라 모든 글자 폭이 같다
CELL_H = 13
DROP_H = 520      # 떨어지기 시작하는 높이
DROP_DUR = 0.9    # 낙하 시간
DROP_GAP = 0.35   # 상자 사이 간격

# (중심 x, 폭, 높이, 몸통 색, 채움 글자, 리본 색) — 낙하 순서대로, 좌우를 번갈아 배치
_BOX_SPECS = [
    (465, 100, 110, PALETTE[0], "x", GOLD),
    (630, 80, 70, PALETTE[2], "o", WHITE),
    (358, 70, 60, PALETTE[3], "%", GOLD),
    (730, 100, 120, PALETTE[6], "#", RED),
    (268, 90, 85, PALETTE[1], "*", WHITE),
    (840, 90, 65, PALETTE[5], "&", GOLD),
]


def _make_box(cx, w, h, color, ch, ribbon):
    """상자 하나를 '몸통 줄들 + 리본 줄들'로 미리 만들어 둔다(그릴 때는 문자열만 찍는다)."""
    cols, rows = max(3, round(w / CELL_W)) | 1, max(3, round(h / CELL_H)) | 1   # 홀수 -> 정가운데 존재
    mc, mr = cols // 2, rows // 2
    x0 = cx - cols * CELL_W / 2
    body_row = ch * mc + " " + ch * (cols - mc - 1)       # 가운데 열은 비워 둔다
    body = [(r, body_row) for r in range(rows) if r != mr]
    rib = [(mr, "=" * cols)] + [(r, " " * mc + "|") for r in range(rows) if r != mr]
    return dict(x0=x0, rows=rows, body=body, rib=rib, color=color, ribbon=ribbon,
                bow_x=x0 + (mc - 1) * CELL_W)


BOXES = [_make_box(*s) for s in _BOX_SPECS]


def _draw_gifts(d, t):
    for i, b in enumerate(BOXES):
        p = (t - T_GIFTS - i * DROP_GAP) / DROP_DUR
        if p < 0:
            continue
        # bounce(p): 0 -> 1 로 가면서 바닥에 닿고 통통 튄다. 남은 거리만큼 위로 올려 그린다.
        top = GROUND - b["rows"] * CELL_H - DROP_H * (1 - bounce(p))
        for r, s in b["body"]:
            d.text((b["x0"], top + r * CELL_H), s, font=GIFT_FONT, fill=b["color"])
        for r, s in b["rib"]:
            d.text((b["x0"], top + r * CELL_H), s, font=GIFT_FONT, fill=b["ribbon"])
        d.text((b["bow_x"], top - CELL_H), "@@@", font=GIFT_FONT, fill=b["ribbon"])  # 리본 매듭


# ---------------------------------------------------------------- 2. 배너
# 글자 사이에 공백을 넣어(letter-spacing) 한 글자씩 타이핑. 단어마다 어두운 색 블록을 깐다.
BANNER_FONT = font(22)
BANNER_CW = BANNER_FONT.getlength("M")
TYPE_DUR = 1.6
_WORDS = [("MERRY", GREEN), ("CHRISTMAS", RED), ("2026", GOLD)]
_WORD_GAP = 3                                   # 단어 사이 칸 수
_SPACED = [" ".join(w) for w, _ in _WORDS]
_TOTAL_COLS = sum(map(len, _SPACED)) + _WORD_GAP * (len(_WORDS) - 1)
_N_LETTERS = sum(len(w) for w, _ in _WORDS)

# 각 단어의 시작 x와, 몇 번째 글자부터 시작하는지 미리 계산
_LAYOUT, _x, _k = [], 540 - _TOTAL_COLS * BANNER_CW / 2, 0
for (word, color), spaced in zip(_WORDS, _SPACED):
    _LAYOUT.append((word, color, _x, _k))
    _x += (len(spaced) + _WORD_GAP) * BANNER_CW
    _k += len(word)
_TY = BANNER_Y - 11       # 글자 높이(22)의 절반만큼 올려 중심을 맞춘다


def _draw_banner(d, t):
    p = clamp01((t - T_BANNER) / TYPE_DUR)
    n = int(p * _N_LETTERS + 1e-9)                # 지금까지 타이핑된 글자 수
    cursor_x = None
    for word, color, x, k in _LAYOUT:
        shown = max(0, min(len(word), n - k))
        if shown == 0 and n < k:
            break
        # 단어 배경 블록: 단어 색을 어둡게 한 사각형(이 효과에서 유일한 도형)
        wpx = (2 * len(word) - 1) * BANNER_CW
        d.rectangle((x - 10, BANNER_Y - 20, x + wpx + 10, BANNER_Y + 20), fill=shade(color, 0.22))
        if shown:
            d.text((x, _TY), " ".join(word[:shown]), font=BANNER_FONT, fill=color)
        cursor_x = x + 2 * shown * BANNER_CW
    # 타이핑 중에만 깜빡이는 커서(약 4Hz)
    if p < 1 and cursor_x is not None and int((t - T_BANNER) * 8) % 2 == 0:
        d.rectangle((cursor_x, BANNER_Y - 12, cursor_x + BANNER_CW - 2, BANNER_Y + 12), fill=WHITE)


# ---------------------------------------------------------------- 3. 불꽃놀이
# 터지는 지점마다 입자 70개: 바깥으로 퍼지며 점점 느려지고, 살짝 아래로 처지며 사라진다.
FW_FONT = font(18)
FW_DUR = 1.3
FW_GAP = 0.55             # 4발이 영상 끝(13.2s) 전에 다 끝나도록 0.6 대신 0.55
N_PART = 70
GRAVITY = 70              # 끝날 때까지 아래로 처지는 거리(px)
_CHARS = "*+.o"
_BURSTS = []
_r = rng(2026)
for i, (dx, dy, ci) in enumerate([(-60, 20, 0), (90, -70, 1), (-100, -90, 3), (50, 100, 6)]):
    ang = _r.uniform(0, 2 * math.pi, N_PART)
    spd = _r.uniform(90, 200, N_PART)            # 최종 반지름(px)
    chars = _r.integers(0, len(_CHARS), N_PART)
    _BURSTS.append(dict(t0=T_FIREWORKS + i * FW_GAP, cx=FIREWORKS_C[0] + dx, cy=FIREWORKS_C[1] + dy,
                        color=PALETTE[ci], parts=[
                            (s * math.cos(a), s * math.sin(a), _CHARS[c]) for a, s, c in zip(ang, spd, chars)]))


def _draw_fireworks(d, t):
    for b in _BURSTS:
        p = (t - b["t0"]) / FW_DUR
        if not 0 <= p < 1:
            continue
        r = 1 - (1 - p) ** 3                     # ease-out: 처음엔 빠르게, 점점 느리게
        fall = GRAVITY * p * p
        fade = 1.0 if p < 0.55 else (1 - p) / 0.45
        col = shade(b["color"], fade)
        for vx, vy, ch in b["parts"]:
            d.text((b["cx"] + vx * r - 5, b["cy"] + vy * r + fall - 9), ch, font=FW_FONT, fill=col)


def draw(d, t):
    if t >= T_GIFTS:
        _draw_gifts(d, t)
    if t >= T_BANNER:
        _draw_banner(d, t)
    if t >= T_FIREWORKS:
        _draw_fireworks(d, t)


if __name__ == "__main__":
    import os
    import time

    from PIL import Image, ImageDraw

    os.makedirs("out", exist_ok=True)
    for tt in (7.0, 9.0, 10.8, 12.0):
        img = Image.new("RGB", (W, H), BG)
        t0 = time.perf_counter()
        draw(ImageDraw.Draw(img), tt)
        print(f"t={tt}: {(time.perf_counter() - t0) * 1000:.1f} ms")
        img.save(f"out/gifts_{tt}.png")
