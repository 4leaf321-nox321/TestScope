"""주인 없는 첨부 파일을 쓸어낸다.

첨부는 ① 디스크에 쓰고 ② 표에 적는 순서라, ②가 되돌아가면 ①만 남는다 — 아무 줄도 안
가리키는 바이트다(2026-09-24 개발 DB 실측: 18개 중 16개). 순서를 뒤집지 않는 이유와
자세한 판단은 `attachments/services.sweep_filestore` 머리말에 있다.

    python scripts/sweep_filestore.py                    # 세기만 한다
    python scripts/sweep_filestore.py --delete           # 24시간 넘은 것을 지운다
    python scripts/sweep_filestore.py --delete --hours 1 # 급할 때

**기본은 안 지운다.** 지우는 것은 되돌릴 수 없으므로 한 번 보고 나서 하게 한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.all_models  # noqa: F401  (DB 를 만지는 스크립트는 반드시 이것을 읽는다)
from _console import survive_cp949
from app.database import SessionLocal
from app.modules.attachments import services

# 무엇이든 찍기 전에 — `--help` 도 출력이다.
survive_cp949()


def main() -> int:
    parser = argparse.ArgumentParser(description="주인 없는 첨부 파일 정리")
    parser.add_argument("--delete", action="store_true", help="실제로 지운다")
    parser.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="이 시간보다 오래된 것만 본다(갓 올라온 것은 아직 표에 안 적혔을 수 있다)",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        report = services.sweep_filestore(db, older_than_hours=args.hours, delete=args.delete)

    megabytes = report["bytes"] / 1024 / 1024
    did = "지웠다" if report["deleted"] else "지울 수 있다"
    print(f"주인 없는 파일 {report['orphans']}개 ({megabytes:.1f} MB) — {did}")
    if report["skipped_recent"]:
        print(
            f"  최근 {args.hours}시간 안의 파일 {report['skipped_recent']}개는 건드리지 않았다"
        )
    if not report["deleted"] and report["orphans"]:
        print("  실제로 지우려면 --delete 를 붙인다")
    if report["missing_files"]:
        # **이쪽이 진짜 고장이다.** 가리키는 줄이 있는데 파일이 없다 — 되살릴 수 없다.
        print(f"\n표에는 있는데 파일이 없는 것 {len(report['missing_files'])}개:")
        for digest in report["missing_files"][:10]:
            print(f"  {digest}")
        print("  백업 복구가 DB 만 된 것일 수 있다 — 파일스토어 백업을 확인하라")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
