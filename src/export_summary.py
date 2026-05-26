import os
import numpy as np
import pandas as pd
from scipy.signal import find_peaks, savgol_filter
from data_parser import parse_wafer_data
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# ==========================================================
# [설정] 아웃라이어(Outlier) 및 에러 판단 기준
# ==========================================================
THRESHOLD = {
    'IL_MIN': -20.0,
    'ER_MIN': 10.0,
    'VPIL_MIN': 0.2,
    'VPIL_MAX': 3.0
}

zip_path = "../dat/HY202103"
save_dir = "../res/csv"
os.makedirs(save_dir, exist_ok=True)

target_wafers = ['D07', 'D08', 'D23', 'D24']
L_length = 0.05


def q_sub(x, y):
    if len(x) < 3: return x[np.argmin(y)]
    idx = np.argmin(y)
    if idx == 0 or idx == len(x) - 1: return x[idx]
    c = np.polyfit(x[idx - 1:idx + 2], y[idx - 1:idx + 2], 2)
    return -c[1] / (2 * c[0]) if abs(c[0]) > 1e-12 else x[idx]


def check_status(row):
    reasons = []
    if pd.isna(row['IL_dB']):
        reasons.append("IL 데이터 없음")
    elif row['IL_dB'] < THRESHOLD['IL_MIN']:
        reasons.append(f"IL 손실 과다(<{THRESHOLD['IL_MIN']})")

    if pd.isna(row['ER_dB']):
        reasons.append("ER 데이터 없음")
    elif row['ER_dB'] < THRESHOLD['ER_MIN']:
        reasons.append(f"ER 낮음(<{THRESHOLD['ER_MIN']})")

    if pd.isna(row['VpiL_Vcm']):
        reasons.append("VpiL 계산 실패")
    elif row['VpiL_Vcm'] < THRESHOLD['VPIL_MIN'] or row['VpiL_Vcm'] > THRESHOLD['VPIL_MAX']:
        reasons.append(f"VpiL 범위 초과({THRESHOLD['VPIL_MIN']}~{THRESHOLD['VPIL_MAX']})")

    return ("정상", "") if not reasons else ("이상 발생", ", ".join(reasons))


# ==========================================================
# 엑셀 서식 자동 적용 함수
# ==========================================================
def apply_excel_style(worksheet, dataframe):
    header_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)
    error_fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
    link_font = Font(color='0563C1', underline='single')
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'),
                    bottom=Side(style='thin'))

    col_idx = {col: i for i, col in enumerate(dataframe.columns, 1)}

    for col_num, column_title in enumerate(dataframe.columns, 1):
        cell = worksheet.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

        for row_num in range(2, len(dataframe) + 2):
            data_cell = worksheet.cell(row=row_num, column=col_num)
            data_cell.border = border

            # 1. 폴더 열기 하이퍼링크 설정
            if column_title == 'Folder_Link':
                target_folder = data_cell.value
                if target_folder:
                    data_cell.value = f'=HYPERLINK("{target_folder}", "📁 폴더 열기")'
                    data_cell.font = link_font
                    data_cell.alignment = Alignment(horizontal='center')

            # 2. 이미지 확인 하이퍼링크 설정
            elif column_title == 'Image_Link':
                target_image = data_cell.value
                if target_image:
                    data_cell.value = f'=HYPERLINK("{target_image}", "🖼️ Summary 확인")'
                    data_cell.font = link_font
                    data_cell.alignment = Alignment(horizontal='center')

            else:
                if column_title in ['IL_dB', 'ER_dB', 'VpiL_Vcm'] and isinstance(data_cell.value, (int, float)):
                    data_cell.number_format = '0.000'

            # 에러 행 하이라이트 (링크 컬럼 제외)
            if 'Status' in col_idx:
                status_value = worksheet.cell(row=row_num, column=col_idx['Status']).value
                if status_value == "이상 발생" and column_title not in ['Folder_Link', 'Image_Link']:
                    data_cell.fill = error_fill

    for col in worksheet.columns:
        max_length = 0
        column_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value is not None:
                text = str(cell.value)
                max_length = max(max_length, sum(2 if ord(c) > 127 else 1 for c in text))
        worksheet.column_dimensions[column_letter].width = min(max_length + 3, 50)


# ==========================================================
# 메인 실행 블록
# ==========================================================
print("🚀 데이터 분석을 시작합니다...")
summary_list = []
count = 0

for d in parse_wafer_data(zip_path, target_wafers):
    wafer, band, c, r = d['wafer_id'], d['band'], d['die_c'], d['die_r']
    radius = np.sqrt(c ** 2 + r ** 2)
    date_str = d.get('date', 'Unknown_Date')

    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(v_ref_wl) < 31: continue
    poly_func = np.poly1d(np.polyfit(v_ref_wl, savgol_filter(v_ref_il, 31, 3), 3))

    max_peak = float('-inf')
    for b in d['bias_data_list']:
        if b['bias'] is None: continue
        mb = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        if np.any(mb):
            max_peak = max(max_peak, np.max(b['il'][mb]))
    il_val = max_peak if max_peak != float('-inf') else np.nan

    max_er = 0.0
    for b in d['bias_data_list']:
        if b['bias'] is None: continue
        mb = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        v_wl, v_il = b['wl'][mb], b['il'][mb]
        if len(v_wl) == 0: continue
        flat_il = v_il - poly_func(v_wl)
        peaks, _ = find_peaks(flat_il, prominence=3.0, distance=30)
        final_il = flat_il - np.poly1d(np.polyfit(v_wl[peaks], flat_il[peaks], 1))(v_wl) if len(peaks) >= 2 else flat_il
        max_er = max(max_er, np.percentile(final_il, 99) - np.percentile(final_il, 1))
    er_val = max_er if max_er > 0 else np.nan

    vpil_val = np.nan
    z_data = next((b for b in d['bias_data_list'] if b['bias'] == 0.0), None)
    if z_data:
        m0 = (z_data['wl'] >= d['wl_min']) & (z_data['wl'] <= d['wl_max'])
        w0, i0 = z_data['wl'][m0], z_data['il'][m0]
        v0, _ = find_peaks(-(savgol_filter(i0, 31, 3) - poly_func(w0)), prominence=0.3, distance=20)
        if len(v0) >= 2:
            fsr, cwl = np.mean(np.diff(w0[v0])), w0[v0[np.argmin(np.abs(w0[v0] - d['target_wl']))]]
            volts, p_pi = [], []
            for b in d['bias_data_list']:
                if b['bias'] is None: continue
                w, i = b['wl'], b['il']
                mb = (w >= d['wl_min']) & (w <= d['wl_max'])
                wb, ib = w[mb], i[mb]
                mloc = (wb >= cwl - fsr / 2.5) & (wb <= cwl + fsr / 2.5)
                if np.sum(mloc) >= 5:
                    volts.append(b['bias'])
                    p_pi.append(
                        2.0 * (q_sub(wb[mloc], savgol_filter(ib[mloc], 11, 3) - poly_func(wb[mloc])) - cwl) / fsr)
            if len(volts) >= 5:
                vpil_0V = L_length / max(np.abs(np.polyder(np.poly1d(np.polyfit(volts, p_pi, 2)))(0.0)), 1e-5)
                if 0.1 <= vpil_0V <= 10.0: vpil_val = vpil_0V

    summary_list.append({
        'Wafer': wafer, 'Band': band, 'Date': date_str, 'Column': c, 'Row': r, 'Radius': radius,
        'IL_dB': il_val, 'ER_dB': er_val, 'VpiL_Vcm': vpil_val
    })
    count += 1
    if count % 200 == 0: print(f"현재 {count}개 Die 분석 완료...")

# --- 데이터 정리 ---
df = pd.DataFrame(summary_list).groupby(['Wafer', 'Band', 'Date', 'Column', 'Row', 'Radius'], as_index=False).min(
    numeric_only=True)
df['Status'], df['Reason'] = zip(*df.apply(check_status, axis=1))


# 🌟 [핵심] 폴더 및 파일 경로 자동 생성 함수 (Band(LMZC 등) 포함되도록 수정!)
def generate_paths(row):
    wafer = str(row['Wafer'])
    date = str(row['Date'])
    c = int(row['Column'])
    r = int(row['Row'])
    band = str(row['Band'])  # LMZC, LMZO 등 엑셀의 Band 정보 가져오기

    # 기본 폴더 베이스 경로
    base_dir = f"C:\\Users\\sodlg\\PycharmProjects\\PE2\\res\\png\\{wafer}\\{date}"

    # 칩(Die)별 폴더명 예: HY202103_D07_(0,0)_LION1_DCM_LMZC
    folder_name = f"HY202103_{wafer}_({c},{r})_LION1_DCM_{band}"

    # 1. 최종 폴더 경로
    folder_path = f"{base_dir}\\{folder_name}.png"

    # 2. 최종 이미지 파일명 조립 (규칙: Summary_웨이퍼_폴더명.png)
    # 예: Summary_D07_HY202103_D07_(0,0)_LION1_DCM_LMZC.png
    image_name = f"Summary_{wafer}_{folder_name}.png"

    # 최종 이미지 전체 경로 (따옴표 닫기 주의!)
    image_path = f"{folder_path}\\{image_name}.png"

    return pd.Series([folder_path, image_path])


# 경로 생성 적용
df[['Folder_Link', 'Image_Link']] = df.apply(generate_paths, axis=1)

print("--------------------------------------------------")
print("▶ 통합 및 개별 Wafer 파일을 생성합니다...")

total_file_path = os.path.join(save_dir, "Process_result_Total.xlsx")
with pd.ExcelWriter(total_file_path, engine='openpyxl') as writer:
    df.to_excel(writer, index=False, sheet_name='Total_Result')
    apply_excel_style(writer.sheets['Total_Result'], df)
print(f"  - 저장 완료: {total_file_path}")

for wafer_id in df['Wafer'].unique():
    wafer_df = df[df['Wafer'] == wafer_id].copy()
    wafer_file_path = os.path.join(save_dir, f"{wafer_id}_Process_result.xlsx")
    with pd.ExcelWriter(wafer_file_path, engine='openpyxl') as writer:
        wafer_df.to_excel(writer, index=False, sheet_name='Analysis_Result')
        apply_excel_style(writer.sheets['Analysis_Result'], wafer_df)
    print(f"  - 저장 완료: {wafer_file_path}")

print("--------------------------------------------------")
print(f"✅ 저장이 완료되었습니다!")