import os
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor
from data_parser import parse_wafer_data


# 1. 병렬 코어들이 나누어서 실행할 독립적인 함수 (파일 최상단에 위치)
def _draw_and_save_plot(args):
    # args로 묶여서 전달된 데이터(d)와 저장 경로(base_save_dir)를 풀어줍니다.
    d, base_save_dir = args

    # ------------------- 그래프 그리기 -------------------
    plt.figure(figsize=(10, 6))
    for b in d['bias_data_list']:
        plt.plot(b['wl'], b['il'], label=b['label'])
    plt.plot(d['ref_data']['wl'], d['ref_data']['il'], label=d['ref_data']['label'])

    plt.title(f"Wafer: {d['wafer_id']} / Coord: ({d['die_c']}, {d['die_r']}) / Band: {d['band']}")
    plt.ylim(-65, 5)
    plt.xlabel("Wavelength (nm)")
    plt.ylabel("IL (dB)")
    plt.legend(loc='best')
    plt.grid(True)

    # ------------------- 저장 경로 설정 -------------------
    date_str = d.get('date', 'Unknown_Date')
    coord_folder = f"HY202103_{d['wafer_id']}_({d['die_c']},{d['die_r']})_LION1_DCM_{d['band']}.png"
    w_dir = os.path.join(base_save_dir, d['wafer_id'], date_str, coord_folder)
    os.makedirs(w_dir, exist_ok=True)

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
    # 메모리가 충분하다면 리스트로 변환하는 것이 병렬 처리 분배에 좋습니다.
    parsed_data_list = list(parse_wafer_data(zip_path, target_wafers))
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
            # 진행률을 보고 싶다면 아래 주석을 해제하세요.
            # if i % 10 == 0:
            #     print(f"   - 진행 상황: {i}/{total_tasks} 완료")

    print(f"✅ 총 {total_tasks}개 플롯 저장 완료")


# 5. 멀티프로세싱 필수 보호 구문 (이 파일이 직접 실행될 때만 main() 동작)
if __name__ == "__main__":
    main()