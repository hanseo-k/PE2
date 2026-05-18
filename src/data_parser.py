import zipfile
import xml.etree.ElementTree as ET
import numpy as np
from datetime import datetime  # <--- 날짜 처리를 위해 추가


def parse_wafer_data(zip_path, target_wafers):
    """Zip 파일을 열어 XML 데이터를 파싱하고 다이(Die)별 데이터와 측정 날짜를 반환합니다."""
    with zipfile.ZipFile(zip_path, 'r') as myzip:
        for file_name in myzip.namelist():
            if not file_name.lower().endswith('.xml'): continue
            if not any(w in file_name for w in target_wafers): continue

            with myzip.open(file_name) as f:
                try:
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
                    wafer_id = next((w for w in target_wafers if w in file_name), "Unknown")

                    # =========================================================
                    # [수정된 부분] 날짜 정보 추출 및 'YYYYMMDD' 변환 로직
                    date_raw = info.get('Date') or root.get('Date') or root.get('CreationDate')
                    if not date_raw:
                        date_elem = root.find('.//Date') or root.find('.//CreationDate')
                        if date_elem is not None:
                            date_raw = date_elem.text

                    date_str = "Unknown_Date"
                    if date_raw:
                        date_clean = date_raw.split('.')[0].strip()  # 밀리초나 앞뒤 공백 제거

                        # XML에서 주로 나오는 날짜 포맷들
                        date_formats = [
                            "%a %b %d %H:%M:%S %Y",  # 예: Mon Mar 15 14:30:00 2021 (요일 포함)
                            "%Y-%m-%d %H:%M:%S",  # 예: 2021-03-15 14:30:00
                            "%Y-%m-%d",  # 예: 2021-03-15
                            "%Y-%m-%dT%H:%M:%S",  # 예: 2021-03-15T14:30:00
                            "%Y/%m/%d %H:%M:%S"  # 예: 2021/03/15 14:30:00
                        ]

                        for fmt in date_formats:
                            try:
                                dt = datetime.strptime(date_clean, fmt)
                                date_str = dt.strftime("%Y%m%d")  # 연도, 월, 일 (예: 20210315)
                                break
                            except ValueError:
                                continue

                        # 만약 위 포맷들에 전부 맞지 않는 특이한 문자열이라면, 특수문자와 띄어쓰기만 제거하고 그대로 사용
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
                                bias_val = float(bias_str);
                                label = f'{bias_val}V'
                            except:
                                bias_val = None;
                                label = f'Bias: {bias_str}'
                            bias_list.append({'bias': bias_val, 'wl': l_data, 'il': il_data, 'label': label})

                    if ref_data is None: continue

                    yield {
                        'wafer_id': wafer_id, 'band': band, 'die_c': die_c, 'die_r': die_r,
                        'wl_min': wl_min, 'wl_max': wl_max, 'target_wl': tgt_wl,
                        'date': date_str,  # <--- 변환된 연월일(YYYYMMDD) 추가
                        'ref_data': ref_data, 'bias_data_list': bias_list
                    }
                except Exception as e:
                    print(f"[{file_name}] 파싱 에러: {e}")