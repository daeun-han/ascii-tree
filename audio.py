"""배경음: "Jingle Bells"(J. Pierpont, 1857, 퍼블릭 도메인) 후렴을 직접 합성해 wav로 저장한다.

녹음/편곡 자료 없이 악보를 (음이름, 박) 목록으로 옮겨 적고, 사인파를 더해 오르골 소리를 만든다.
"""

import os
import wave

import numpy as np

import core

SR = 44100
N = int(round(core.DURATION * SR))       # 영상 길이와 정확히 같은 샘플 수
BEAT = 0.38                              # 4분음표 길이(초) ≈ 158 BPM
START = 0.10                             # 첫 음 전 여유
FADE = 0.8                               # 루프가 자연스럽게 이어지도록 끝부분 페이드아웃
HERE = os.path.dirname(os.path.abspath(__file__))

# 후렴 16마디는 13.2초에 다 안 들어가서, 앞 4마디 + 마지막 4마디(으뜸음 C로 끝나는 종지)를 잇는다.
MELODY = [
    ("E5", 1), ("E5", 1), ("E5", 2),                   # Jin-gle bells,
    ("E5", 1), ("E5", 1), ("E5", 2),                   # jin-gle bells,
    ("E5", 1), ("G5", 1), ("C5", 1.5), ("D5", 0.5),    # jin-gle all the
    ("E5", 4),                                         # way,
    ("F5", 1), ("F5", 1), ("F5", 1.5), ("F5", 0.5),    # Oh what fun it
    ("F5", 1), ("E5", 1), ("E5", 1), ("E5", 0.5), ("E5", 0.5),  # is to ride in a
    ("G5", 1), ("G5", 1), ("F5", 1), ("D5", 1),        # one-horse o-pen
    ("C5", 4),                                         # sleigh!
]
CHORDS = ["C", "C", "C", "C", "F", "C", "G", "C"]      # 마디별 화음(다장조 I-IV-V)
CHORD_NOTES = {"C": ("C3", "G3", "E4"), "F": ("F2", "C3", "A3"), "G": ("G2", "D3", "B3")}


def freq(name):
    """'E5' 같은 음이름 -> 주파수(Hz). A4 = 440Hz 평균율."""
    semis = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}[name[0]]
    return 440.0 * 2 ** ((semis + 12 * (int(name[1:]) - 4)) / 12)


def bell(f, dur, amp):
    """종소리 한 음: 약간 어긋난(비정수배) 배음을 섞고, 빠르게 올라가 지수적으로 사라진다."""
    t = np.arange(int(dur * SR)) / SR
    tone = np.zeros_like(t)
    for ratio, a, decay in [(1.0, 1.0, 2.2), (2.0, 0.45, 3.5), (3.01, 0.22, 5.0), (5.43, 0.10, 8.0)]:
        tone += a * np.sin(2 * np.pi * f * ratio * t) * np.exp(-decay * t)
    return amp * tone * np.minimum(1.0, t / 0.004)      # 4ms 어택(딸깍 소리 방지)


def soft(f, dur, amp):
    """베이스/화음용 부드러운 음: 기본음 + 옥타브 조금, 천천히 사라진다."""
    t = np.arange(int(dur * SR)) / SR
    tone = np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t)
    return amp * tone * np.exp(-2.0 * t) * np.minimum(1.0, t / 0.02)


def sleigh(rng, amp):
    """썰매 방울: 짧은 노이즈를 미분(고역 통과)해서 '찰랑' 하는 소리."""
    n = int(0.09 * SR)
    noise = np.diff(rng.standard_normal(n + 1))
    return amp * noise * np.exp(-np.arange(n) / SR * 45)


def add(buf, sig, at):
    """sig를 at초 위치에 더한다(버퍼 끝을 넘는 부분은 자른다)."""
    i = int(at * SR)
    if i < len(buf):
        buf[i:i + len(sig)] += sig[:len(buf) - i]


def schedule():
    """멜로디를 (시작 초, 음이름, 박) 목록으로 펼친다."""
    out, beat = [], 0.0
    for name, beats in MELODY:
        out.append((START + beat * BEAT, name, beats))
        beat += beats
    return out


def build(path=os.path.join(HERE, "assets", "carol.wav")):
    buf = np.zeros(N)
    rng = np.random.default_rng(7)
    for at, name, beats in schedule():                         # 멜로디
        add(buf, bell(freq(name), max(1.2, beats * BEAT + 0.8), 0.5), at)
    for bar, chord in enumerate(CHORDS):                       # 마디 1·3박에 베이스 + 화음
        root, fifth, top = CHORD_NOTES[chord]
        t0 = START + bar * 4 * BEAT
        add(buf, soft(freq(root), 1.6, 0.30) + soft(freq(top), 1.6, 0.10), t0)
        add(buf, soft(freq(fifth), 1.2, 0.22), t0 + 2 * BEAT)
    for k in range(len(CHORDS) * 8):                            # 8분음표마다 방울, 정박은 크게
        add(buf, sleigh(rng, 0.05 if k % 2 == 0 else 0.025), START + k * BEAT / 2)

    fade_n = int(FADE * SR)
    buf[-fade_n:] *= np.linspace(1.0, 0.0, fade_n) ** 2        # 끝을 0으로 → 깔끔한 루프
    buf *= 10 ** (-3 / 20) / np.max(np.abs(buf))               # -3 dBFS로 정규화
    pcm = (buf * 32767).astype("<i2")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


if __name__ == "__main__":
    for at, name, beats in schedule():
        print(f"{at:6.2f}s  {name:3s} {freq(name):7.2f} Hz  x{beats}")
    print("saved:", build())
