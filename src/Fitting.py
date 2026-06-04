import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from concurrent.futures import ProcessPoolExecutor
from data_parser import load_parsed


# 1. 각 코어가 독립적으로 가져가서 실행할 메인 작업 함수
def _draw_and_save_zoomed_plot(args):
    d, base_save_dir = args

    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]

    # Savitzky-Golay 필터 윈도우(31)보다 데이터가 적으면 에러가 나므로 건너뜀
    if len(v_ref_wl) < 31:
        return None  # 기존의 continue 역할을 대신함

    sm_ref = savgol_filter(v_ref_il, 31, 3)
    poly = np.poly1d(np.polyfit(v_ref_wl, sm_ref, 3))
    y_fitted = poly(v_ref_wl)

    # --- R^2 (결정계수) 계산 ---
    ss_res = np.sum((sm_ref - y_fitted) ** 2)  # 잔차 제곱합
    ss_tot = np.sum((sm_ref - np.mean(sm_ref)) ** 2)  # 총 제곱합

    # ss_tot가 0인 경우(데이터가 완전히 평탄한 경우)를 방지하기 위한 예외 처리
    if ss_tot == 0:
        r_squared = 1.0
    else:
        r_squared = 1 - (ss_res / ss_tot)
    # ---------------------------

    # ------------------- 그래프 그리기 (Standard Style 적용) -------------------
    plt.figure(figsize=(10, 6))

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

                band_str = str(d.get('band', '')).upper()
                if 'O' in band_str:
                    target_wl = d.get('target_wl', 1310.0)
                else:
                    target_wl = d.get('target_wl', 1550.0)

                idx = np.argmin(np.abs(centers - target_wl))

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

        # [스타일 1] 데이터 선 두껍게
        plt.plot(v_wl, flat_il, label=b['label'], alpha=0.8, linewidth=2.5)

    # 범례에 계산된 R^2 값을 표시 (다른 선들을 덮지 않도록 맨 마지막에 플로팅)
    # [스타일 1.5] Reference 라인은 굵은 점선 처리
    plt.plot(v_ref_wl, sm_ref - y_fitted, label=f'REF (R^2={r_squared:.4f})',
             color='black', lw=2.5, zorder=10, linestyle='--')

    # [스타일 2] 제목, 축 라벨 크기 및 굵기 적용
    plt.title(
        f"Wafer: {d['wafer_id']} / Coord: ({d['die_c']}, {d['die_r']}) / Band: {d['band']}\nSmoothed, Flattened & Zoomed",
        fontsize=18, fontweight='bold', pad=15)
    plt.xlabel('Wavelength (nm)', fontsize=16, fontweight='bold')
    plt.ylabel('Transmission (dB)', fontsize=16, fontweight='bold')

    # y=0 기준선 굵게
    plt.axhline(0, color='gray', ls='--', alpha=0.6, linewidth=2)

    plt.xlim(z_min, z_max)

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

    # --- 날짜별 폴더 하위에 바로 저장 ---
    date_str = d.get('date', 'Unknown_Date')

    # coord_folder를 거치지 않고 wafer_id와 date_str 폴더까지만 경로로 지정합니다.
    w_dir = os.path.join(base_save_dir, d['wafer_id'], date_str)
    os.makedirs(w_dir, exist_ok=True)

    save_filename = f"{d['wafer_id']}_C{d['die_c']}_R{d['die_r']}_{d['band']}_Fitting.png"
    plt.savefig(os.path.join(w_dir, save_filename), bbox_inches='tight')
    plt.close()

    return save_filename  # 성공 시 파일명 반환


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

    print(f"▶ 리플 제거 및 확대 플롯 생성 ({total_items}개, 병렬 처리 중)...")

    success_count = 0
    # 풀가동
    with ProcessPoolExecutor(max_workers=None) as ex:
        futures = [ex.submit(_draw_and_save_zoomed_plot, t) for t in tasks]

        for f in futures:
            result = f.result()  # 반환값 확인
            # 데이터 개수 부족(<31)으로 None이 반환된 게 아니라면 카운트 증가
            if result is not None:
                success_count += 1

    print(f"✅ 리플 제거 및 확대 그래프 저장 완료 (총 {success_count}개)")


if __name__ == "__main__":
    main()