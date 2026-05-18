import os
import matplotlib.pyplot as plt
from data_parser import parse_wafer_data

zip_path = "../dat/HY202103.zip"
base_save_dir = "../res"
target_wafers = ['D07', 'D08', 'D23', 'D24']

for d in parse_wafer_data(zip_path, target_wafers):
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

    # 1. XML 데이터에서 날짜 정보 가져오기 (예: '20190531')
    date_str = d.get('date', 'Unknown_Date')

    # 2. 좌표별 하위 폴더명
    coord_folder = f"C{d['die_c']}_R{d['die_r']}"

    # 3. 새로운 저장 경로: res / 20190531 / Wafer / 좌표
    w_dir = os.path.join(base_save_dir, d['wafer_id'], date_str, coord_folder)
    os.makedirs(w_dir, exist_ok=True)

    # 4. 파일 저장
    save_filename = f"{d['wafer_id']}_C{d['die_c']}_R{d['die_r']}_{d['band']}_Raw.png"
    plt.savefig(os.path.join(w_dir, save_filename), bbox_inches='tight')
    plt.close()

print("✅ 플롯 저장 완료")