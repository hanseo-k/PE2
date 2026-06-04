"""공용 분석 helper — 여러 스크립트에 복붙돼 있던 함수들을 한 곳에 모음.

- q_sub      : valley(또는 peak) 주변 3점 포물선 subpixel 보정
- ref_poly   : Reference 스펙트럼 3차 다항식 평탄화 기준선 (savgol on/off)
"""
import numpy as np
from scipy.signal import savgol_filter

# ── 공통 분석 파라미터 (필요시 여기서 한 번에 조정) ──
SAVGOL_WINDOW = 31     # Savitzky-Golay 윈도우
SAVGOL_POLY = 3        # Savitzky-Golay 차수
REF_POLY_DEG = 3       # Reference 평탄화 다항식 차수


def q_sub(x, y):
    """valley 주변 3점으로 subpixel 위치 정밀 보정."""
    if len(x) < 3:
        return x[np.argmin(y)]
    idx = np.argmin(y)
    if idx == 0 or idx == len(x) - 1:
        return x[idx]
    c = np.polyfit(x[idx - 1:idx + 2], y[idx - 1:idx + 2], 2)
    return -c[1] / (2 * c[0]) if abs(c[0]) > 1e-12 else x[idx]


def ref_poly(ref_wl, ref_il, smooth=False):
    """Reference 스펙트럼의 3차 다항식 평탄화 기준선(np.poly1d) 반환.

    smooth=True  : Savitzky-Golay 스무딩 후 polyfit (Phase/VpiL 계열)
    smooth=False : raw IL 에 바로 polyfit (ER/flatting/zoom 계열)
    """
    y = savgol_filter(ref_il, SAVGOL_WINDOW, SAVGOL_POLY) if smooth else ref_il
    return np.poly1d(np.polyfit(ref_wl, y, REF_POLY_DEG))
