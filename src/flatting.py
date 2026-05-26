import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from concurrent.futures import ProcessPoolExecutor
from data_parser import parse_wafer_data


# 1. 병렬 코어들이 나누어서 실행할 독립적인 함수 (파일 최상단)
def _draw_and_save_flat(args):
    d, base_save_dir = args

    # 파장 범위 마스킹
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]

    # 데이터가 4개 미만이면 polyfit 불가능하므로 건너뜀 (기존의 continue)
    if len(v_ref_wl) < 4:
        return None

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

    # 그래프 꾸미기
    plt.title(f"Wafer: {d['wafer_id']} / Coord: ({d['die_c']}, {d['die_r']}) / Band: {d['band']} Flattened")
    plt.xlabel('Wavelength [nm]')
    plt.ylabel('Transmission [dB]')
    plt.axhline(0, color='gray', ls='--')
    plt.xlim(d['wl_min'], d['wl_max'])
    plt.ylim(-65, 5)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, ls='--')

    # 2. 날짜 정보 가져오기 (이전 코드와 동일한 방식 적용)
    date_str = d.get('date', 'Unknown_Date')
    coord_folder = f"HY202103_{d['wafer_id']}_({d['die_c']},{d['die_r']})_LION1_DCM_{d['band']}.png"

    # 3. 새로운 저장 경로: res / Wafer / 날짜 / 좌표
    save_dir = os.path.join(base_save_dir, d['wafer_id'], date_str, coord_folder)
    os.makedirs(save_dir, exist_ok=True)

    # 파일명에 밴드 정보 포함
    filename = f"{d['wafer_id']}_C{d['die_c']}_R{d['die_r']}_{d['band']}_Flat.png"

    # 4. 변경된 좌표별 폴더에 파일 저장
    plt.savefig(os.path.join(save_dir, filename), bbox_inches='tight')
    plt.close()

    return filename


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

    print(f"▶ 기본 평탄화 플롯 생성 ({total_items}개, 병렬 처리 중)...")

    success_count = 0
    # 8코어 풀가동
    with ProcessPoolExecutor(max_workers=None) as ex:
        futures = [ex.submit(_draw_and_save_flat, t) for t in tasks]

        for f in futures:
            if f.result() is not None:
                success_count += 1

    print(f"✅ 기본 평탄화 저장 완료 (총 {success_count}개)")


if __name__ == "__main__":
    main()