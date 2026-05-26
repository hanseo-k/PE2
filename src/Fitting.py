import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from concurrent.futures import ProcessPoolExecutor
from data_parser import parse_wafer_data


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

        plt.plot(v_wl, flat_il, label=b['label'], alpha=0.8)

    plt.title(
        f"Wafer: {d['wafer_id']} / Coord: ({d['die_c']}, {d['die_r']}) / Band: {d['band']}\nSmoothed, Flattened & Zoomed")
    plt.xlabel('Wavelength [nm]')
    plt.ylabel('Transmission [dB]')
    plt.axhline(0, color='gray', ls='--', alpha=0.6)

    plt.xlim(z_min, z_max)
    plt.legend(bbox_to_anchor=(1.25, 1.0))
    plt.grid(True, ls='--', alpha=0.7)

    # --- 날짜별 폴더 추가 및 저장 ---
    date_str = d.get('date', 'Unknown_Date')
    coord_folder = f"HY202103_{d['wafer_id']}_({d['die_c']},{d['die_r']})_LION1_DCM_{d['band']}.png"

    w_dir = os.path.join(base_save_dir, d['wafer_id'], date_str, coord_folder)
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
    parsed_data_list = list(parse_wafer_data(zip_path, target_wafers))
    total_items = len(parsed_data_list)

    # 각 코어에 넘겨줄 작업 튜플 리스트 생성
    tasks = [(d, base_save_dir) for d in parsed_data_list]

    print(f"▶ 리플 제거 및 확대 플롯 생성 ({total_items}개, 병렬 처리 중)...")

    success_count = 0
    # 8코어 풀가동
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