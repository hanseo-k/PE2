import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from concurrent.futures import ProcessPoolExecutor
from data_parser import load_parsed
from analysis_utils import ref_poly


# 1. 병렬 코어들이 나누어서 실행할 독립적인 함수 (파일 최상단)
def _draw_and_save_flat(args):
    d, base_save_dir = args

    # 파장 범위 마스킹
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]

    # 데이터가 4개 미만이면 polyfit 불가능하므로 건너뜀
    if len(v_ref_wl) < 4:
        return None

    # 기준 데이터(REF) 3차 다항식 피팅
    poly = ref_poly(v_ref_wl, v_ref_il, smooth=False)

    # ------------------- 그래프 그리기 (Standard Style 적용) -------------------
    plt.figure(figsize=(10, 6))

    # 각 바이어스 데이터 평탄화 및 플롯 (선 두껍게 적용)
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

        plt.plot(v_wl, flat_il, label=b['label'], alpha=0.8, linewidth=2.5)

    # 평탄화된 기준 데이터 플롯 (다른 선들을 덮지 않도록 맨 마지막에 그리는 것이 좋습니다)
    plt.plot(v_ref_wl, v_ref_il - poly(v_ref_wl), label='REF',
             linewidth=2.5, color='black', alpha=0.8, linestyle='--')

    # [스타일 2] 제목, 축 라벨 크기 및 굵기 적용
    plt.title(f"Wafer: {d['wafer_id']} / Coord: ({d['die_c']}, {d['die_r']}) / Band: {d['band']} Flattened",
              fontsize=18, fontweight='bold', pad=15)
    plt.xlabel('Wavelength (nm)', fontsize=16, fontweight='bold')
    plt.ylabel('Transmission (dB)', fontsize=16, fontweight='bold')

    # y=0 기준선 굵게
    plt.axhline(0, color='gray', ls='--', linewidth=2)

    plt.xlim(d['wl_min'], d['wl_max'])
    plt.ylim(-65, 5)

    # [스타일 3] 축 눈금(Tick) 숫자 굵기 및 크기 적용
    plt.xticks(fontsize=13, fontweight='bold')
    plt.yticks(fontsize=13, fontweight='bold')

    # [스타일 4] 범례(Legend) 폰트 굵게
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
    save_dir = os.path.join(base_save_dir, d['wafer_id'], date_str)
    os.makedirs(save_dir, exist_ok=True)

    # 파일명 설정 (밴드 정보 포함)
    filename = f"{d['wafer_id']}_C{d['die_c']}_R{d['die_r']}_{d['band']}_Flat.png"

    # 날짜 폴더에 바로 파일 저장
    plt.savefig(os.path.join(save_dir, filename), bbox_inches='tight')
    plt.close()

    return filename


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

    print(f"▶ 기본 평탄화 플롯 생성 ({total_items}개, 병렬 처리 중)...")

    success_count = 0
    # 풀가동
    with ProcessPoolExecutor(max_workers=None) as ex:
        futures = [ex.submit(_draw_and_save_flat, t) for t in tasks]

        for f in futures:
            if f.result() is not None:
                success_count += 1

    print(f"✅ 기본 평탄화 저장 완료 (총 {success_count}개)")


if __name__ == "__main__":
    main()