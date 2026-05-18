import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from data_parser import parse_wafer_data

zip_path = "../dat/HY202103.zip"
base_save_dir = "../res/Flatting"
target_wafers = ['D07', 'D08', 'D23', 'D24']

# 1. 데이터 파싱
for d in parse_wafer_data(zip_path, target_wafers):

    # 파장 범위 마스킹
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]

    if len(v_ref_wl) < 4:
        continue

    # 기준 데이터(REF) 3차 다항식 피팅
    poly = np.poly1d(np.polyfit(v_ref_wl, v_ref_il, 3))

    plt.figure(figsize=(10, 6))

    # 평탄화된 기준 데이터 플롯
    plt.plot(v_ref_wl, v_ref_il - poly(v_ref_wl), label='REF', color='black', lw=2.5)

    # 각 바이어스 데이터 평탄화 및 플롯
    for b in d['bias_data_list']:
        m_b = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        v_wl, v_il = b['wl'][m_b], b['il'][m_b]
        if len(v_wl) == 0:
            continue

        # 3차 다항식을 이용한 1차 평탄화
        flat_il = v_il - poly(v_wl)

        # 피크를 찾아서 선형 피팅(1차 다항식)으로 2차 평탄화 (기울기 보정)
        peaks, _ = find_peaks(flat_il, prominence=3.0, distance=30)
        if len(peaks) >= 2:
            linear_fit = np.poly1d(np.polyfit(v_wl[peaks], flat_il[peaks], 1))
            flat_il -= linear_fit(v_wl)

        plt.plot(v_wl, flat_il, label=b['label'], alpha=0.8)

    # 그래프 꾸미기 (두 번째 코드의 스타일 참고하여 제목에 밴드 정보 추가)
    plt.title(f"Wafer: {d['wafer_id']} / Coord: ({d['die_c']}, {d['die_r']}) / Band: {d['band']} Flattened")
    plt.xlabel('Wavelength [nm]')
    plt.ylabel('Transmission [dB]')
    plt.axhline(0, color='gray', ls='--')
    plt.xlim(d['wl_min'], d['wl_max'])
    plt.ylim(-65, 5)  # 두 번째 코드의 y축 범위 적용 (필요에 따라 조정)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')  # 범례 위치 조정
    plt.grid(True, ls='--')

    # 저장 디렉토리 생성 및 저장
    w_dir = os.path.join(base_save_dir, d['wafer_id'])
    os.makedirs(w_dir, exist_ok=True)

    # 파일명에 밴드 정보 포함
    filename = f"{d['wafer_id']}_C{d['die_c']}_R{d['die_r']}_{d['band']}_Flat.png"
    plt.savefig(os.path.join(w_dir, filename), bbox_inches='tight')
    plt.close()

print("✅ 기본 평탄화 저장 완료")