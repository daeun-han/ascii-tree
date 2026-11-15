"""터미널에서 회전하는 3D 아스키 크리스마스 트리.

원리: 글자 수천 개를 원뿔 표면의 3D 좌표에 올려두고, 매 프레임
(1) Y축 회전 -> (2) 원근 투영 -> (3) 깊이에 따른 밝기 조절을 거쳐 터미널 격자에 찍는다.

실행:  python tree.py            (Ctrl+C 로 종료)
확인:  python tree.py --frames 1 --plain   (색 없이 한 프레임만 출력)
"""

import argparse
import os
import shutil
import sys
import time

import numpy as np

LEAF_CHARS = np.array(list("*+^x#%&@"))
ORNAMENT_COLORS = np.array([[230, 60, 60], [240, 190, 60], [80, 150, 255], [230, 110, 200]])
CHAR_ASPECT = 2.0  # 터미널 글자는 세로가 가로의 약 2배라서 x를 그만큼 늘려준다


def build_tree(n_leaves=3000, n_ornaments=140, seed=7):
    """트리를 이루는 점들의 (좌표, 글자, 색, 반짝임 여부)를 만든다. y는 위(-1)에서 아래(+1)."""
    rng = np.random.default_rng(seed)

    def cone_points(n, shell):
        # 높이 t(0=꼭대기, 1=바닥). sqrt를 씌워야 넓은 아래쪽에 점이 더 많이 깔려 밀도가 고르다.
        t = np.sqrt(rng.uniform(0.001, 1, n))
        # 톱니 모양으로 반지름을 흔들어 나무의 '층'을 만든다.
        tier = 0.72 + 0.28 * ((t * 5) % 1)
        r = 0.62 * t * tier * rng.uniform(shell, 1, n)
        theta = rng.uniform(0, 2 * np.pi, n)
        return np.stack([r * np.cos(theta), t * 1.7 - 1.0, r * np.sin(theta)], axis=1)

    # 잎: 초록 계열, 안쪽까지 살짝 채워 입체감을 준다
    leaves = cone_points(n_leaves, shell=0.55)
    leaf_chars = rng.choice(LEAF_CHARS, n_leaves)
    green = rng.uniform(0.6, 1.0, (n_leaves, 1))
    leaf_colors = green * np.array([40, 200, 90]) + (1 - green) * np.array([10, 90, 60])

    # 장식: 표면에만, 색색으로 반짝임
    orns = cone_points(n_ornaments, shell=0.97)
    orn_chars = np.full(n_ornaments, "o")
    orn_colors = ORNAMENT_COLORS[rng.integers(0, len(ORNAMENT_COLORS), n_ornaments)]

    # 줄기: 바닥 아래의 가는 원기둥
    n_trunk = 120
    th = rng.uniform(0, 2 * np.pi, n_trunk)
    trunk = np.stack([0.07 * np.cos(th), rng.uniform(0.7, 0.95, n_trunk), 0.07 * np.sin(th)], axis=1)
    trunk_chars = np.full(n_trunk, "|")
    trunk_colors = np.tile([140, 90, 50], (n_trunk, 1))

    # 꼭대기 별
    star = np.array([[0.0, -0.99, 0.0]])

    points = np.vstack([leaves, orns, trunk, star])
    chars = np.concatenate([leaf_chars, orn_chars, trunk_chars, ["★"]])
    colors = np.vstack([leaf_colors, orn_colors, trunk_colors, [[255, 230, 90]]]).astype(float)
    twinkle = np.zeros(len(points), dtype=bool)
    twinkle[n_leaves:n_leaves + n_ornaments] = True
    always_bright = np.zeros(len(points), dtype=bool)
    always_bright[-1] = True
    phase = rng.uniform(0, 2 * np.pi, len(points))
    return points, chars, colors, twinkle, always_bright, phase


def render(tree, angle, t, cols, rows, plain=False):
    points, chars, colors, twinkle, always_bright, phase = tree

    # (1) Y축 회전
    c, s = np.cos(angle), np.sin(angle)
    x = points[:, 0] * c + points[:, 2] * s
    z = -points[:, 0] * s + points[:, 2] * c
    y = points[:, 1]

    # 살짝 위에서 내려다보도록 X축으로 기울인다 (원뿔의 둥근 단면이 보여 입체감이 산다)
    tilt = 0.28
    y, z = y * np.cos(tilt) - z * np.sin(tilt), y * np.sin(tilt) + z * np.cos(tilt)

    # (2) 원근 투영: 카메라에서 멀수록(z가 클수록) 작게
    cam = 3.2
    scale = (rows * 0.46) * cam / (cam + z)
    sx = np.round(cols / 2 + x * scale * CHAR_ASPECT).astype(int)
    sy = np.round(rows / 2 + y * scale).astype(int)

    # (3) 깊이 -> 밝기: 앞쪽은 밝게, 뒤쪽은 어둡게
    depth = (z - z.min()) / (z.max() - z.min())  # 0=가장 앞, 1=가장 뒤
    bright = 1.0 - 0.75 * depth
    bright = np.where(twinkle, bright * (0.55 + 0.45 * np.sin(t * 5 + phase)), bright)
    bright = np.where(always_bright, 1.0, bright)

    # 먼 점부터 찍어서 가까운 점이 덮어쓰게 한다 (화가 알고리즘)
    order = np.argsort(-z)
    order = order[(sx[order] >= 0) & (sx[order] < cols) & (sy[order] >= 0) & (sy[order] < rows)]
    grid_char = np.full((rows, cols), " ", dtype="<U1")
    grid_rgb = np.zeros((rows, cols, 3), dtype=int)
    grid_char[sy[order], sx[order]] = chars[order]
    grid_rgb[sy[order], sx[order]] = (colors[order] * bright[order, None]).astype(int)

    if plain:
        return "\n".join("".join(row).rstrip() for row in grid_char)

    lines = []
    for r in range(rows):
        parts, last = [], None
        for ch, rgb in zip(grid_char[r], grid_rgb[r]):
            if ch == " ":
                parts.append(" ")
                continue
            key = tuple(rgb)
            if key != last:
                parts.append(f"\x1b[38;2;{key[0]};{key[1]};{key[2]}m")
                last = key
            parts.append(ch)
        lines.append("".join(parts) + "\x1b[0m\x1b[K")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="회전하는 3D 아스키 크리스마스 트리")
    ap.add_argument("--frames", type=int, default=0, help="이 프레임 수만 그리고 종료 (0=무한)")
    ap.add_argument("--fps", type=float, default=24)
    ap.add_argument("--speed", type=float, default=0.9, help="회전 속도 (rad/s)")
    ap.add_argument("--plain", action="store_true", help="색/화면 제어 없이 글자만 출력")
    ap.add_argument("--size", type=str, default="", help="가로x세로 (예: 80x40). 기본은 터미널 크기")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    if args.size:
        cols, rows = (int(v) for v in args.size.lower().split("x"))
    else:
        size = shutil.get_terminal_size((80, 40))
        cols, rows = size.columns, size.lines - 1

    tree = build_tree()

    if args.plain:
        for i in range(max(args.frames, 1)):
            print(render(tree, i * args.speed / args.fps, i / args.fps, cols, rows, plain=True))
        return

    os.system("")  # Windows 콘솔에서 ANSI 이스케이프를 켠다
    out = sys.stdout
    out.write("\x1b[?1049h\x1b[?25l")  # 대체 화면으로 전환 + 커서 숨김
    try:
        start, i = time.perf_counter(), 0
        while args.frames == 0 or i < args.frames:
            t = time.perf_counter() - start
            out.write("\x1b[H" + render(tree, t * args.speed, t, cols, rows))
            out.flush()
            i += 1
            time.sleep(max(0.0, start + i / args.fps - time.perf_counter()))
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[0m\x1b[?25h\x1b[?1049l")  # 원래 화면과 커서 복구
        out.flush()


if __name__ == "__main__":
    main()
