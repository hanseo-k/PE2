import os
import math
from PIL import Image


def get_sort_index(filename):
    """
    다이(Die) 분석 이미지의 정렬 순서를 결정합니다.
    1.Plot(Raw) -> 2.Flatting -> 3.Fitting -> 4.Zoom -> 5.Phase shift -> 6.VpiL
    """
    name = filename.lower()
    if 'raw' in name or 'plot' in name:
        return 1
    elif 'flatting' in name or 'flat' in name:
        return 2
    elif 'zoom' in name:
        return 3
    elif 'fitting' in name or 'fit' in name:
        return 4
    elif 'phase' in name:
        return 5
    elif 'vpil' in name:
        return 6
    else:
        return 99


def get_map_sort_index(filename):
    """
    웨이퍼 맵 이미지의 정렬 순서를 결정합니다.
    요청하신 순서: 1.ER(소광비) -> 2.IL(손실) -> 3.VpiL(효율) 순서로 배치합니다.
    """
    name = filename.upper()
    if 'ER' in name:
        return 1
    elif 'IL' in name and 'VPIL' not in name:
        return 2
    elif 'VPIL' in name:
        return 3
    else:
        return 99


def merge_die_images(base_dir, delete_originals=True):
    """
    각 날짜 폴더 내의 분석 이미지들을 좌표(Die) 및 밴드(Band)별로 그룹화하여
    가로 3, 세로 2 격자 형태로 병합하고 원본을 삭제합니다.
    """
    print("▶ 1. 날짜 폴더 내 분석 이미지 병합 및 원본 파일 관리를 시작합니다...")
    combine_count = 0
    deleted_count = 0

    for wafer in os.listdir(base_dir):
        wafer_path = os.path.join(base_dir, wafer)
        if not os.path.isdir(wafer_path) or wafer == "Analysis":
            continue

        for date_folder in os.listdir(wafer_path):
            date_path = os.path.join(wafer_path, date_folder)
            if not os.path.isdir(date_path):
                continue

            # 1) 기존에 생성된 병합 파일이 있다면 중복 방지를 위해 삭제
            # 이전처럼 Summary_가 아니라 특정 포맷(HY202103_...)을 삭제 대상으로 추적
            for f in os.listdir(date_path):
                if f.startswith('HY202103_') and 'LION1_DCM' in f and f.endswith('.png'):
                    try:
                        os.remove(os.path.join(date_path, f))
                    except:
                        pass

            # 2) 날짜 폴더에 바로 있는 모든 .png 이미지 추출 (맵 제외, 기존 병합본 제외)
            image_files = [f for f in os.listdir(date_path) if f.endswith('.png')
                           and not f.startswith('Map_')
                           and not f.startswith('HY202103_')]

            if not image_files:
                continue

            # 3) 동일한 좌표(Die)와 밴드(Band)를 가진 파일끼리 그룹화
            die_groups = {}
            for f in image_files:
                parts = f.replace(".png", "").split('_')
                # 파일명 예: D07_C0_R2_LMZC_Raw
                if len(parts) >= 4:
                    try:
                        # C0 -> 0, R2 -> 2 형태로 숫자 추출
                        c_val = parts[1].replace('C', '')
                        r_val = parts[2].replace('R', '')
                        band = parts[3]
                        group_key = (c_val, r_val, band)

                        if group_key not in die_groups:
                            die_groups[group_key] = []
                        die_groups[group_key].append(f)
                    except Exception as e:
                        print(f"파일 이름 분석 오류: {f} -> {e}")

            # 4) 그룹별(각 Die 좌표 및 Band)로 병합 프로세스 진행
            for (c_val, r_val, band), files in die_groups.items():
                if not files:
                    continue

                # 정렬 규칙 적용 (Raw -> Flatting -> Fitting ...)
                files.sort(key=get_sort_index)

                images = []
                valid_files = []
                for img_name in files:
                    try:
                        img_path = os.path.join(date_path, img_name)
                        img = Image.open(img_path)
                        img.load()
                        images.append(img)
                        valid_files.append(img_path)
                    except:
                        pass
                if not images:
                    continue

                # 가로 3열 격자 설정
                cols = 3
                rows = math.ceil(len(images) / cols)
                max_width = max(img.size[0] for img in images)
                max_height = max(img.size[1] for img in images)

                grid_width = cols * max_width
                grid_height = rows * max_height
                new_im = Image.new('RGB', (grid_width, grid_height), color='white')

                for i, img in enumerate(images):
                    x_offset = (i % cols) * max_width
                    y_offset = (i // cols) * max_height
                    new_im.paste(img, (x_offset, y_offset))
                    img.close()

                # ★ 저장 파일명 변경 완료 (요청하신 포맷 적용)
                save_filename = f"HY202103_{wafer}_({c_val},{r_val})_LION1_DCM_{band}.png"
                new_im.save(os.path.join(date_path, save_filename))
                combine_count += 1

                # 5) 원본 파일 제거
                if delete_originals:
                    for orig_path in valid_files:
                        try:
                            os.remove(orig_path)
                            deleted_count += 1
                        except Exception as e:
                            print(f"  [경고] 원본 파일 삭제 실패 ({os.path.basename(orig_path)}): {e}")

    print(f"  ✅ 총 {combine_count}개의 다이(Die) 요약 이미지 병합 완료!")
    if delete_originals:
        print(f"  🧹 병합에 사용된 원본 이미지 총 {deleted_count}개 삭제 완료.\n")


def merge_wafer_maps(base_dir, delete_originals=True):
    """Analysis 폴더 내의 웨이퍼 맵 3종을 1개의 이미지로 가로 병합하고 원본을 삭제합니다."""
    analysis_dir = os.path.join(base_dir, "Analysis")
    if not os.path.exists(analysis_dir):
        print(f"  [안내] Analysis 폴더가 없어 웨이퍼 맵 병합을 건너뜁니다.")
        return

    print("▶ 2. 웨이퍼별 통합 맵(IL, ER, VpiL) 병합 및 원본 파일 관리를 시작합니다...")
    map_combine_count = 0
    deleted_count = 0

    for wafer in os.listdir(analysis_dir):
        w_path = os.path.join(analysis_dir, wafer)
        if not os.path.isdir(w_path) or wafer == "Overall_BoxPlots":
            continue

        for date_folder in os.listdir(w_path):
            d_path = os.path.join(w_path, date_folder)
            if not os.path.isdir(d_path):
                continue

            band_images = {}
            for f in os.listdir(d_path):
                if f.startswith('Summary_WaferMap'):
                    try:
                        os.remove(os.path.join(d_path, f))
                    except:
                        pass
                    continue

                if f.startswith('Map_') and f.endswith('.png'):
                    parts = f.replace(f"Map_{wafer}_", "").split("_")
                    band = parts[0]
                    if band not in band_images:
                        band_images[band] = []
                    band_images[band].append(f)

            for band, files in band_images.items():
                if len(files) < 2:
                    continue

                files.sort(key=get_map_sort_index)

                images = []
                valid_files = []
                for f in files:
                    try:
                        img_path = os.path.join(d_path, f)
                        img = Image.open(img_path)
                        img.load()
                        images.append(img)
                        valid_files.append(img_path)
                    except:
                        pass

                if not images:
                    continue

                cols = len(images)
                max_width = max(img.size[0] for img in images)
                max_height = max(img.size[1] for img in images)

                new_im = Image.new('RGB', (max_width * cols, max_height), color='white')
                for i, img in enumerate(images):
                    new_im.paste(img, (i * max_width, 0))
                    img.close()

                save_filename = f"Summary_WaferMap_{wafer}_{band}_{date_folder}.png"
                new_im.save(os.path.join(d_path, save_filename))
                map_combine_count += 1

                if delete_originals:
                    for orig_path in valid_files:
                        try:
                            os.remove(orig_path)
                            deleted_count += 1
                        except Exception as e:
                            print(f"  [경고] 웨이퍼 맵 원본 삭제 실패 ({os.path.basename(orig_path)}): {e}")

    print(f"  ✅ 총 {map_combine_count}장의 통합 웨이퍼 맵(Dashboard) 생성 완료!")
    if delete_originals:
        print(f"  🧹 병합에 사용된 웨이퍼 맵 원본 이미지 총 {deleted_count}개 삭제 완료.\n")


def main():
    base_dir = "../res/png"
    base_dir = os.path.abspath(base_dir)

    if not os.path.exists(base_dir):
        print(f"❌ [오류] {base_dir} 경로를 찾을 수 없습니다.")
        return

    # 🌟 원본 파일을 실제로 삭제하려면 True, 원본을 유지하고 싶다면 False로 설정하세요.
    DELETE_ORIGINAL_FILES = True

    # 1. Die 이미지 병합 실행
    merge_die_images(base_dir, delete_originals=DELETE_ORIGINAL_FILES)

    # 2. Wafer Map 이미지 병합 실행
    merge_wafer_maps(base_dir, delete_originals=DELETE_ORIGINAL_FILES)

    print("\n🎉 모든 이미지 병합 및 원본 파일 정리 작업이 성공적으로 마무리되었습니다!")


if __name__ == "__main__":
    main()