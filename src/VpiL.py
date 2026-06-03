import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from concurrent.futures import ProcessPoolExecutor
from data_parser import load_parsed
from analysis_utils import q_sub, ref_poly


# ==========================================================
# 2. 개별 Die VpiL 연산 및 플롯 저장
# ==========================================================
def _process_vpil(args):
    d, base_res_dir, L_length = args
    wafer, band, c, r = d['wafer_id'], d['band'], d['die_c'], d['die_r']
    date_str = d.get('date', 'Unknown_Date')

    # Baseline (Ref) Fitting
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(v_ref_wl) < 31: return None
    poly_func = ref_poly(v_ref_wl, v_ref_il, smooth=True)

    # 0V 데이터 확인
    z_data = next((b for b in d['bias_data_list'] if b['bias'] == 0.0), None)
    if not z_data: return None

    m0 = (z_data['wl'] >= d['wl_min']) & (z_data['wl'] <= d['wl_max'])
    w0, i0 = z_data['wl'][m0], z_data['il'][m0]
    flat0 = savgol_filter(i0, 31, 3) - poly_func(w0)
    v0, _ = find_peaks(-flat0, prominence=0.3, distance=20)
    if len(v0) < 2: return None

    fsr = np.mean(np.diff(w0[v0]))
    cwl = w0[v0[np.argmin(np.abs(w0[v0] - d['target_wl']))]]

    volts, p_pi = [], []
    sh = fsr / 2.5
    for b in d['bias_data_list']:
        if b['bias'] is None: continue
        w, i = b['wl'], b['il']
        mb = (w >= d['wl_min']) & (w <= d['wl_max'])
        wb, ib = w[mb], i[mb]

        mloc = (wb >= cwl - sh) & (wb <= cwl + sh)
        if np.sum(mloc) < 5: continue

        flat = savgol_filter(ib[mloc], 11, 3) - poly_func(wb[mloc])
        vwl = q_sub(wb[mloc], flat)
        volts.append(b['bias'])
        p_pi.append(2.0 * (vwl - cwl) / fsr)

    if len(volts) < 5: return None
    volts, p_pi = np.array(volts), np.array(p_pi)

    # 0V 기준 VpiL 추출
    fit = np.poly1d(np.polyfit(volts, p_pi, 2))
    derivative = np.polyder(fit)
    slope_at_0 = np.abs(derivative(0.0))
    slope_at_0 = max(slope_at_0, 1e-5)
    vpil_0V = L_length / slope_at_0

    if not (0.1 <= vpil_0V <= 10.0): return None

    # ------------------- 그래프 그리기 (Standard Style 적용) -------------------
    # [스타일 1] 비율 통일
    plt.figure(figsize=(10, 6))
    vpil_curve = L_length / np.maximum(np.abs(derivative(volts)), 1e-5)

    # 선 굵기 및 마커 크기 키우기
    plt.plot(volts, vpil_curve, 's-', linewidth=2.5, markersize=8, color='gray', label="VpiL Curve")

    # 핵심 데이터인 0V 값 강하게 부각
    plt.plot(0.0, vpil_0V, 'r*', markersize=18, label=f'Value @ 0V = {vpil_0V:.3f}')

    # 0 기준선 굵고 또렷하게
    plt.axhline(vpil_0V, color='red', ls=':', linewidth=2, alpha=0.6)
    plt.axvline(0.0, color='red', ls=':', linewidth=2, alpha=0.6)

    # [스타일 2] 제목, 축 라벨 크기 및 굵기 적용 (형식 통일)
    plt.title(f"Wafer: {wafer} / Coord: ({c}, {r}) / Band: {band}\nVπL at 0V",
              fontsize=18, fontweight='bold', pad=15)
    plt.xlabel("Voltage (V)", fontsize=16, fontweight='bold')
    plt.ylabel("Vpi*L (V*cm)", fontsize=16, fontweight='bold')

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

    # --- 날짜별 폴더 하위에 바로 저장 ---
    # 깊은 하위 폴더(coord_folder) 경로를 제거하고 날짜 폴더까지만 경로로 설정합니다.
    w_dir = os.path.join(base_res_dir, wafer, date_str)
    os.makedirs(w_dir, exist_ok=True)

    # 생성된 파일이 날짜 폴더 안에 바로 저장됩니다.
    plt.savefig(os.path.join(w_dir, f"{wafer}_C{c}_R{r}_{band}_VpiL.png"), bbox_inches='tight')
    plt.close()

    return True


# ==========================================================
# 3. 메인 실행 블록
# ==========================================================
def main():
    zip_path = "../dat/HY202103"
    base_res_dir = "../res/png"
    target_wafers = ['D07', 'D08', 'D23', 'D24']
    L_length = 0.05

    os.makedirs(base_res_dir, exist_ok=True)
    print("🚀 0V 기준 개별 다이 그래프 생성을 시작합니다...")

    parsed_data_list = load_parsed(zip_path, target_wafers)
    tasks = [(d, base_res_dir, L_length) for d in parsed_data_list]
    valid_count = 0

    with ProcessPoolExecutor(max_workers=None) as ex:
        futures = [ex.submit(_process_vpil, t) for t in tasks]
        for f in futures:
            if f.result() is not None:
                valid_count += 1

    print(f"✅ 개별 그래프 저장 완료 (유효 Die: {valid_count}개)")


if __name__ == "__main__":
    main()