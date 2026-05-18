import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from data_parser import parse_wafer_data

zip_path = "../dat/HY202103.zip"
# 1. Base 폴더를 res로 통일
base_res_dir = "../res"
target_wafers = ['D07', 'D08', 'D23', 'D24']
IL_TARGETS = {'LMZO': -8.75, 'LMZC': -8.75}

# --- [통합 설정] 모든 분석 결과가 모일 res/Analysis 폴더 생성 ---
global_analysis_dir = os.path.join(base_res_dir, "Analysis")
os.makedirs(global_analysis_dir, exist_ok=True)

il_data_list = []
for d in parse_wafer_data(zip_path, target_wafers):
    max_peak = -999.0
    for b in d['bias_data_list']:
        if b['bias'] is None: continue
        m = (b['wl'] >= d['wl_min']) & (b['wl'] <= d['wl_max'])
        if np.any(m): max_peak = max(max_peak, np.max(b['il'][m]))

    if max_peak != -999.0:
        il_data_list.append(
            {'Wafer': d['wafer_id'], 'Band': d['band'], 'Column': d['die_c'], 'Row': d['die_r'], 'IL': max_peak})

df = pd.DataFrame(il_data_list).groupby(['Wafer', 'Band', 'Column', 'Row'], as_index=False)['IL'].mean()
df['Radius'] = np.sqrt(df['Column'] ** 2 + df['Row'] ** 2)

filtered_df = pd.DataFrame()
for _, group in df.groupby(['Wafer', 'Band']):
    m, s = group['IL'].mean(), group['IL'].std()
    filtered_df = pd.concat([filtered_df, group[(group['IL'] >= m - 3 * s) & (group['IL'] <= m + 3 * s)]])

max_rad = filtered_df['Radius'].max()
filtered_df['Region'] = np.where(filtered_df['Radius'] > max_rad * 0.75, 'Edge', 'Center')

# ==========================================================
# 2. Wafer Map 그리기 (통합 Analysis 폴더에 저장)
# ==========================================================
for b in filtered_df['Band'].unique():
    limits = {'min': np.floor(filtered_df[filtered_df['Band'] == b]['IL'].min()),
              'max': np.ceil(filtered_df[filtered_df['Band'] == b]['IL'].max())}
    for w in filtered_df['Wafer'].unique():
        grp = filtered_df[(filtered_df['Wafer'] == w) & (filtered_df['Band'] == b)]
        if grp.empty: continue

        plt.figure(figsize=(9, 9))
        th = np.linspace(0, 2 * np.pi, 100)
        plt.plot((max_rad + 0.5) * np.cos(th), (max_rad + 0.5) * np.sin(th), color='gray', lw=2)
        plt.plot(max_rad * 0.75 * np.cos(th), max_rad * 0.75 * np.sin(th), color='red', ls='--', lw=2, alpha=0.6)

        sc = plt.scatter(grp['Column'], grp['Row'], c=grp['IL'], cmap='coolwarm_r', vmin=limits['min'],
                         vmax=limits['max'], s=500, edgecolor='black')
        for _, r in grp.iterrows(): plt.text(r['Column'], r['Row'], f"{r['IL']:.1f}", ha='center', va='center',
                                             fontweight='bold')
        cb = plt.colorbar(sc, shrink=0.8)
        cb.set_label('IL [dB]', fontsize=14, fontweight='bold')

        plt.title(f"Wafer Map: {w} / {b} (IL)", fontsize=18, fontweight='bold')
        plt.gca().set_aspect('equal')

        # --- 지정해 둔 통합 폴더로 저장 (Map_...) ---
        plt.savefig(os.path.join(global_analysis_dir, f"Map_{w}_{b}_IL.png"), bbox_inches='tight')
        plt.close()

# ==========================================================
# 3. Box Plot 그리기 (통합 Analysis 폴더에 저장)
# ==========================================================
for b in ['LMZO', 'LMZC']:
    b_df = filtered_df[filtered_df['Band'] == b]
    if b_df.empty: continue

    plt.figure(figsize=(14, 8))
    pos, data, lbl, clr = [], [], [], []
    for i, w in enumerate(sorted(b_df['Wafer'].unique())):
        w_df = b_df[b_df['Wafer'] == w]
        c, e = w_df[w_df['Region'] == 'Center']['IL'].values, w_df[w_df['Region'] == 'Edge']['IL'].values
        if len(c) > 0: pos.append(i * 3 + 1); data.append(c); lbl.append(f"{w}\n(C)"); clr.append('#3498db')
        if len(e) > 0: pos.append(i * 3 + 2); data.append(e); lbl.append(f"{w}\n(E)"); clr.append('#e74c3c')

    box = plt.boxplot(data, positions=pos, patch_artist=True,
                      flierprops=dict(marker='d', markerfacecolor='black', alpha=0.6))
    for p, c_hex in zip(box['boxes'], clr): p.set_facecolor(c_hex); p.set_alpha(0.6)

    avg_il, tgt_il = b_df['IL'].mean(), IL_TARGETS[b]
    plt.axhline(avg_il, color='blue', ls='--', lw=2.5, label=f'Avg: {avg_il:.2f} dB')
    plt.axhline(tgt_il, color='red', ls='-', lw=2.5, label=f'Target: {tgt_il:.2f} dB')
    plt.xticks(pos, lbl, fontweight='bold')
    plt.title(f"IL Analysis ({b})", fontweight='bold', fontsize=18)
    plt.legend(loc='upper right')
    plt.tight_layout()

    # --- 지정해 둔 통합 폴더로 저장 (Box_...) ---
    plt.savefig(os.path.join(global_analysis_dir, f"Box_{b}_IL.png"), bbox_inches='tight')
    plt.close()

print("✅ 모든 IL 분석 결과(Wafer Map, Box Plot)가 'res/Analysis' 폴더에 통합 저장되었습니다!")