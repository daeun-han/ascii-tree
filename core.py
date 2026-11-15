"""공용 상수와 도구. 모든 효과 모듈(*_fx.py)이 여기서 가져다 쓴다.

좌표계: 1080x1920 세로 영상. 위쪽 SCENE_H 픽셀이 장면, 그 아래가 코드 패널.
시간: t는 초 단위, 0 ~ DURATION 을 한 바퀴로 반복한다.
"""

import math

import numpy as np
from PIL import ImageFont

# ---- 화면 ----
W, H = 1080, 1920
SCENE_H = 1340
FPS = 30
DURATION = 13.2
TAU = 2 * math.pi

# ---- 색 ----
BG = (6, 8, 18)
PANEL = (12, 14, 21)
GOLD = (255, 205, 90)
WHITE = (240, 240, 245)
RED = (230, 70, 70)
GREEN = (60, 200, 110)
DIM = (120, 126, 150)
PALETTE = [(255, 70, 70), (255, 200, 60), (90, 160, 255), (200, 110, 255),
           (255, 255, 255), (255, 120, 190), (80, 230, 200)]

# ---- 타임라인(초) ----
T_BUILD = 4.6       # 트리가 다 자라는 시점
T_STAR = 5.2        # 별 등장
T_GIFTS = 6.2       # 선물이 떨어지기 시작
T_BANNER = 8.2      # MERRY CHRISTMAS 타이핑 시작
T_RING = 9.2        # 초상 원을 그리기 시작
T_FIREWORKS = 10.2  # 불꽃놀이 시작
T_HOHO = 11.0       # HO HO HO! 등장

# ---- 배치(px) ----
CX = 553            # 트리 중심 x
Y_TOP = 337         # 트리 꼭대기 y
TREE_H = 767        # 트리 높이
R_BASE = 317        # 트리 바닥 반지름
GROUND = 1180       # 선물 상자 바닥이 놓이는 y
PORTRAIT_C = (283, 565)   # 초상 원 중심
PORTRAIT_R = 210          # 초상 원 반지름
FIREWORKS_C = (837, 404)  # 불꽃놀이 중심
BANNER_Y = 1287           # 배너 글자 중심 y

_MONO = ["consolab.ttf", "consola.ttf", "DejaVuSansMono-Bold.ttf", "Menlo.ttc", "cour.ttf"]
_HANGUL = ["malgunbd.ttf", "malgun.ttf", "AppleSDGothicNeo.ttc", "NotoSansCJK-Bold.ttc"]
_fonts = {}


def font(size, hangul=False):
    """고정폭 글꼴(hangul=True면 한글 글꼴)을 크기별로 캐시해서 돌려준다."""
    key = (size, hangul)
    if key not in _fonts:
        for name in (_HANGUL if hangul else _MONO):
            try:
                _fonts[key] = ImageFont.truetype(name, size)
                break
            except OSError:
                continue
        else:
            _fonts[key] = ImageFont.load_default(size)
    return _fonts[key]


def clamp01(p):
    return max(0.0, min(1.0, p))


def ease(p):
    """0~1 진행도를 부드럽게(천천히 시작, 천천히 끝) 바꾼다."""
    p = clamp01(p)
    return p * p * (3 - 2 * p)


def bounce(p):
    """0~1 진행도 -> 바닥에 떨어져 통통 튀다 멈추는 곡선(1에서 끝남)."""
    p = clamp01(p)
    if p < 1 / 2.75:
        return 7.5625 * p * p
    if p < 2 / 2.75:
        p -= 1.5 / 2.75
        return 7.5625 * p * p + 0.75
    if p < 2.5 / 2.75:
        p -= 2.25 / 2.75
        return 7.5625 * p * p + 0.9375
    p -= 2.625 / 2.75
    return 7.5625 * p * p + 0.984375


def shade(color, k):
    """색을 k배(0~1) 밝기로."""
    return tuple(int(max(0, min(255, c * k))) for c in color)


def rng(seed):
    return np.random.default_rng(seed)
