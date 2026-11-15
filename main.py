"""아스키 크리스마스 트리 영상 만들기.

실행:  python main.py                 -> out/christmas_tree.mp4 를 만들고 바로 재생
확인:  python main.py --frame 6.0     -> 6.0초 시점 한 장만 out/frame_6.00.png 로 저장
"""

import argparse
import importlib
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import tree_fx
from core import BG, DURATION, FPS, H, PORTRAIT_C, PORTRAIT_R, SCENE_H, T_RING, W, ease

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
CAROL = os.path.join(ROOT, "assets", "carol.wav")


def _optional(name):
    """효과 모듈이 아직 없으면 그 효과만 빼고 그린다."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        return None


gifts_fx, portrait_fx, panel_fx = _optional("gifts_fx"), _optional("portrait_fx"), _optional("panel_fx")


def render(t):
    """t초 시점의 한 프레임을 그려 돌려준다. 뒤에 있는 것부터 차례로 덧그린다."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    tree_fx.draw_snow(d, t)
    tree_fx.draw_tree(d, t)
    if gifts_fx:
        gifts_fx.draw(d, t)
    if portrait_fx:
        if t > T_RING:  # 얼굴이 트리 글자와 섞이지 않게 원 안을 먼저 배경색으로 비운다
            r = PORTRAIT_R * ease((t - T_RING) / 0.6)
            d.ellipse((PORTRAIT_C[0] - r, PORTRAIT_C[1] - r, PORTRAIT_C[0] + r, PORTRAIT_C[1] + r), fill=BG)
        portrait_fx.draw(d, t)
    tree_fx.draw_hud(d, t)

    # 번짐(글로우): 장면을 작게 줄여 흐린 뒤 원본에 더하면 밝은 글자 주변이 은은하게 빛난다
    scene = img.crop((0, 0, W, SCENE_H))
    glow = scene.resize((W // 4, SCENE_H // 4)).filter(ImageFilter.GaussianBlur(5)).resize(scene.size)
    img.paste(ImageChops.add(scene, glow.point(lambda v: int(v * 0.55))), (0, 0))

    if panel_fx:
        panel_fx.draw(d, t)
    return img


def make_video(path, loops):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg 이 필요합니다. 설치 후 다시 실행하세요.")
    if not os.path.exists(CAROL) and _optional("audio"):
        importlib.import_module("audio").build(CAROL)

    # 프레임을 파일로 저장하지 않고 ffmpeg 에 바로 흘려보낸다
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if os.path.exists(CAROL):
        cmd += ["-stream_loop", str(loops - 1), "-i", CAROL, "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", path]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    frames = [render(n / FPS).tobytes() for n in _progress(range(int(DURATION * FPS)))]
    for _ in range(loops):
        for frame in frames:
            ff.stdin.write(frame)
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg 인코딩에 실패했습니다.")


def _progress(seq):
    total = len(seq)
    for i, v in enumerate(seq):
        print(f"\r프레임 {i + 1}/{total}", end="", file=sys.stderr)
        yield v
    print(file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="아스키 크리스마스 트리")
    ap.add_argument("--frame", type=float, help="이 시점(초)의 한 장만 PNG로 저장")
    ap.add_argument("--loops", type=int, default=1, help="영상에서 애니메이션을 반복할 횟수")
    ap.add_argument("--no-play", action="store_true", help="만든 뒤 자동 재생하지 않음")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    if args.frame is not None:
        path = os.path.join(OUT, f"frame_{args.frame:.2f}.png")
        render(args.frame).save(path)
        print(path)
        return

    path = os.path.join(OUT, "christmas_tree.mp4")
    make_video(path, args.loops)
    print(path)
    if not args.no_play and hasattr(os, "startfile"):
        os.startfile(path)


if __name__ == "__main__":
    main()
