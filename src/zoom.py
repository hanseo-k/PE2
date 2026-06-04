import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from concurrent.futures import ProcessPoolExecutor
from data_parser import load_parsed
from analysis_utils import ref_poly


# 1. 병렬 코어들이 나누어서 실행할 독립적인 함수 (파일 최상단)
def _draw_and_save_zoom_only(args):
    d, base_save_dir = args

    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]

    # 데이터가 4개 미만이면 polyfit을 할 수 없으므로 건너뜀 (기존의 continue 역할)
    if len(v_ref_wl) < 4:
        return None

    poly = ref_poly(v_ref_wl, v_ref_il, smooth=False)
    z_min, z_max = d['wl_min'], d['wl_max']

    t_bias = next((b for b in d['bias_data_list'] if b['bias'] == -2.0),
                  d['bias_data_list'][0] if d['bias_data_list'] else None)

    if t_bias:
        mt = (t_bias['wl'] >= d['wl_min']) & (t_bias['wl'] <= d['wl_max'])
        wt, it = t_bias['wl'][mt], t_bias['il'][mt]
        peaks, _ = find_peaks(it - poly(wt), prominence=3.0, distance=30)

        if len(peaks) >= 2:
            cent = (wt[peaks[:-1]] + wt[peaks[1:]]) / 2.0

            # --- 이전 코드와 동일한 O밴드 처리 로직 적용 ---
            band_str = str(d.get('band', '')).upper()
            if 'O' in band_str:
                target_wl = d.get('target_wl', 1310.0)  # O-band
            else:
                target_wl = d.get('target_wl', 1550.0)  # C/L-band

            idx = np.argmin(np.abs(cent - target_wl))

            # 인덱스 초과 방지 안전장치
            if idx + 1 < len(peaks):
                z_min, z_max = wt[peaks[idx]] - 0.5, wt[peaks[idx + 1]] + 0.5

    # ------------------- 그래프 그리기 (Standard Style 적용) -------------------
    plt.figure(figsize=(10, 6))

    for b in d['bias_data_list']:
        mb = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        wb, ib = b['wl'][mb], b['il'][mb]

        if len(wb) == 0:
            continue

        flat = ib - poly(wb)
        peaks, _ = find_peaks(flat, prominence=3.0, distance=30)
        if len(peaks) >= 2:
            flat -= np.poly1d(np.polyfit(wb[peaks], flat[peaks], 1))(wb)

        # [스타일 1] 데이터 선 두껍게
        plt.plot(wb, flat, label=b['label'], alpha=0.8, linewidth=2.5)

    # 0 기준선 굵게
    plt.axhline(0, color='gray', ls='--', linewidth=2)
    plt.xlim(z_min, z_max)

    # [스타일 2] 제목, 축 라벨 크기 및 굵기 적용
    plt.title(f"Wafer: {d['wafer_id']} / Coord: ({d['die_c']}, {d['die_r']}) / Band: {d['band']} Zoom Only",
              fontsize=18, fontweight='bold', pad=15)
    plt.xlabel('Wavelength (nm)', fontsize=16, fontweight='bold')
    plt.ylabel('Transmission (dB)', fontsize=16, fontweight='bold')

    # [스타일 3] 축 눈금(Tick) 숫자 굵기 및 크기 적용
    plt.xticks(fontsize=13, fontweight='bold')
    plt.yticks(fontsize=13, fontweight='bold')

    # [스타일 4] 범례(Legend) 폰트 굵게 및 최적 위치 배치
    plt.legend(loc='best', prop={'size': 12, 'weight': 'bold'})

    # [스타일 5] 격자(Grid) 점선 및 반투명 처리
    plt.grid(True, linestyle='--', alpha=0.6, linewidth=1)

    # [스타일 6] 그래프 테두리(Spines) 두껍게
    ax = plt.gca()
    for spine in ax.spines.values():
        spine.set_linewidth(2)

    # [스타일 7] 불필요한 여백 제거
    plt.tight_layout()

    # ------------------- 저장 경로 설정 -------------------
    date_str = d.get('date', 'Unknown_Date')

    # coord_folder를 거치지 않고 wafer_id와 date_str 폴더까지만 생성
    w_dir = os.path.join(base_save_dir, d['wafer_id'], date_str)
    os.makedirs(w_dir, exist_ok=True)

    # 결과 예시: D07_C1_R2_LMZO_Zoom.png
    save_filename = f"{d['wafer_id']}_C{d['die_c']}_R{d['die_r']}_{d['band']}_Zoom.png"

    # 날짜 폴더 안에 파일 바로 저장
    plt.savefig(os.path.join(w_dir, save_filename), bbox_inches='tight')
    plt.close()

    return save_filename


def main():
    zip_path = "../dat/HY202103"
    base_save_dir = "../res/png"
    target_wafers = ['D07', 'D08', 'D23', 'D24']

    print("▶ 데이터 파싱을 시작합니다...")
    # 파싱된 데이터를 리스트로 변환하여 메모리에 적재
    parsed_data_list = load_parsed(zip_path, target_wafers)
    total_items = len(parsed_data_list)

    # 각 코어에 넘겨줄 작업 튜플 리스트 생성
    tasks = [(d, base_save_dir) for d in parsed_data_list]

    print(f"▶ 줌 전용 플롯 생성 ({total_items}개, 병렬 처리 중)...")

    success_count = 0
    # 풀가동
    with ProcessPoolExecutor(max_workers=None) as ex:
        futures = [ex.submit(_draw_and_save_zoom_only, t) for t in tasks]

        for f in futures:
            if f.result() is not None:
                success_count += 1

    print(f"✅ 줌 전용 저장 완료 (총 {success_count}개)")


if __name__ == "__main__":
    main()