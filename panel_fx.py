"""아래쪽 코드 패널: 이 프로젝트의 실제 소스 코드를 에디터처럼 스크롤하며 보여준다.

소스는 import 시점에 한 번만 읽고 토큰/색/글꼴/x좌표까지 미리 계산해 두고,
draw()는 보이는 줄만 그대로 찍는다(프레임당 수 ms).
"""

import os
import re

from PIL import Image, ImageDraw

import core

# ---- 배치 ----
TOP = core.SCENE_H          # 패널 시작 y
HEADER_H = 50               # 헤더(파일명 + 실행 상태) 높이
CODE_TOP = TOP + HEADER_H   # 코드 영역 시작 y
LINE_H = 29                 # 줄 간격
PAD_Y = 8                   # 코드 영역 위쪽 여백
MAX_CHARS = 80              # 한 줄 최대 글자 수
MAX_X = core.W - 24         # 글자가 넘지 말아야 할 오른쪽 끝
VISIBLE = (core.H - CODE_TOP - PAD_Y) // LINE_H   # 한 화면에 보이는 줄 수

F_CODE = core.font(17)
F_HAN = core.font(16, hangul=True)   # 고정폭 글꼴에 한글 글리프가 없어서 따로 쓴다

# ---- 문법 색 ----
C_COMMENT = (110, 150, 110)
C_STRING = (240, 150, 110)
C_NUMBER = (170, 160, 255)
C_KEYWORD = (240, 110, 190)
C_TEXT = (205, 208, 220)

FILES = ["core.py", "tree_fx.py", "gifts_fx.py", "portrait_fx.py", "panel_fx.py", "main.py"]
KEYWORDS = set("def return for in if else elif while import from as class try except "
               "with lambda not and or None True False".split())
TOKEN = re.compile(r"""(?P<comment>\#.*)
                     |(?P<string>"(?:\\.|[^"\\])*"?|'(?:\\.|[^'\\])*'?)
                     |(?P<number>\b\d+(?:\.\d*)?\b)
                     |(?P<word>[A-Za-z_]\w*)
                     |(?P<other>\s+|.)""", re.X)
HANGUL = re.compile(r"[㄰-㆏가-힣]")
HANGUL_RUN = re.compile(r"([㄰-㆏가-힣]+(?: +[㄰-㆏가-힣]+)*)")


def _read_source():
    """프로젝트 폴더의 .py 파일을 정해진 순서로 이어 붙인다(없는 파일은 건너뜀)."""
    here = os.path.dirname(os.path.abspath(__file__))
    lines = []
    for name in FILES:
        try:
            with open(os.path.join(here, name), encoding="utf-8") as f:
                lines += [ln.rstrip("\n").expandtabs(4) for ln in f]
        except (OSError, UnicodeDecodeError):
            continue
    return lines or ["# (source not found)"]


def _tokenize(line, in_doc):
    """한 줄을 (글자, 색) 조각으로 나눈다. 여러 줄 docstring 안이면 통째로 문자열 색."""
    line = line[:MAX_CHARS]
    if in_doc or line.lstrip().startswith(('"""', "'''")):
        quotes = line.count('"""') + line.count("'''")
        return [(line, C_STRING)], (in_doc != (quotes % 2 == 1))
    parts = []
    for m in TOKEN.finditer(line):
        kind, text = m.lastgroup, m.group()
        color = {"comment": C_COMMENT, "string": C_STRING, "number": C_NUMBER}.get(kind, C_TEXT)
        if kind == "word" and text in KEYWORDS:
            color = C_KEYWORD
        if parts and parts[-1][1] == color:          # 같은 색은 합쳐서 draw 호출 수를 줄인다
            parts[-1] = (parts[-1][0] + text, color)
        else:
            parts.append((text, color))
    return parts, in_doc


def _layout(parts, x0):
    """조각마다 글꼴과 x좌표를 정하고, 오른쪽 끝을 넘는 부분은 잘라낸다."""
    out, x = [], x0
    # 한글 구간만 한글 글꼴로 (맑은 고딕은 '\'를 '₩'로 그리므로 영문/기호는 고정폭 유지)
    runs = [(r, c) for text, c in parts for r in HANGUL_RUN.split(text) if r]
    for text, color in runs:
        fnt = F_HAN if HANGUL.search(text) else F_CODE
        while text and x + fnt.getlength(text) > MAX_X:
            text = text[:-1]
        if text.strip():
            out.append((x, text, color, fnt))
        x += fnt.getlength(text)
        if x >= MAX_X:
            break
    return out


# ---- import 시점에 한 번만: 소스 읽기 -> 토큰화 -> 배치 ----
SOURCE = _read_source()
TOTAL = len(SOURCE)
GUTTER = F_CODE.getlength("0" * len(str(TOTAL))) + 18   # 줄 번호 칸 너비(오른쪽 정렬 기준)
CODE_X = GUTTER + 18
LINES, _doc = [], False
for _ln in SOURCE:
    _parts, _doc = _tokenize(_ln, _doc)
    LINES.append(_layout(_parts, CODE_X))


def draw(d, t):
    d.rectangle([0, TOP, core.W, core.H], fill=core.PANEL)

    # 스크롤: 읽을 수 있는 속도(초당 10줄)로 픽셀 단위로 부드럽게 흘려보낸다
    span = max(0, TOTAL - VISIBLE)
    off = min(span, t * 10)
    first = int(off)
    for i in range(first, min(TOTAL, first + VISIBLE + 2)):
        base = CODE_TOP + PAD_Y + (i - off) * LINE_H + 21      # 글자 기준선 y
        if base > core.H + LINE_H:
            break
        d.text((GUTTER, base), str(i + 1), font=F_CODE, fill=core.shade(core.DIM, 0.7), anchor="rs")
        for x, text, color, fnt in LINES[i]:
            d.text((x, base), text, font=fnt, fill=color, anchor="ls")

    # 현재 줄 표시: 가운데 줄 왼쪽 끝의 금색 세로 막대
    mid = CODE_TOP + PAD_Y + (VISIBLE // 2) * LINE_H
    d.rectangle([0, mid, 1, mid + LINE_H - 1], fill=core.GOLD)

    # 헤더는 코드 위에 덮어 그려서, 위로 밀려난 줄이 헤더를 침범하지 않게 한다
    d.rectangle([0, TOP, core.W, CODE_TOP - 1], fill=core.PANEL)
    d.text((24, TOP + HEADER_H // 2), "christmas_tree.py", font=core.font(20), fill=core.WHITE, anchor="lm")
    status = f"running · {core.FPS} fps"
    f_st = core.font(17)
    sx = core.W - 24 - f_st.getlength(status)
    cy = TOP + HEADER_H // 2
    d.ellipse([sx - 20, cy - 5, sx - 10, cy + 5], fill=core.GREEN)
    d.text((sx, cy), status, font=f_st, fill=core.GOLD, anchor="lm")
    d.line([0, CODE_TOP - 1, core.W, CODE_TOP - 1], fill=core.shade(core.DIM, 0.35), width=1)


if __name__ == "__main__":
    import time

    os.makedirs("out", exist_ok=True)
    for t in (0.5, 6.0, 12.9):
        img = Image.new("RGB", (core.W, core.H), core.BG)
        t0 = time.perf_counter()
        draw(ImageDraw.Draw(img), t)
        print(f"t={t}: {(time.perf_counter() - t0) * 1000:.1f} ms, lines={TOTAL}")
        img.save(f"out/panel_{t}.png")
