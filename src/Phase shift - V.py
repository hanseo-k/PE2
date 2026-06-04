import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from concurrent.futures import ProcessPoolExecutor
from data_parser import load_parsed
from analysis_utils import ref_poly

# ── 설정 ──────────────────────────────────────────────────────────────
BROKEN_SLOPE_PM = 10.0     # |dλ/dV| 이 값(pm/V) 미만이면 '망가진 측정'으로 표시
YLIM_PM = (-250, 550)      # Δλ y축 고정 범위(정상 기준) → 망가진 건 y≈0 평평하게 보임


# 1. 병렬 코어들이 나누어 실행할 독립 함수
def _draw_and_save_phase(args):
    d, base_save_dir = args

    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(v_ref_wl) < 31:
        return None
    poly_func = ref_poly(v_ref_wl, v_ref_il, smooth=True)

    # FSR: -2.0V(없으면 첫 bias)의 인접 peak 간격
    tgt_data = next((b for b in d['bias_data_list'] if b['bias'] == -2.0),
                    d['bias_data_list'][0] if d['bias_data_list'] else None)
    if not tgt_data:
        return None
    w, i = tgt_data['wl'], tgt_data['il']
    m_t = (w >= d['wl_min']) & (w <= d['wl_max'])
    flat = savgol_filter(i[m_t], 31, 3) - poly_func(w[m_t])
    peaks, _ = find_peaks(flat, prominence=3.0, distance=30)
    if len(peaks) < 2:
        return None
    w_t = w[m_t]
    centers = (w_t[peaks[:-1]] + w_t[peaks[1:]]) / 2
    idx = np.argmin(np.abs(centers - d['target_wl']))
    FSR = w_t[peaks[idx + 1]] - w_t[peaks[idx]]

    # 전압별 null(valley) 파장 추적
    res = []
    for b in d['bias_data_list']:
        if b['bias'] is None:
            continue
        w_b, i_b = b['wl'], b['il']
        m_b = (w_b >= d['wl_min']) & (w_b <= d['wl_max'])
        if np.sum(m_b) < 31:
            continue
        flat_b = savgol_filter(i_b[m_b], 31, 3) - poly_func(w_b[m_b])
        p_b, _ = find_peaks(flat_b, prominence=3.0, distance=30)
        if len(p_b) < 2:
            continue
        wb_v = w_b[m_b]
        cent = (wb_v[p_b[:-1]] + wb_v[p_b[1:]]) / 2
        i_idx = np.argmin(np.abs(cent - d['target_wl']))
        if i_idx + 1 >= len(p_b):
            continue
        lp, rp = p_b[i_idx], p_b[i_idx + 1]
        v_idx = lp + np.argmin(flat_b[lp:rp + 1])
        res.append({'bias': b['bias'], 'v_wl': wb_v[v_idx]})

    if not res:
        return None
    res.sort(key=lambda x: x['bias'])
    z = next((p for p in res if abs(p['bias']) < 1e-6), None)
    if not z:
        return None
    null0 = z['v_wl']

    biases  = np.array([p['bias'] for p in res])
    dlam_pm = np.array([(p['v_wl'] - null0) * 1000.0 for p in res])   # Δλ [pm]
    dphi    = 2 * np.pi * (dlam_pm / 1000.0) / FSR                    # Δφ [rad]

    # 망가짐 판정: dλ/dV 기울기가 거의 0 (전압 줘도 위상변화 없음)
    slope_pm = np.polyfit(biases, dlam_pm, 1)[0]    # pm/V
    is_broken = abs(slope_pm) < BROKEN_SLOPE_PM
    tag = "_BROKEN" if is_broken else ""

    # ── 이중 축 그래프 (좌: Δλ[pm], 우: Δφ[rad]) ──
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.plot(biases, dlam_pm, 'o-', color='steelblue', lw=2.5, ms=8, label='Δλ_null (pm)')
    ax1.axhline(0, color='gray', ls='--', lw=2, alpha=0.6)
    ax1.axvline(0, color='gray', ls='--', lw=2, alpha=0.6)
    ax1.set_xlabel("Bias Voltage (V)", fontsize=16, fontweight='bold')
    ax1.set_ylabel("Δλ_null vs V=0 [pm]", fontsize=16, fontweight='bold', color='steelblue')
    ax1.tick_params(axis='y', labelcolor='steelblue')
    # Δλ 축을 정상 범위로 고정 → 망가진 측정은 평평하게 (정상이 넘으면 자동 확장)
    ax1.set_ylim(min(YLIM_PM[0], dlam_pm.min() - 20), max(YLIM_PM[1], dlam_pm.max() + 20))
    ax1.grid(True, ls='--', alpha=0.6, lw=1)

    ax2 = ax1.twinx()
    ax2.plot(biases, dphi, 's--', color='crimson', lw=1.5, ms=6, label='Δφ (rad)')
    ax2.axhline(np.pi, color='crimson', ls=':', lw=1, alpha=0.5)
    ax2.text(biases.max(), np.pi, ' π', color='crimson', va='center', fontsize=10)
    ax2.set_ylabel("Δφ [rad] (= 2π·Δλ/FSR)", fontsize=16, fontweight='bold', color='crimson')
    ax2.tick_params(axis='y', labelcolor='crimson')

    band_label = 'C' if 'LMZC' in d['band'] else 'O'
    broken_txt = "  [BROKEN: dλ/dV≈0]" if is_broken else ""
    ax1.set_title(
        f"Wafer: {d['wafer_id']} / Coord: ({d['die_c']}, {d['die_r']}) / {band_label}-band{broken_txt}\n"
        f"Phase Shift  |  dλ/dV = {slope_pm:.1f} pm/V ; FSR = {FSR:.2f} nm",
        fontsize=15, fontweight='bold', pad=15, color='black')
    for spine in ax1.spines.values():
        spine.set_linewidth(2)
    plt.tight_layout()

    # 날짜별 폴더 하위에 저장 (기존 Phase 출력 위치/파일명 유지 → combine_plot 호환)
    date_str = d.get('date', 'Unknown_Date')
    w_dir = os.path.join(base_save_dir, d['wafer_id'], date_str)
    os.makedirs(w_dir, exist_ok=True)
    save_filename = f"{d['wafer_id']}_C{d['die_c']}_R{d['die_r']}_{d['band']}_Phase{tag}.png"
    plt.savefig(os.path.join(w_dir, save_filename), bbox_inches='tight')
    plt.close()
    return save_filename


def main():
    zip_path = "../dat/HY202103"
    base_save_dir = "../res/png"
    target_wafers = ['D07', 'D08', 'D23', 'D24']

    print("▶ 데이터 파싱을 시작합니다...")
    parsed_data_list = load_parsed(zip_path, target_wafers)
    total_items = len(parsed_data_list)
    tasks = [(d, base_save_dir) for d in parsed_data_list]

    print(f"▶ Phase Shift (dλ/dV) 플롯 생성 ({total_items}개, 병렬 처리 중)...")

    success_count = 0
    with ProcessPoolExecutor(max_workers=None) as ex:
        futures = [ex.submit(_draw_and_save_phase, t) for t in tasks]
        for f in futures:
            if f.result() is not None:
                success_count += 1

    print(f"✅ Phase Shift 저장 완료 (총 {success_count}개)")


if __name__ == "__main__":
    main()
