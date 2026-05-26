import subprocess
import os
import sys


def main():
    # 현재 run.py 파일이 있는 최상단 디렉토리 경로를 가져옵니다.
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 실제 실행할 파이썬 파일들이 모여있는 'src' 폴더의 경로를 지정합니다.
    src_dir = os.path.join(current_dir, "src")

    # 실행할 스크립트들의 목록입니다.
    scripts_to_run = [
        "data_parser.py",  # 1. 데이터 파싱
        "plot.py",
        "flatting.py",
        "zoom.py",
        "Fitting.py",
        "Phase shift - V.py",
        "VpiL.py",
        "ER_Analysis.py",
        "IL_Analysis.py",
        "VpiL_Analysis.py",
        "combine_plots.py",
        "export_summary.py"
    ]

    print("=== 통합 실행을 시작합니다 ===")

    for script in scripts_to_run:
        script_path = os.path.join(src_dir, script)

        if not os.path.exists(script_path):
            print(f"[경고] {script} 파일을 찾을 수 없습니다. 경로: {script_path}")
            continue

        print(f"\n▶ 실행 중: {script} ...")

        try:
            # 핵심 해결책: cwd=src_dir 를 추가하여
            # 각 스크립트가 src 폴더 안에서 직접 실행되는 것과 똑같은 환경을 만들어 줍니다.
            result = subprocess.run([sys.executable, script_path], check=True, cwd=src_dir)
            print(f"▷ 완료: {script}")

        except subprocess.CalledProcessError as e:
            print(f"\n[오류] {script} 실행 중 에러가 발생했습니다!")
            print(f"에러 코드: {e.returncode}")
            print("=== 전체 실행을 중단합니다 ===")
            break

    else:
        print("\n=== 모든 스크립트 실행이 성공적으로 완료되었습니다! ===")


if __name__ == "__main__":
    main()