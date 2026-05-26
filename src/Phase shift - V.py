import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from data_parser import parse_wafer_data

zip_path = "../dat/HY202103"
# 1. Base 폴더를 res로 통일
base_save_dir = "../res/png"
target_wafers = ['D07', 'D08', 'D23', 'D24']

for d in parse_wafer_data(zip_path, target_wafers):
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(v_ref_wl) < 31: continue
    poly_func = np.poly1d(np.polyfit(v_ref_wl, savgol_filter(v_ref_il, 31, 3), 3))

    tgt_data = next((b for b in d['bias_data_list'] if b['bias'] == -2.0),
                    d['bias_data_list'][0] if d['bias_data_list'] else None)
    if not tgt_data: continue

    w, i = tgt_data['wl'], tgt_data['il']
    m_t = (w >= d['wl_min']) & (w <= d['wl_max'])
    flat = savgol_filter(i[m_t], 31, 3) - poly_func(w[m_t])
    peaks, _ = find_peaks(flat, prominence=3.0, distance=30)
    if len(peaks) < 2: continue

    w_t = w[m_t]
    centers = (w_t[peaks[:-1]] + w_t[peaks[1:]]) / 2
    idx = np.argmin(np.abs(centers - d['target_wl']))
    FSR = w_t[peaks[idx + 1]] - w_t[peaks[idx]]

    phase_res = []
    for b in d['bias_data_list']:
        if b['bias'] is None: continue
        w_b, i_b = b['wl'], b['il']
        m_b = (w_b >= d['wl_min']) & (w_b <= d['wl_max'])
        if np.sum(m_b) < 31: continue

        flat_b = savgol_filter(i_b[m_b], 31, 3) - poly_func(w_b[m_b])
        p_b, _ = find_peaks(flat_b, prominence=3.0, distance=30)
        if len(p_b) < 2: continue

        wb_v = w_b[m_b]
        cent = (wb_v[p_b[:-1]] + wb_v[p_b[1:]]) / 2
        i_idx = np.argmin(np.abs(cent - d['target_wl']))
        if i_idx + 1 >= len(p_b): continue

        lp, rp = p_b[i_idx], p_b[i_idx + 1]
        v_idx = lp + np.argmin(flat_b[lp:rp + 1])
        phase_res.append({'bias': b['bias'], 'v_wl': wb_v[v_idx]})

    if not phase_res: continue
    phase_res.sort(key=lambda x: x['bias'])
    z_data = next((p for p in phase_res if abs(p['bias']) < 1e-6), None)
    if not z_data: continue

    biases, phases = [], []
    for p in phase_res:
        biases.append(p['bias'])
        phases.append(((p['v_wl'] - z_data['v_wl']) / FSR) * 360.0)

    ph_arr = np.rad2deg(np.unwrap(np.deg2rad((np.array(phases) + 180) % 360 - 180)))

    plt.figure(figsize=(8, 5))
    plt.plot(biases, ph_arr, marker='o', lw=2)
    plt.axhline(0, ls='--', alpha=0.5)
    plt.axvline(0, ls='--', alpha=0.5)
    plt.xlabel("Bias Voltage (V)")
    plt.ylabel("Phase Shift (deg)")
    plt.title(f"{d['wafer_id']} ({d['die_c']},{d['die_r']}) {d['band']}\nPhase Shift")
    plt.grid(True)

    # --- 변경점: 날짜별 폴더 추가 ---
    date_str = d.get('date', 'Unknown_Date')
    coord_folder = f"HY202103_{d['wafer_id']}_({d['die_c']},{d['die_r']})_LION1_DCM_{d['band']}.png"

    # 2. 새로운 저장 경로: res / Wafer / 날짜 / 좌표
    w_dir = os.path.join(base_save_dir, d['wafer_id'], date_str, coord_folder)
    os.makedirs(w_dir, exist_ok=True)

    # 다른 코드들과 동일하게 밴드 정보를 파일명에 포함
    save_filename = f"{d['wafer_id']}_C{d['die_c']}_R{d['die_r']}_{d['band']}_Phase.png"
    plt.savefig(os.path.join(w_dir, save_filename), bbox_inches='tight')
    plt.close()

print("✅ Phase Shift 저장 완료")