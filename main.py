#!/usr/bin/env python3
"""Publisher settlement automation script.

Usage:
    python main.py --publisher 개념원리 --month 3 --year 2026
    python main.py -p 개념원리 -m 3          # year defaults to current year
"""

import argparse
import calendar
from datetime import datetime

from auth import get_credentials, get_sheets_service
from bookips import update_pivot_parameters, refresh_data_connectors, get_publisher_data
from mg_summary import create_new_month_tab


def parse_args():
    parser = argparse.ArgumentParser(
        description="출판사 정산 자동화 - Publisher Settlement Automation"
    )
    parser.add_argument(
        "-p", "--publisher",
        required=True,
        help="정산할 출판사 이름 (e.g., 개념원리)",
    )
    parser.add_argument(
        "-m", "--month",
        type=int,
        required=True,
        choices=range(1, 13),
        help="정산 월 (1-12)",
    )
    parser.add_argument(
        "-y", "--year",
        type=int,
        default=datetime.now().year,
        help="정산 연도 (default: current year)",
    )
    parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="BigQuery 데이터 커넥터 새로고침 건너뛰기",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 데이터 쓰기 없이 읽기만 수행",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    publisher = args.publisher
    month = args.month
    year = args.year

    # Calculate date range
    _, last_day = calendar.monthrange(year, month)
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day:02d}"

    print(f"{'=' * 60}")
    print(f"출판사 정산 자동화")
    print(f"{'=' * 60}")
    print(f"  출판사: {publisher}")
    print(f"  기간: {start_date} ~ {end_date}")
    print(f"{'=' * 60}")

    # Step 1: Authenticate
    print("\n[1/4] Google 인증 중...")
    creds = get_credentials()
    sheets_service = get_sheets_service(creds)
    print("  인증 완료!")

    # Step 2: Update Pivot parameters
    print("\n[2/4] Bookips Pivot 탭 업데이트 중...")
    update_pivot_parameters(sheets_service, year, start_date, end_date)

    # Step 3: Refresh data connectors
    if not args.skip_refresh:
        print("\n[3/4] BigQuery 데이터 커넥터 새로고침 중...")
        refresh_data_connectors(sheets_service)
    else:
        print("\n[3/4] BigQuery 새로고침 건너뜀 (--skip-refresh)")

    # Step 4: Get publisher data
    print(f"\n[4/4] '{publisher}' 데이터 추출 중...")
    headers, data_rows = get_publisher_data(sheets_service, publisher)

    if not data_rows:
        print(f"\n  '{publisher}'에 해당하는 데이터가 없습니다. 종료합니다.")
        return

    # Print summary
    print(f"\n  추출된 데이터 요약:")
    print(f"  - 행 수: {len(data_rows)}")
    if data_rows:
        total_amount = sum(row[-1] for row in data_rows if isinstance(row[-1], (int, float)))
        print(f"  - 총 금액 ((사용자 수) * (단가) 합계): {total_amount:,.0f}원")

    if args.dry_run:
        print(f"\n  [DRY RUN] 데이터 미리보기 (처음 5행):")
        print(f"  {headers}")
        for row in data_rows[:5]:
            print(f"  {row}")
        if len(data_rows) > 5:
            print(f"  ... ({len(data_rows) - 5}행 더 있음)")
        print("\n  [DRY RUN] 실제 쓰기는 수행하지 않습니다.")
        return

    # Step 5: Create new tab and paste data
    print(f"\n[5/5] MG Summary에 새 탭 생성 및 데이터 붙여넣기 중...")
    spreadsheet_id, tab_name = create_new_month_tab(
        sheets_service, publisher, month, year, headers, data_rows
    )

    print(f"\n{'=' * 60}")
    print(f"완료!")
    print(f"  새 탭: '{tab_name}'")
    print(f"  시트: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
