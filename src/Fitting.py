import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from data_parser import parse_wafer_data

zip_path = "../dat/HY202103.zip"
base_save_dir = "../res"
target_wafers = ['D07', 'D08', 'D23', 'D24']
count = 0

for d in parse_wafer_data(zip_path, target_wafers):
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]

    # Savitzky-Golay 필터 윈도우(31)보다 데이터가 적으면 에러가 나므로 예외 처리
    if len(v_ref_wl) < 31:
        continue

    sm_ref = savgol_filter(v_ref_il, 31, 3)
    poly = np.poly1d(np.polyfit(v_ref_wl, sm_ref, 3))

    plt.figure(figsize=(10, 6))
    plt.plot(v_ref_wl, sm_ref - poly(v_ref_wl), label='REF', color='black', lw=2.5, zorder=10)

    z_min, z_max = d['wl_min'], d['wl_max']
    tgt_bias = next((b for b in d['bias_data_list'] if b['bias'] == -2.0),
                    d['bias_data_list'][0] if d['bias_data_list'] else None)

    if tgt_bias:
        m_t = (tgt_bias['wl'] >= d['wl_min']) & (tgt_bias['wl'] <= d['wl_max'])
        w_t, i_t = tgt_bias['wl'][m_t], tgt_bias['il'][m_t]

        if len(w_t) >= 31:
            flat_t = savgol_filter(i_t, 31, 3) - poly(w_t)
            peaks, _ = find_peaks(flat_t, prominence=3.0, distance=30)

            if len(peaks) >= 2:
                centers = (w_t[peaks[:-1]] + w_t[peaks[1:]]) / 2.0

                # 밴드 정보(O밴드 등)에 따라 타겟 파장(target_wl) 설정
                # d 딕셔너리에 target_wl이 제대로 안 들어있을 경우를 대비한 안전장치
                band_str = str(d.get('band', '')).upper()
                if 'O' in band_str:
                    target_wl = d.get('target_wl', 1310.0)  # O-band 기본 중심
                else:
                    target_wl = d.get('target_wl', 1550.0)  # C/L-band 기본 중심

                # 타겟 파장과 가장 가까운 피크 중앙값 찾기
                idx = np.argmin(np.abs(centers - target_wl))

                # 인덱스 초과 에러 방지
                if idx + 1 < len(peaks):
                    z_min, z_max = w_t[peaks[idx]] - 0.5, w_t[peaks[idx + 1]] + 0.5

    for b in d['bias_data_list']:
        m_b = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        v_wl, v_il = b['wl'][m_b], b['il'][m_b]
        if len(v_wl) < 31:
            continue

        flat_il = savgol_filter(v_il, 31, 3) - poly(v_wl)
        peaks, _ = find_peaks(flat_il, prominence=3.0, distance=30)

        if len(peaks) >= 2:
            flat_il -= np.poly1d(np.polyfit(v_wl[peaks], flat_il[peaks], 1))(v_wl)

        plt.plot(v_wl, flat_il, label=b['label'], alpha=0.8)

    plt.title(
        f"Wafer: {d['wafer_id']} / Coord: ({d['die_c']}, {d['die_r']}) / Band: {d['band']}\nSmoothed, Flattened & Zoomed")
    plt.xlabel('Wavelength [nm]')
    plt.ylabel('Transmission [dB]')
    plt.axhline(0, color='gray', ls='--', alpha=0.6)

    # 계산된 확대 구간(z_min, z_max) 적용
    plt.xlim(z_min, z_max)
    plt.legend(bbox_to_anchor=(1.25, 1.0))
    plt.grid(True, ls='--', alpha=0.7)

    # --- 변경된 부분: 날짜별 폴더 추가 ---
    date_str = d.get('date', 'Unknown_Date')
    coord_folder = f"C{d['die_c']}_R{d['die_r']}"

    # 새로운 저장 경로: res / Wafer / 날짜 / 좌표
    w_dir = os.path.join(base_save_dir, d['wafer_id'], date_str, coord_folder)
    os.makedirs(w_dir, exist_ok=True)

    # 밴드 정보를 포함하여 저장
    save_filename = f"{d['wafer_id']}_C{d['die_c']}_R{d['die_r']}_{d['band']}_Zoomed.png"
    plt.savefig(os.path.join(w_dir, save_filename), bbox_inches='tight')
    plt.close()

    count += 1

print(f"✅ 리플 제거 및 확대 그래프 저장 완료 (총 {count}개)")