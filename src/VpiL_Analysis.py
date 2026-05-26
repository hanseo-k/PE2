import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from concurrent.futures import ProcessPoolExecutor
from data_parser import parse_wafer_data


# ==========================================================
# 1. 전역 보조 함수
# ==========================================================
def q_sub(x, y):
    if len(x) < 3: return x[np.argmin(y)]
    idx = np.argmin(y)
    if idx == 0 or idx == len(x) - 1: return x[idx]
    c = np.polyfit(x[idx - 1:idx + 2], y[idx - 1:idx + 2], 2)
    return -c[1] / (2 * c[0]) if abs(c[0]) > 1e-12 else x[idx]


# ==========================================================
# 2. 고속 데이터 연산 함수 (그래프 생성 안 함)
# ==========================================================
def _extract_vpil_data(args):
    d, L_length = args
    wafer, band, c, r = d['wafer_id'], d['band'], d['die_c'], d['die_r']
    radius = np.sqrt(c ** 2 + r ** 2)
    date_str = d.get('date', 'Unknown_Date')  # 날짜 정보 추가 추출

    # Baseline (Ref) Fitting
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(v_ref_wl) < 31: return None
    poly_func = np.poly1d(np.polyfit(v_ref_wl, savgol_filter(v_ref_il, 31, 3), 3))

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

    fit = np.poly1d(np.polyfit(volts, p_pi, 2))
    slope_at_0 = max(np.abs(np.polyder(fit)(0.0)), 1e-5)
    vpil_0V = L_length / slope_at_0

    if not (0.1 <= vpil_0V <= 10.0): return None

    # 데이터만 빠르게 반환 (Date 포함)
    return {
        'Wafer': wafer, 'Band': band, 'Date': date_str, 'Column': c, 'Row': r,
        'Radius': radius, 'VpiL_0V': vpil_0V
    }


# ==========================================================
# 3. 메인 실행 블록 (분석 및 통합 시각화)
# ==========================================================
def main():
    zip_path = "../dat/HY202103"
    base_res_dir = "../res/png"
    target_wafers = ['D07', 'D08', 'D23', 'D24']
    L_length = 0.05
    TARGET_VPIL = {'LMZO': 1.4, 'LMZC': 2.0}

    global_analysis_dir = os.path.join(base_res_dir, "Analysis")
    os.makedirs(global_analysis_dir, exist_ok=True)

    print("🚀 날짜별 분석용 데이터 추출을 시작합니다...")

    parsed_data_list = list(parse_wafer_data(zip_path, target_wafers))
    tasks = [(d, L_length) for d in parsed_data_list]
    summary_rows = []

    with ProcessPoolExecutor(max_workers=None) as ex:
        futures = [ex.submit(_extract_vpil_data, t) for t in tasks]
        for f in futures:
            res = f.result()
            if res is not None:
                summary_rows.append(res)

    if not summary_rows:
        print("❌ 유효한 데이터를 찾지 못했습니다.")
        return

    # 데이터 필터링 (Date 포함해서 그룹화)
    df = pd.DataFrame(summary_rows)
    filtered_df = pd.DataFrame()
    df_grouped = df.groupby(['Wafer', 'Band', 'Date', 'Column', 'Row', 'Radius'], as_index=False)['VpiL_0V'].mean()

    for (wafer, band, date), group in df_grouped.groupby(['Wafer', 'Band', 'Date']):
        if len(group) > 5:
            m, s = group['VpiL_0V'].mean(), group['VpiL_0V'].std()
            valid_group = group[(group['VpiL_0V'] >= m - 3 * s) & (group['VpiL_0V'] <= m + 3 * s)]
            filtered_df = pd.concat([filtered_df, valid_group])
        else:
            filtered_df = pd.concat([filtered_df, group])

    max_r = filtered_df['Radius'].max()
    edge_limit = max_r * 0.75
    filtered_df['Region'] = np.where(filtered_df['Radius'] > edge_limit, 'Edge', 'Center')

    print(f"✅ 데이터 추출 및 필터링 완료! (총 {len(filtered_df)}개 다이 분석)")

    # ----------------------------------------------------------
    # 통합 Wafer Map 시각화 (날짜별)
    # ----------------------------------------------------------
    print("▶ 날짜별 Wafer Map 생성 중...")
    band_limits = {}
    for b in filtered_df['Band'].unique():
        b_data = filtered_df[filtered_df['Band'] == b]['VpiL_0V']
        band_limits[b] = {'min': b_data.min() - 0.05, 'max': b_data.max() + 0.05}

    # Wafer, Band, Date 3가지 조건으로 쪼개서 맵 생성
    for (wafer, band, date), group in filtered_df.groupby(['Wafer', 'Band', 'Date']):
        plt.figure(figsize=(9, 9))
        theta = np.linspace(0, 2 * np.pi, 100)
        plt.plot((max_r + 0.5) * np.cos(theta), (max_r + 0.5) * np.sin(theta), color='gray', lw=2)
        plt.plot(edge_limit * np.cos(theta), edge_limit * np.sin(theta), 'r--', lw=2, alpha=0.6, label='Boundary')

        v_min, v_max = band_limits[band]['min'], band_limits[band]['max']
        scatter = plt.scatter(group['Column'], group['Row'], c=group['VpiL_0V'], cmap='coolwarm',
                              vmin=v_min, vmax=v_max, s=600, edgecolor='black', alpha=0.9, zorder=5)

        for _, row in group.iterrows():
            plt.text(row['Column'], row['Row'], f"{row['VpiL_0V']:.2f}",
                     ha='center', va='center', fontsize=10, weight='bold', color='black', zorder=10)

        cbar = plt.colorbar(scatter, shrink=0.8)
        cbar.set_label('Vpi*L @ 0V [V*cm]', fontsize=14, fontweight='bold')

        # 타이틀과 파일명에 Date 추가
        plt.title(f"Wafer Map: {wafer} / {band}\nDate: {date} | VpiL at 0V", fontsize=18, fontweight='bold', pad=15)
        plt.xlabel("Die Column (X)", fontsize=16, fontweight='bold')
        plt.ylabel("Die Row (Y)", fontsize=16, fontweight='bold')
        plt.gca().set_aspect('equal')
        plt.grid(True, alpha=0.3, linestyle=':')

        plt.savefig(os.path.join(global_analysis_dir, f"Map_{wafer}_{band}_{date}_VpiL_0V.png"), bbox_inches='tight')
        plt.close()

    # ----------------------------------------------------------
    # Advanced Box Plot (날짜별)
    # ----------------------------------------------------------
    print("▶ 날짜별 Box Plot 생성 중...")
    flierprops = dict(marker='d', markerfacecolor='black', markersize=6, alpha=0.6)

    # Band와 Date 조건으로 쪼개서 박스플롯 생성 (가로축은 여전히 Wafer들)
    for (band, date), band_date_df in filtered_df.groupby(['Band', 'Date']):
        wafer_list = sorted(band_date_df['Wafer'].unique())
        current_target = TARGET_VPIL.get(band, 1.5)

        plt.figure(figsize=(14, 8))
        positions, plot_data, labels, colors = [], [], [], []

        for i, wafer in enumerate(wafer_list):
            w_df = band_date_df[band_date_df['Wafer'] == wafer]
            c_data = w_df[w_df['Region'] == 'Center']['VpiL_0V'].values
            e_data = w_df[w_df['Region'] == 'Edge']['VpiL_0V'].values

            if len(c_data) > 0:
                plot_data.append(c_data)
                positions.append(i * 3 + 1)
                labels.append(f"{wafer}\n(Center)\nn={len(c_data)}")
                colors.append('#3498db')
            if len(e_data) > 0:
                plot_data.append(e_data)
                positions.append(i * 3 + 2)
                labels.append(f"{wafer}\n(Edge)\nn={len(e_data)}")
                colors.append('#e74c3c')

        if not plot_data: continue

        box_reg = plt.boxplot(plot_data, positions=positions, tick_labels=labels, patch_artist=True,
                              flierprops=flierprops)
        for patch, color in zip(box_reg['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)

        for pos, data in zip(positions, plot_data):
            x_jitter = np.random.normal(pos, 0.05, size=len(data))
            plt.scatter(x_jitter, data, color='black', alpha=0.5, s=20, zorder=3)

        plt.axhline(current_target, color='red', ls='-', linewidth=2.5, label=f'Target ({current_target} V*cm)')

        # 타이틀과 파일명에 Date 추가
        plt.title(f"Advanced Box Plot (Center vs Edge): {band} @ 0V\nDate: {date}", fontsize=18, fontweight='bold',
                  pad=15)
        plt.ylabel("Vpi*L @ 0V [V*cm]", fontsize=16, fontweight='bold')
        plt.legend(loc='upper right', prop={'size': 13, 'weight': 'bold'})
        plt.grid(True, axis='y', alpha=0.5, linestyle=':')
        plt.xlim(0, max(positions) + 1)
        plt.tight_layout()

        plt.savefig(os.path.join(global_analysis_dir, f"Box_{band}_{date}_VpiL_0V.png"), bbox_inches='tight')
        plt.close()

    print("✅ 날짜별 통합 플롯 저장이 완료되었습니다!")


if __name__ == "__main__":
    main()