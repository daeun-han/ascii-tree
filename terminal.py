"""터미널에서 도는 완성 장면.

영상(main.py)과 같은 트리 데이터와 타임라인을 쓰되, 글자를 픽셀이 아니라 터미널 칸에 찍는다.
터미널은 가로로 넓으므로 배치만 바꿨다: 가운데 트리, 왼쪽 초상, 오른쪽 불꽃놀이.

실행:  python terminal.py                      (Ctrl+C 로 종료, 창은 가로 110칸 x 세로 32줄 이상 권장)
확인:  python terminal.py --at 12 --plain      (12초 시점 한 장을 색 없이 출력)
"""

import argparse
import os
import shutil
import sys
import time

import numpy as np

import portrait_fx
import tree_fx as T
from core import (DIM, DURATION, GOLD, GREEN, PALETTE, RED, T_BANNER, T_FIREWORKS, T_GIFTS, T_HOHO, T_RING,
                  T_STAR, TAU, WHITE, bounce, clamp01, ease, rng, shade)

CAROL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "carol.wav")
RAMP = " .:-=+*#%@"
WARM = (255, 236, 205)
STAR = ["  *  ", "**@**", " * * "]
_r = rng(11)

# 눈 (좌표는 0~1 비율로 두고 그릴 때 화면 크기를 곱한다)
SNOW_N = 70
snow_x, snow_y, snow_v = _r.uniform(0, 1, SNOW_N), _r.uniform(0, 1, SNOW_N), _r.uniform(0.03, 0.10, SNOW_N)
snow_ch = np.array(list("*+.'"))[_r.integers(0, 4, SNOW_N)]

# 선물: (트리 중심에서의 가로 위치, 폭, 높이, 상자색, 리본색)
GIFTS = [(-24, 7, 3, PALETTE[1], WHITE), (-16, 6, 2, PALETTE[3], WHITE), (-9, 5, 3, PALETTE[0], GOLD),
         (4, 5, 2, PALETTE[2], WHITE), (10, 7, 4, PALETTE[6], WHITE), (18, 6, 3, PALETTE[5], GOLD)]
GIFT_CH = "x*o%&#"

# 불꽃놀이: (중심에서의 위치, 색) 마다 입자 36개의 방향과 속도를 미리 정해 둔다
BURSTS = [((0, 0), PALETTE[3]), ((-9, 3), PALETTE[6]), ((7, -2), PALETTE[1]), ((-3, -3), PALETTE[5])]
fw_ang, fw_spd = _r.uniform(0, TAU, (4, 36)), _r.uniform(0.35, 1.0, (4, 36))
fw_ch = np.array(list("*+.o"))[_r.integers(0, 4, (4, 36))]

BANNER = [("M E R R Y", GREEN), ("C H R I S T M A S", RED), ("2 0 2 6", GOLD)]

# 얼굴: 영상용 55x30 밝기 격자를 2x2씩 평균 내 27x15 로 줄인다
_g = portrait_fx._load_brightness()
FACE = _g[:30, :54].reshape(15, 2, 27, 2).mean(axis=(1, 3))


class Canvas:
    """글자 격자와 색 격자. 나중에 찍은 글자가 먼저 찍은 글자를 덮는다."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.ch = np.full((rows, cols), " ", dtype="<U1")
        self.rgb = np.zeros((rows, cols, 3), dtype=int)

    def put(self, x, y, ch, rgb):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.cols and 0 <= y < self.rows:
            self.ch[y, x], self.rgb[y, x] = ch, rgb

    def text(self, x, y, s, rgb):
        for i, c in enumerate(s):
            if c != " ":
                self.put(x + i, y, c, rgb)

    def points(self, x, y, ch, rgb):
        """여러 점을 한 번에 찍는다 (배열 순서대로, 뒤의 것이 덮는다)."""
        x, y = np.round(x).astype(int), np.round(y).astype(int)
        ok = (x >= 0) & (x < self.cols) & (y >= 0) & (y < self.rows)
        self.ch[y[ok], x[ok]] = ch[ok]
        self.rgb[y[ok], x[ok]] = rgb[ok]

    def to_string(self, plain):
        if plain:
            return "\n".join("".join(row).rstrip() for row in self.ch)
        lines = []
        for r in range(self.rows):
            parts, last = [], None
            for ch, rgb in zip(self.ch[r], self.rgb[r]):
                if ch == " ":
                    parts.append(" ")
                    continue
                key = tuple(rgb)
                if key != last:  # 색이 바뀔 때만 색 코드를 넣어 출력량을 줄인다
                    parts.append(f"\x1b[38;2;{key[0]};{key[1]};{key[2]}m")
                    last = key
                parts.append(ch)
            lines.append("".join(parts) + "\x1b[0m\x1b[K")
        return "\n".join(lines)


def draw_tree(c, t, cx, top, ht, rc):
    rot = t * T.ROT_SPEED

    def project(f, radius, phi):
        # 글자 칸은 세로가 가로의 2배라서, 깊이로 인한 세로 이동은 절반만 준다
        depth = radius * np.sin(phi + rot)
        return cx + radius * np.cos(phi + rot) * rc, top + f * ht + depth * rc / 2 * T.TILT, depth

    if t > 0.2:
        for r in range(2):
            c.text(cx - 1, top + ht + 2 + r, "|H|", (150, 100, 60))

    # 잎: 뒤쪽부터 찍고, 갓 나온 글자는 흰색에서 초록으로 바뀐다
    x, y, depth = project(T.leaf_f, T.leaf_r, T.leaf_phi)
    age = t - T.leaf_born
    bright = 0.30 + 0.70 * (depth + 1) / 2
    fresh = np.clip(1 - age / 0.5, 0, 1)[:, None]
    rgb = (T.leaf_rgb * bright[:, None] * (1 - fresh) + np.array(WHITE) * fresh).astype(int)
    order = np.argsort(depth)
    order = order[age[order] > 0]
    c.points(x[order], y[order], T.leaf_ch[order], rgb[order])

    # 나선 장식
    x, y, depth = project(T.gar_f, T.gar_r, T.gar_phi)
    vis = (depth > -0.05) & (t > 4.0 + T.gar_f * 1.6)
    c.points(x[vis], y[vis], T.gar_ch[vis], np.tile(GOLD, (int(vis.sum()), 1)))

    # 전구
    x, y, depth = project(T.light_f, T.light_r, T.light_phi)
    vis = (depth > -0.15) & (T.light_on < t)
    blink = 0.55 + 0.45 * np.sin(t * T.light_spd + T.light_ph)
    c.points(x[vis], y[vis], T.light_ch[vis], (T.light_rgb[vis] * blink[vis, None]).astype(int))

    # 별
    if t > T_STAR:
        k = ease((t - T_STAR) / 0.6) * (0.85 + 0.15 * np.sin(t * 5))
        for i, row in enumerate(STAR):
            c.text(cx - 2, top - 3 + i, row, shade(GOLD, k))


def draw_gifts(c, t, cx, ground):
    for i, (off, w, h, col, rib) in enumerate(GIFTS):
        t0 = T_GIFTS + i * 0.35
        if t < t0:
            continue
        bottom = ground - (1 - bounce((t - t0) / 0.9)) * 12   # 위에서 떨어져 통통 튄다
        for r in range(h):
            for k in range(w):
                ribbon = k == w // 2 or r == h // 2
                ch = ("|" if k == w // 2 else "=") if ribbon else GIFT_CH[(i + r + k) % len(GIFT_CH)]
                c.put(cx + off + k, bottom - h + 1 + r, ch, rib if ribbon else col)


def draw_banner(c, t, cx, row):
    if t < T_BANNER:
        return
    total = sum(len(w) for w, _ in BANNER) + 2 * (len(BANNER) - 1)
    typed = int(clamp01((t - T_BANNER) / 1.6) * total)      # 한 글자씩 타이핑
    x = cx - total // 2
    for word, col in BANNER:
        c.text(x, row, word[:max(0, typed)], col)
        typed -= len(word) + 2
        x += len(word) + 2


def draw_portrait(c, t, fx, fy):
    """(fx, fy) = 얼굴 격자의 왼쪽 위 칸. 원 -> 얼굴 -> 모자 -> HO HO HO 순서."""
    if t < T_RING:
        return
    rows, cols = FACE.shape
    mx, my = fx + cols / 2, fy + rows / 2
    for k in range(int(64 * ease((t - T_RING) / 0.9))):
        a = -np.pi / 2 + TAU * k / 64
        c.put(mx + np.cos(a) * (cols / 2 + 2), my + np.sin(a) * (rows / 2 + 1), ".", shade(WHITE, 0.6))

    shown = int(rows * clamp01((t - T_RING - 0.5) / 1.0))    # 위에서부터 한 줄씩
    for r in range(shown):
        for k in range(cols):
            inside = ((k + 0.5 - cols / 2) / (cols / 2)) ** 2 + ((r + 0.5 - rows / 2) / (rows / 2)) ** 2 <= 1
            b = FACE[r, k]
            ch = RAMP[min(len(RAMP) - 1, int(b * len(RAMP)))]
            if inside and ch != " ":
                c.put(fx + k, fy + r, ch, shade(WARM, 0.15 + 0.85 * b))

    p = (t - T_RING - 1.3) / 0.6
    if p > 0:   # 산타 모자: 흰 챙 한 줄, 그 위로 좁아지며 오른쪽으로 기우는 빨간 몸통, 끝에 방울
        dy = -3 * (1 - ease(p))
        for k in range(cols + 4):
            c.put(fx - 2 + k, fy - 1 + dy, "o*#@"[k % 4], WHITE)
        for j in range(1, 5):
            w = cols - 2 - j * 6
            for k in range(w):
                c.put(mx - w / 2 + j * 1.5 + k, fy - 1 - j + dy, "#%&@"[(j + k) % 4], shade(RED, 0.7 + 0.3 * (k % 2)))
        c.text(int(mx) + 8, int(fy - 6 + dy), "@@", WHITE)

    if t > T_HOHO:
        c.text(int(mx) - 5, fy + rows + 2, "HO HO HO!", shade(GOLD, 0.8 + 0.2 * np.sin((t - T_HOHO) * 6)))


def draw_fireworks(c, t, ox, oy):
    for i, ((dx, dy), col) in enumerate(BURSTS):
        p = (t - T_FIREWORKS - i * 0.55) / 1.3
        if not 0 < p < 1:
            continue
        e = 1 - (1 - p) ** 3                                 # 빠르게 퍼지다 느려진다
        x = ox + dx + np.cos(fw_ang[i]) * fw_spd[i] * 11 * e
        y = oy + dy + np.sin(fw_ang[i]) * fw_spd[i] * 5.5 * e + 1.5 * p * p   # 살짝 아래로 처진다
        c.points(x, y, fw_ch[i], np.tile(shade(col, 1 - p * p), (36, 1)))


def frame(t, cols, rows, plain=False):
    c = Canvas(cols, rows)
    cx, top = cols // 2, 4
    ht = rows - 11                              # 트리 높이(줄)
    rc = min(ht * 0.82, cols * 0.3)             # 바닥 반지름(칸)

    y = (snow_y + snow_v * t) % 1
    c.points(snow_x * cols, y * (rows - 5), snow_ch, np.tile(shade(WHITE, 0.45), (SNOW_N, 1)))
    draw_tree(c, t, cx, top, ht, rc)
    draw_gifts(c, t, cx, rows - 4)
    draw_banner(c, t, cx, rows - 2)
    face_x = int(cx - rc - 8 - FACE.shape[1])
    if face_x >= 3 and rows >= 30:              # 자리가 모자라면 초상은 생략한다
        draw_portrait(c, t, face_x, 8)
    draw_fireworks(c, t, min(cx + rc + 16, cols - 13), 8)

    letters, lights = T.counts(t)
    hud = [f"rotation {np.degrees(t * T.ROT_SPEED) % 360:6.2f}", f"lights   {lights:>3}", f"letters  {letters:,}"]
    for i, s in enumerate(hud):
        c.text(2, rows - 4 + i, s, DIM)
    c.text(cols - 12, 1, f"t {t:5.2f}s", shade(GOLD, 0.8))
    return c.to_string(plain)


def main():
    ap = argparse.ArgumentParser(description="터미널용 아스키 크리스마스 트리")
    ap.add_argument("--at", type=float, help="이 시점(초)의 한 장만 출력하고 종료")
    ap.add_argument("--plain", action="store_true", help="색 없이 글자만 출력")
    ap.add_argument("--size", default="", help="가로x세로 (예: 120x36). 기본은 터미널 크기")
    ap.add_argument("--fps", type=float, default=24)
    ap.add_argument("--mute", action="store_true", help="캐롤을 틀지 않음")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    if args.size:
        cols, rows = (int(v) for v in args.size.lower().split("x"))
    else:
        size = shutil.get_terminal_size((120, 36))
        cols, rows = size.columns, size.lines - 1

    os.system("")  # Windows 콘솔에서 ANSI 이스케이프를 켠다
    if args.at is not None:
        print(frame(args.at, cols, rows, args.plain))
        return

    sound = None
    if not args.mute and os.path.exists(CAROL) and sys.platform == "win32":
        import winsound as sound
        sound.PlaySound(CAROL, sound.SND_FILENAME | sound.SND_ASYNC | sound.SND_LOOP)

    out = sys.stdout
    out.write("\x1b[?1049h\x1b[?25l")  # 대체 화면으로 전환 + 커서 숨김
    try:
        start, i = time.perf_counter(), 0
        while True:
            t = (time.perf_counter() - start) % DURATION
            out.write("\x1b[H" + frame(t, cols, rows))
            out.flush()
            i += 1
            time.sleep(max(0.0, start + i / args.fps - time.perf_counter()))
    except KeyboardInterrupt:
        pass
    finally:
        if sound:
            sound.PlaySound(None, 0)
        out.write("\x1b[0m\x1b[?25h\x1b[?1049l")  # 원래 화면과 커서 복구
        out.flush()


if __name__ == "__main__":
    main()
