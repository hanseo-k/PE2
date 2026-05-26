import os
import xml.etree.ElementTree as ET
import numpy as np
from datetime import datetime


def parse_wafer_data(data_path, target_wafers):
    """지정된 폴더(data_path)를 탐색하여 XML 데이터를 파싱하고 다이(Die)별 데이터와 측정 날짜를 반환합니다."""

    # os.walk를 사용하여 폴더 내의 모든 파일을 재귀적으로(하위 폴더까지) 탐색합니다.
    for root_dir, dirs, files in os.walk(data_path):
        for file_name in files:
            if not file_name.lower().endswith('.xml'):
                continue

            # 파일 경로 전체를 문자열로 만듭니다.
            file_path = os.path.join(root_dir, file_name)

            # 파일 경로나 이름에 타겟 웨이퍼(D07, D08 등)가 포함되어 있는지 확인
            if not any(w in file_path for w in target_wafers):
                continue

            try:
                # 일반 폴더에 있는 파일이므로 open() 함수로 바로 엽니다.
                with open(file_path, 'r', encoding='utf-8') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()

                    info = root.find('.//TestSiteInfo')
                    if info is None: continue

                    test_site = info.get('TestSite', '')
                    if 'LMZO' in test_site.upper():
                        band, wl_min, wl_max, tgt_wl = 'LMZO', 1260.0, 1360.0, 1310.0
                    elif 'LMZC' in test_site.upper():
                        band, wl_min, wl_max, tgt_wl = 'LMZC', 1520.0, 1580.0, 1550.0
                    else:
                        continue

                    die_c = int(info.get('DieRow', 0)) if info.get('DieRow') else 0
                    die_r = int(info.get('DieColumn', 0)) if info.get('DieColumn') else 0

                    # 웨이퍼 아이디는 파일명이나 폴더명(경로)에 포함되어 있는지 확인하여 추출
                    wafer_id = next((w for w in target_wafers if w in file_path), "Unknown")

                    # =========================================================
                    # 날짜 정보 추출 및 'YYYYMMDD' 변환 로직 (기존 로직 유지)
                    date_raw = info.get('Date') or root.get('Date') or root.get('CreationDate')
                    if not date_raw:
                        date_elem = root.find('.//Date') or root.find('.//CreationDate')
                        if date_elem is not None:
                            date_raw = date_elem.text

                    date_str = "Unknown_Date"
                    if date_raw:
                        date_clean = date_raw.split('.')[0].strip()

                        date_formats = [
                            "%a %b %d %H:%M:%S %Y",
                            "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%d",
                            "%Y-%m-%dT%H:%M:%S",
                            "%Y/%m/%d %H:%M:%S"
                        ]

                        for fmt in date_formats:
                            try:
                                dt = datetime.strptime(date_clean, fmt)
                                date_str = dt.strftime("%Y%m%d")
                                break
                            except ValueError:
                                continue

                        if date_str == "Unknown_Date":
                            date_str = "".join(filter(str.isalnum, date_clean))
                    # =========================================================

                    sweeps = root.findall('.//WavelengthSweep')
                    if not sweeps or len(sweeps) < 2: continue

                    ref_data = None
                    bias_list = []

                    for i, sweep in enumerate(sweeps):
                        l_elem, il_elem = sweep.find('L'), sweep.find('IL')
                        if l_elem is None or il_elem is None: continue

                        l_data = np.array(list(map(float, l_elem.text.split(','))))
                        il_data = np.array(list(map(float, il_elem.text.split(','))))
                        bias_str = sweep.get('DCBias', '')

                        if i == len(sweeps) - 1:
                            ref_data = {'wl': l_data, 'il': il_data, 'label': 'REF'}
                        else:
                            try:
                                bias_val = float(bias_str)
                                label = f'{bias_val}V'
                            except:
                                bias_val = None
                                label = f'Bias: {bias_str}'
                            bias_list.append({'bias': bias_val, 'wl': l_data, 'il': il_data, 'label': label})

                    if ref_data is None: continue

                    yield {
                        'wafer_id': wafer_id, 'band': band, 'die_c': die_c, 'die_r': die_r,
                        'wl_min': wl_min, 'wl_max': wl_max, 'target_wl': tgt_wl,
                        'date': date_str,
                        'ref_data': ref_data, 'bias_data_list': bias_list
                    }
            except Exception as e:
                print(f"[{file_path}] 파싱 에러: {e}")