"""초상 효과: 점선 원 -> ASCII 얼굴 -> 산타 모자 -> HO HO HO!

모든 요소는 도형이 아니라 글자(ImageDraw.text)로만 그린다.
정적인 데이터(밝기 격자, 모자 격자)는 import 시점에 한 번만 계산하고,
draw(d, t)는 t만 보고 그리는 순수 함수다.
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw

import core
from core import PORTRAIT_C, PORTRAIT_R, T_RING, T_HOHO, ease, shade, clamp01

HERE = os.path.dirname(os.path.abspath(__file__))
COLS, ROWS = 55, 30
RAMP = " .:-=+*#%@"                     # 어두움 -> 밝음(성김 -> 빽빽함)
FACE_FONT = core.font(13)
GRID_W = 2 * PORTRAIT_R * 0.92          # 격자가 원 안을 채우는 폭/높이
CELL_W, CELL_H = GRID_W / COLS, GRID_W / ROWS
WARM = (255, 236, 205)                  # 얼굴 글자의 따뜻한 흰색

# ---------------- 1. 밝기 격자(30x55, 0~1) ----------------

def _from_photo(path):
    """사진 -> 가운데 정사각 크롭 -> 흑백 -> 55x30 격자 -> 대비 정규화."""
    img = Image.open(path).convert("L")
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
    g = np.asarray(img.resize((COLS, ROWS), Image.LANCZOS), dtype=np.float32)
    lo, hi = np.percentile(g, 2), np.percentile(g, 98)   # 양 끝을 잘라 대비를 살린다
    return np.clip((g - lo) / max(hi - lo, 1e-3), 0, 1)


def _placeholder():
    """사진이 없을 때 쓰는 절차적 스마일 얼굴(밝은 둥근 머리, 어두운 눈/입)."""
    y, x = np.mgrid[0:ROWS, 0:COLS].astype(np.float32)
    u = (x + 0.5) / COLS * 2 - 1           # -1~1 정규 좌표 (가로)
    v = (y + 0.5) / ROWS * 2 - 1           # -1~1 정규 좌표 (세로)
    r = np.hypot(u / 0.8, v / 0.9)
    g = np.clip(1.15 - r ** 3, 0, 1) * 0.85                      # 머리: 가장자리로 갈수록 어둡게
    g *= np.clip(1.0 - 0.35 * (u + 0.4) - 0.2 * v, 0.55, 1.0)    # 왼쪽 위에서 빛이 오는 음영
    for ex in (-0.32, 0.32):                                     # 두 눈
        g *= 1 - 0.9 * np.exp(-(((u - ex) / 0.12) ** 2 + ((v + 0.2) / 0.17) ** 2))
    mouth = np.abs(np.hypot(u, v + 0.1) - 0.5) < 0.1          # 웃는 입: 원호의 아랫부분
    g[mouth & (v > 0.2) & (np.abs(u) < 0.4)] *= 0.12
    for cx in (-0.5, 0.5):                                       # 볼 하이라이트
        g += 0.12 * np.exp(-(((u - cx) / 0.15) ** 2 + ((v - 0.15) / 0.12) ** 2)) * (r < 1)
    return np.clip(g, 0, 1)


def _load_brightness():
    for name in ("face.jpg", "face.png"):
        path = os.path.join(HERE, "assets", name)
        if os.path.exists(path):
            return _from_photo(path)
    return _placeholder()


def _build_face(bright):
    """밝기 격자 -> (행, x, y, 글자, 색) 목록. 원 밖 칸과 빈칸은 미리 버린다."""
    cx, cy = PORTRAIT_C
    x0, y0 = cx - GRID_W / 2, cy - GRID_W / 2
    cells = []
    for r in range(ROWS):
        for c in range(COLS):
            px, py = x0 + (c + 0.5) * CELL_W, y0 + (r + 0.5) * CELL_H
            if math.hypot(px - cx, py - cy) > PORTRAIT_R - 6:     # 원형 마스크
                continue
            b = float(bright[r, c])
            ch = RAMP[min(len(RAMP) - 1, int(b * len(RAMP)))]
            if ch == " ":
                continue
            cells.append((r, px, py, ch, shade(WARM, 0.1 + 0.9 * b)))
    return cells


FACE_CELLS = _build_face(_load_brightness())

# ---------------- 2. 산타 모자 격자 ----------------
HAT_W, HAT_H = 390, 240                             # 모자 도안 크기
HAT_SCALE = 0.6                                     # 머리 폭에 맞게 도안을 줄여서 쓴다
HAT_X, HAT_Y = 217, 303                             # 줄인 모자의 왼쪽 위 (챙이 이마 위에 걸친다)
HAT_CW, HAT_CH = 8, 12                              # 모자 글자 칸 크기


def _build_hat():
    """작은 오프스크린 이미지에 모자 모양을 칠한 뒤 글자 칸으로 샘플링한다.
    채널 R=빨간 몸통, G=흰 털(챙/방울)."""
    im = Image.new("RGB", (HAT_W, HAT_H))
    p = ImageDraw.Draw(im)
    # 몸통: 두 개의 2차 베지어 곡선(왼쪽 볼록, 오른쪽 오목)으로 끝이 오른쪽 위로 휘는 원뿔
    def bez(a, c, b, n=24):
        return [((1 - s) ** 2 * a[0] + 2 * (1 - s) * s * c[0] + s * s * b[0],
                 (1 - s) ** 2 * a[1] + 2 * (1 - s) * s * c[1] + s * s * b[1])
                for s in np.linspace(0, 1, n)]
    tip = (338, 42)
    p.polygon(bez((45, 210), (150, 50), tip) + bez(tip, (285, 95), (345, 210)), fill=(255, 0, 0))
    p.rounded_rectangle((10, 196, 380, 240), radius=22, fill=(0, 255, 0))   # 흰 챙
    p.ellipse((322, 4, 382, 64), fill=(0, 255, 0))                          # 방울
    w, h = int(HAT_W * HAT_SCALE), int(HAT_H * HAT_SCALE)
    a = np.asarray(im.resize((w, h), Image.NEAREST))
    gen = core.rng(7)
    cells = []
    for y in range(0, h - HAT_CH // 2, HAT_CH):
        for x in range(0, w - HAT_CW // 2, HAT_CW):
            r, g, _ = a[y + HAT_CH // 2, x + HAT_CW // 2]
            if g > 128:          # 흰 털: 몽글몽글한 질감
                ch = "@#o*"[gen.integers(4)]
                col = shade(core.WHITE, 0.8 + 0.2 * gen.random())
            elif r > 128:        # 빨간 몸통: 왼쪽 위가 밝은 음영
                k = 1.05 - 0.45 * (x / w) * 0.6 - 0.35 * (y / h)
                ch = "#%@&"[gen.integers(4)]
                col = shade(core.RED, clamp01(k + 0.1 * gen.random()) + 0.05)
            else:
                continue
            cells.append((HAT_X + x, HAT_Y + y, ch, col))
    return cells


HAT_CELLS = _build_hat()
HAT_FONT = core.font(13)
HOHO_FONT = core.font(22)

# ---------------- 그리기 ----------------

def draw(d, t):
    if t < T_RING:
        return
    cx, cy = PORTRAIT_C

    # 1) 점선 원: 꼭대기부터 시계방향으로 점을 하나씩 찍는다
    n_dots, rr = 96, PORTRAIT_R + 14
    shown = int(ease((t - T_RING) / 0.9) * n_dots + 0.5)
    for i in range(shown):
        ang = -math.pi / 2 + core.TAU * i / n_dots           # 화면 y가 아래로 커지므로 +각도 = 시계방향
        d.text((cx + rr * math.cos(ang), cy + rr * math.sin(ang)), ".",
               font=FACE_FONT, fill=(215, 218, 228), anchor="mm")

    # 2) 얼굴: 위에서 아래로 한 줄씩 드러난다 (경계 줄은 살짝 흐리게)
    p = (t - (T_RING + 0.5)) / 1.0
    if p > 0:
        rows = ease(p) * ROWS
        for r, x, y, ch, col in FACE_CELLS:
            if r < rows:
                k = clamp01(rows - r)
                d.text((x, y), ch, font=FACE_FONT, fill=shade(col, k), anchor="mm")

    # 3) 산타 모자: 60px 위에서 내려오며 나타난다
    p = (t - (T_RING + 1.3)) / 0.6
    if p > 0:
        e = ease(p)
        dy = -60 * (1 - e)
        for x, y, ch, col in HAT_CELLS:
            d.text((x, y + dy), ch, font=HAT_FONT, fill=shade(col, e))

    # 4) HO HO HO!: 금색 글자가 은은하게 깜빡인다
    if t >= T_HOHO:
        k = ease((t - T_HOHO) / 0.3) * (0.8 + 0.2 * math.sin((t - T_HOHO) * 6))
        d.text((150, 815), "HO HO HO!", font=HOHO_FONT, fill=shade(core.GOLD, k))


if __name__ == "__main__":
    import time
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    for tt in (9.6, 10.3, 11.0, 12.5):
        img = Image.new("RGB", (core.W, core.H), core.BG)
        t0 = time.perf_counter()
        draw(ImageDraw.Draw(img), tt)
        print(f"t={tt}: {(time.perf_counter() - t0) * 1000:.1f} ms")
        img.save(os.path.join(HERE, "out", f"portrait_{tt}.png"))
