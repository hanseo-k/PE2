import os
import math
import shutil
from PIL import Image


def get_sort_index(filename):
    """
    파일 이름에 포함된 키워드를 바탕으로 정렬 순서를 결정합니다.
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


def main():
    print("▶ 개별 좌표(Die) 폴더 내의 분석 이미지 지정 순서 병합을 시작합니다...")

    base_dir = "../res/png"
    # 절대 경로로 변환하여 파일 경로 꼬임 방지
    base_dir = os.path.abspath(base_dir)

    if not os.path.exists(base_dir):
        print(f"[오류] {base_dir} 폴더를 찾을 수 없습니다.")
        return

    combine_count = 0

    for wafer in os.listdir(base_dir):
        wafer_path = os.path.join(base_dir, wafer)
        if not os.path.isdir(wafer_path) or wafer == "Analysis":
            continue

        for date_folder in os.listdir(wafer_path):
            date_path = os.path.join(wafer_path, date_folder)
            if not os.path.isdir(date_path):
                continue

            for coord_folder in os.listdir(date_path):
                coord_path = os.path.join(date_path, coord_folder)
                if not os.path.isdir(coord_path):
                    continue

                # --- 1. 기존에 생성된 Summary 파일이 있다면 안전하게 삭제 ---
                # (중복 병합이나 파일 잠김 방지)
                for f in os.listdir(coord_path):
                    if f.startswith('Summary_') and f.endswith('.png'):
                        try:
                            os.remove(os.path.join(coord_path, f))
                        except Exception as e:
                            print(f"[경고] 기존 Summary 파일 삭제 실패: {e}")

                # --- 2. 병합할 이미지 파일 목록 추출 ---
                image_files = [f for f in os.listdir(coord_path) if f.endswith('.png')]

                # 합칠 이미지가 없으면 패스
                if not image_files:
                    continue

                # --- 3. 정렬 수행 ---
                image_files.sort(key=get_sort_index)

                # --- 4. 이미지 파일 열기 ---
                images = []
                for img_name in image_files:
                    img_path = os.path.join(coord_path, img_name)
                    if os.path.exists(img_path):  # 파일 존재 여부 한 번 더 체크
                        try:
                            images.append(Image.open(img_path))
                        except Exception as e:
                            print(f"[경고] {img_name} 이미지를 열 수 없습니다: {e}")
                    else:
                        print(f"[경고] 파일 경로를 찾을 수 없습니다: {img_path}")

                if not images:
                    continue

                # --- 5. 병합 (격자 생성) ---
                cols = 2
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

                # --- 6. 저장 ---
                save_filename = f"Summary_{wafer}_{coord_folder}.png"
                save_path = os.path.join(coord_path, save_filename)

                try:
                    new_im.save(save_path)
                    combine_count += 1
                except Exception as e:
                    print(f"[오류] Summary 이미지 저장 실패 ({save_path}): {e}")

    print(f"✅ 총 {combine_count}개의 다이(Die) 좌표에서 정렬된 요약 이미지 병합 완료!")


if __name__ == "__main__":
    main()