import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from concurrent.futures import ProcessPoolExecutor
from data_parser import parse_wafer_data

# ==========================================================
# 1. 전역 보조 함수
# ==========================================================
def q_sub(x, y):
    if len(x) < 3: return x[np.argmin(y)]
    idx = np.argmin(y)
    if idx == 0 or idx == len(x) - 1: return x[idx]
    c = np.polyfit(x[idx - 1:idx + 2], y[idx - 1:idx + 2], 2)
    return -c[1] / (2 * c[0]) if abs(c[0]) > 1e-12 else x[idx]

# ==========================================================
# 2. 개별 Die VpiL 연산 및 플롯 저장
# ==========================================================
def _process_vpil(args):
    d, base_res_dir, L_length = args
    wafer, band, c, r = d['wafer_id'], d['band'], d['die_c'], d['die_r']
    date_str = d.get('date', 'Unknown_Date')

    # Baseline (Ref) Fitting
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(v_ref_wl) < 31: return None
    poly_func = np.poly1d(np.polyfit(v_ref_wl, savgol_filter(v_ref_il, 31, 3), 3))

    # 0V 데이터 확인
    z_data = next((b for b in d['bias_data_list'] if b['bias'] == 0.0), None)
    if not z_data: return None

    m0 = (z_data['wl'] >= d['wl_min']) & (z_data['wl'] <= d['wl_max'])
    w0, i0 = z_data['wl'][m0], z_data['il'][m0]
    flat0 = savgol_filter(i0, 31, 3) - poly_func(w0)
    v0, _ = find_peaks(-flat0, prominence=0.3, distance=20)
    if len(v0) < 2: return None

    fsr = np.mean(np.diff(w0[v0]))
    cwl = w0[v0[np.argmin(np.abs(w0[v0] - d['target_wl']))]]

    volts, p_pi = [], []
    sh = fsr / 2.5
    for b in d['bias_data_list']:
        if b['bias'] is None: continue
        w, i = b['wl'], b['il']
        mb = (w >= d['wl_min']) & (w <= d['wl_max'])
        wb, ib = w[mb], i[mb]

        mloc = (wb >= cwl - sh) & (wb <= cwl + sh)
        if np.sum(mloc) < 5: continue

        flat = savgol_filter(ib[mloc], 11, 3) - poly_func(wb[mloc])
        vwl = q_sub(wb[mloc], flat)
        volts.append(b['bias'])
        p_pi.append(2.0 * (vwl - cwl) / fsr)

    if len(volts) < 5: return None
    volts, p_pi = np.array(volts), np.array(p_pi)

    # 0V 기준 VpiL 추출
    fit = np.poly1d(np.polyfit(volts, p_pi, 2))
    derivative = np.polyder(fit)
    slope_at_0 = np.abs(derivative(0.0))
    slope_at_0 = max(slope_at_0, 1e-5)
    vpil_0V = L_length / slope_at_0

    if not (0.1 <= vpil_0V <= 10.0): return None

    # 트렌드 그래프 그리기 및 저장
    plt.figure(figsize=(8, 6))
    vpil_curve = L_length / np.maximum(np.abs(derivative(volts)), 1e-5)
    plt.plot(volts, vpil_curve, 's-', lw=2, color='gray', label="VpiL Curve")
    plt.plot(0.0, vpil_0V, 'r*', markersize=15, label=f'Value @ 0V = {vpil_0V:.3f}')
    plt.axhline(vpil_0V, color='red', ls=':', alpha=0.5)
    plt.axvline(0.0, color='red', ls=':', alpha=0.5)
    plt.title(f"{wafer} {band} / Coord: ({c}, {r}) / VπL at 0V", fontweight='bold')
    plt.xlabel("Voltage (V)")
    plt.ylabel("Vpi*L (V*cm)")
    plt.grid(True)
    plt.legend()

    coord_folder = f"HY202103_{d['wafer_id']}_({d['die_c']},{d['die_r']})_LION1_DCM_{d['band']}.png"
    w_dir = os.path.join(base_res_dir, wafer, date_str, coord_folder)
    os.makedirs(w_dir, exist_ok=True)
    plt.savefig(os.path.join(w_dir, f"{wafer}_C{c}_R{r}_{band}_VpiL.png"))
    plt.close()

    return True

# ==========================================================
# 3. 메인 실행 블록
# ==========================================================
def main():
    zip_path = "../dat/HY202103"
    base_res_dir = "../res/png"
    target_wafers = ['D07', 'D08', 'D23', 'D24']
    L_length = 0.05

    os.makedirs(base_res_dir, exist_ok=True)
    print("🚀 0V 기준 개별 다이 그래프 생성을 시작합니다...")

    parsed_data_list = list(parse_wafer_data(zip_path, target_wafers))
    tasks = [(d, base_res_dir, L_length) for d in parsed_data_list]
    valid_count = 0

    with ProcessPoolExecutor(max_workers=None) as ex:
        futures = [ex.submit(_process_vpil, t) for t in tasks]
        for f in futures:
            if f.result() is not None:
                valid_count += 1

    print(f"✅ 개별 그래프 저장 완료 (유효 Die: {valid_count}개)")

if __name__ == "__main__":
    main()