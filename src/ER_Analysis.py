import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from data_parser import parse_wafer_data

zip_path = "../dat/HY202103.zip"
# 1. Base 폴더를 res로 통일
base_res_dir = "../res"
target_wafers = ['D07', 'D08', 'D23', 'D24']

print("🚀 평탄화 로직 기반 ER 추출 및 Center vs Edge 분석을 시작합니다...")

er_data_list = []
count = 0

for d in parse_wafer_data(zip_path, target_wafers):
    m = (d['ref_data']['wl'] >= d['wl_min']) & (d['ref_data']['wl'] <= d['wl_max'])
    v_ref_wl, v_ref_il = d['ref_data']['wl'][m], d['ref_data']['il'][m]
    if len(v_ref_wl) < 4: continue

    poly_func = np.poly1d(np.polyfit(v_ref_wl, v_ref_il, 3))
    max_er = 0.0

    for b in d['bias_data_list']:
        m_b = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        v_wl, v_il = b['wl'][m_b], b['il'][m_b]
        if len(v_wl) == 0: continue

        flat_il = v_il - poly_func(v_wl)
        peaks, _ = find_peaks(flat_il, prominence=3.0, distance=30)

        if len(peaks) >= 2:
            trend = np.poly1d(np.polyfit(v_wl[peaks], flat_il[peaks], 1))
            final_il = flat_il - trend(v_wl)
        else:
            final_il = flat_il

        er = np.percentile(final_il, 99) - np.percentile(final_il, 1)
        max_er = max(max_er, er)

    er_data_list.append({
        'Wafer': d['wafer_id'], 'Band': d['band'], 'Column': d['die_c'], 'Row': d['die_r'],
        'Radius': np.sqrt(d['die_c'] ** 2 + d['die_r'] ** 2), 'ER': max_er
    })

    count += 1
    if count % 100 == 0: print(f"현재 {count}개 Die 파싱 및 평탄화 ER 추출 완료...")

df = pd.DataFrame(er_data_list)
filtered_df = pd.DataFrame()

for (wafer, band), group in df.groupby(['Wafer', 'Band']):
    if len(group) > 5:
        m_val, s_val = group['ER'].mean(), group['ER'].std()
        filtered_df = pd.concat(
            [filtered_df, group[(group['ER'] >= m_val - 3 * s_val) & (group['ER'] <= m_val + 3 * s_val)]])
    else:
        filtered_df = pd.concat([filtered_df, group])

max_rad = filtered_df['Radius'].max()
edge_thresh = max_rad * 0.75
filtered_df['Region'] = np.where(filtered_df['Radius'] > edge_thresh, 'Edge', 'Center')

# ==========================================================
# 2. Wafer Map 그리기 (각 웨이퍼의 Analysis 폴더에 저장)
# ==========================================================
for b in filtered_df['Band'].unique():
    band_limits = {'min': np.floor(filtered_df[filtered_df['Band'] == b]['ER'].min()),
                   'max': np.ceil(filtered_df[filtered_df['Band'] == b]['ER'].max())}

    for w in filtered_df['Wafer'].unique():
        group = filtered_df[(filtered_df['Wafer'] == w) & (filtered_df['Band'] == b)]
        if group.empty: continue

        plt.figure(figsize=(9, 9))
        theta = np.linspace(0, 2 * np.pi, 100)
        plt.plot((max_rad + 0.5) * np.cos(theta), (max_rad + 0.5) * np.sin(theta), color='gray', lw=2)
        plt.plot(edge_thresh * np.cos(theta), edge_thresh * np.sin(theta), color='red', ls='--', lw=2, alpha=0.6)

        sc = plt.scatter(group['Column'], group['Row'], c=group['ER'], cmap='coolwarm_r',
                         vmin=band_limits['min'], vmax=band_limits['max'], s=500, edgecolor='black', alpha=0.9,
                         zorder=5)
        for _, row in group.iterrows():
            plt.text(row['Column'], row['Row'], f"{row['ER']:.1f}", ha='center', va='center', fontsize=10,
                     color='black', fontweight='bold', zorder=10)

        cb = plt.colorbar(sc, shrink=0.8)
        cb.set_label('Extinction Ratio [dB]', fontsize=14, fontweight='bold')
        cb.ax.tick_params(labelsize=12)
        for l in cb.ax.yaxis.get_ticklabels(): l.set_weight("bold")

        plt.title(f"Wafer Map: {w} / {b} (Flattened ER)", fontsize=18, fontweight='bold', pad=15)
        plt.xlabel('Die Column', fontsize=16, fontweight='bold')
        plt.ylabel('Die Row', fontsize=16, fontweight='bold')
        plt.grid(True, ls=':', alpha=0.5)
        plt.gca().set_aspect('equal')
        global_analysis_dir = os.path.join(base_res_dir, "Analysis")
        os.makedirs(global_analysis_dir, exist_ok=True)
        plt.savefig(os.path.join(global_analysis_dir, f"Map_{w}_{b}_ER.png"), bbox_inches='tight')
        plt.close()

# ==========================================================
# 3. Box Plot 그리기 (최상위 Analysis 폴더에 저장)
# ==========================================================
global_analysis_dir = os.path.join(base_res_dir, "Analysis")
os.makedirs(global_analysis_dir, exist_ok=True)

for band in ['LMZO', 'LMZC']:
    b_df = filtered_df[filtered_df['Band'] == band]
    if b_df.empty: continue

    avg_er = b_df['ER'].mean()
    plt.figure(figsize=(14, 8))
    pos, data, labels, colors = [], [], [], []

    for i, w in enumerate(sorted(b_df['Wafer'].unique())):
        w_df = b_df[b_df['Wafer'] == w]
        c, e = w_df[w_df['Region'] == 'Center']['ER'].values, w_df[w_df['Region'] == 'Edge']['ER'].values
        if len(c) > 0: pos.append(i * 3 + 1); data.append(c); labels.append(f"{w}\n(C)\nn={len(c)}"); colors.append(
            '#3498db')
        if len(e) > 0: pos.append(i * 3 + 2); data.append(e); labels.append(f"{w}\n(E)\nn={len(e)}"); colors.append(
            '#e74c3c')

    box = plt.boxplot(data, positions=pos, patch_artist=True,
                      flierprops=dict(marker='d', markerfacecolor='black', alpha=0.6))
    for p, c in zip(box['boxes'], colors): p.set_facecolor(c); p.set_alpha(0.6)
    for p, d_arr in zip(pos, data): plt.scatter(np.random.normal(p, 0.05, len(d_arr)), d_arr, color='black', alpha=0.5,
                                                s=20, zorder=3)

    plt.axhline(avg_er, color='blue', ls='--', lw=2.5, label=f'Avg: {avg_er:.2f} dB')
    plt.axhline(20.0, color='red', ls='-', lw=2.5, label='Theoretical: 20 dB')

    plt.title(f"Extinction Ratio: Center vs Edge ({band})", fontsize=18, fontweight='bold', pad=15)
    plt.xticks(pos, labels, fontsize=13, fontweight='bold')
    plt.yticks(fontsize=14, fontweight='bold')
    plt.legend(loc='upper right', prop={'size': 13, 'weight': 'bold'})
    plt.grid(True, axis='y', ls=':', alpha=0.6)
    plt.tight_layout()

    # --- 박스 플롯 저장 경로 (res/Analysis) ---
    plt.savefig(os.path.join(global_analysis_dir, f"BoxPlot_{band}_ER_Flattened.png"), bbox_inches='tight')
    plt.close()

print("✅ ER 분석 및 저장 완료")