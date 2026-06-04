import os
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor
from data_parser import load_parsed


# 1. 병렬 코어들이 나누어서 실행할 독립적인 함수 (파일 최상단에 위치)
def _draw_and_save_plot(args):
    # args로 묶여서 전달된 데이터(d)와 저장 경로(base_save_dir)를 풀어줍니다.
    d, base_save_dir = args

    # ------------------- 그래프 그리기 (Standard Style 적용) -------------------
    plt.figure(figsize=(10, 6))

    # [스타일 1] 데이터 선 두껍게 (linewidth=2.5)
    for b in d['bias_data_list']:
        plt.plot(b['wl'], b['il'], label=b['label'], linewidth=2.5)

    # Reference 데이터 선 굵게 (검은색 점선으로 강조하면 더 좋습니다, 필요에 따라 컬러 변경 가능)
    plt.plot(d['ref_data']['wl'], d['ref_data']['il'], label=d['ref_data']['label'],
             linewidth=2.5, color='black', alpha=0.8, linestyle='--')

    # [스타일 2] 제목, 축 라벨 크기 및 굵기 적용
    plt.title(f"Wafer: {d['wafer_id']} / Coord: ({d['die_c']}, {d['die_r']}) / Band: {d['band']}",
              fontsize=18, fontweight='bold', pad=15)
    plt.xlabel("Wavelength (nm)", fontsize=16, fontweight='bold')
    plt.ylabel("Transmission (dB)", fontsize=16, fontweight='bold')
    plt.ylim(-65, 5)

    # [스타일 3] 축 눈금(Tick) 숫자 굵기 및 크기 적용
    plt.xticks(fontsize=13, fontweight='bold')
    plt.yticks(fontsize=13, fontweight='bold')

    # [스타일 4] 범례(Legend) 폰트 굵게
    plt.legend(loc='best', prop={'size': 12, 'weight': 'bold'})

    # [스타일 5] 격자(Grid) 점선 및 반투명 처리 (데이터 방해 최소화)
    plt.grid(True, linestyle='--', alpha=0.6, linewidth=1)

    # [스타일 6] 그래프 테두리(Spines) 두껍게
    ax = plt.gca()
    for spine in ax.spines.values():
        spine.set_linewidth(2)

    # [스타일 7] 불필요한 여백 제거
    plt.tight_layout()

    # ------------------- 저장 경로 설정 -------------------
    date_str = d.get('date', 'Unknown_Date')

    # coord_folder를 거치지 않고 웨이퍼ID/날짜 폴더까지만 생성하여 바로 위치시킵니다.
    w_dir = os.path.join(base_save_dir, d['wafer_id'], date_str)
    os.makedirs(w_dir, exist_ok=True)

    # 날짜 폴더 안에 모든 좌표 파일들이 모이므로 구분하기 편하도록 기존 파일명 구조를 유지합니다.
    save_filename = f"{d['wafer_id']}_C{d['die_c']}_R{d['die_r']}_{d['band']}_Raw.png"

    # ------------------- 파일 저장 및 메모리 해제 -------------------
    plt.savefig(os.path.join(w_dir, save_filename), bbox_inches='tight')
    plt.close()  # 중요: plt.close()를 해야 코어 메모리가 누수되지 않습니다.

    return save_filename  # 성공적으로 완료되었음을 알림


def main():
    zip_path = "../dat/HY202103"
    base_save_dir = "../res/png"
    target_wafers = ['D07', 'D08', 'D23', 'D24']

    print("▶ 데이터 파싱을 시작합니다...")
    # 2. 제너레이터에서 데이터를 모두 추출하여 리스트로 만듭니다. (작업 분배용)
    parsed_data_list = load_parsed(zip_path, target_wafers)
    total_tasks = len(parsed_data_list)
    print(f"▶ 총 {total_tasks}개의 그래프 데이터를 불러왔습니다.")

    # 3. 각 코어에 넘겨줄 작업(Task) 리스트 생성
    tasks = [(d, base_save_dir) for d in parsed_data_list]

    print("▶ 플롯 생성 (가용 코어 최대 활용 병렬 처리 중)...")

    # 4. ProcessPoolExecutor를 이용한 병렬 플로팅
    with ProcessPoolExecutor(max_workers=None) as ex:
        futures = [ex.submit(_draw_and_save_plot, t) for t in tasks]

        # 진행 상황 확인 (선택 사항)
        for i, f in enumerate(futures, 1):
            f.result()  # 에러 발생 시 여기서 멈추고 에러 로그를 보여줌

    print(f"✅ 총 {total_tasks}개 플롯 저장 완료")


# 5. 멀티프로세싱 필수 보호 구문 (이 파일이 직접 실행될 때만 main() 동작)
if __name__ == "__main__":
    main()