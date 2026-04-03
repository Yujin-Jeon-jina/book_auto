#!/usr/bin/env python3
"""Publisher settlement automation script (Playwright browser version).

Usage:
    python3 main.py --publisher 개념원리 --month 3 --year 2026
    python3 main.py -p 개념원리 -m 3          # year defaults to current year
    python3 main.py -p 개념원리 -m 3 --dry-run  # read only, no writes
"""

import argparse
import asyncio
import calendar
from datetime import datetime

from playwright.async_api import async_playwright

from config import BOOKIPS_URL, MG_SUMMARY_URL, BROWSER_DATA_DIR
from bookips import (
    navigate_to_pivot_tab,
    update_pivot_parameters,
    refresh_data_connectors,
    get_publisher_data,
)
from mg_summary import (
    find_publisher_last_month_link,
    copy_previous_month_sheet,
    rename_and_setup_new_tab,
    paste_publisher_data,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="출판사 정산 자동화 (Playwright 브라우저 버전)"
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
        help="데이터 읽기만 수행, 시트에 쓰기하지 않음",
    )
    return parser.parse_args()


async def run(args):
    publisher = args.publisher
    month = args.month
    year = args.year

    _, last_day = calendar.monthrange(year, month)
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{last_day:02d}"

    print(f"{'=' * 60}")
    print(f"출판사 정산 자동화 (Browser)")
    print(f"{'=' * 60}")
    print(f"  출판사: {publisher}")
    print(f"  기간:   {start_date} ~ {end_date}")
    print(f"{'=' * 60}")

    async with async_playwright() as p:
        # Launch browser with persistent context (keeps Google login)
        print("\n[1/6] 브라우저 실행 중...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_DATA_DIR,
            headless=False,
            args=["--window-size=1400,900"],
            viewport={"width": 1400, "height": 900},
        )

        page = context.pages[0] if context.pages else await context.new_page()

        # Grant clipboard permissions
        await context.grant_permissions(["clipboard-read", "clipboard-write"])

        try:
            # Step 2: Navigate to Bookips and select Pivot tab
            print("\n[2/6] Bookips 시트 Pivot 탭 이동 중...")
            await navigate_to_pivot_tab(page, BOOKIPS_URL)

            # Step 3: Update parameters
            print("\n[3/6] Pivot 파라미터 설정 중...")
            await update_pivot_parameters(page, year, start_date, end_date)

            # Step 4: Refresh data connectors
            if not args.skip_refresh:
                print("\n[4/6] BigQuery 데이터 커넥터 새로고침 중...")
                await refresh_data_connectors(page)
            else:
                print("\n[4/6] BigQuery 새로고침 건너뜀 (--skip-refresh)")

            # Step 5: Get publisher data
            print(f"\n[5/6] '{publisher}' 데이터 추출 중...")
            headers, data_rows = await get_publisher_data(page, publisher)

            if not data_rows:
                print(f"\n  '{publisher}'에 해당하는 데이터가 없습니다.")
                return

            # Print summary
            total_amount = sum(
                float(row[-1]) for row in data_rows
                if row[-1] and row[-1] != "0"
            )
            print(f"\n  추출 데이터 요약:")
            print(f"  - 행 수: {len(data_rows)}")
            print(f"  - 총 금액: {total_amount:,.0f}원")

            if args.dry_run:
                print(f"\n  [DRY RUN] 데이터 미리보기 (처음 5행):")
                print(f"  {headers}")
                for row in data_rows[:5]:
                    print(f"  {row}")
                if len(data_rows) > 5:
                    print(f"  ... ({len(data_rows) - 5}행 더 있음)")
                print("\n  [DRY RUN] 쓰기는 수행하지 않습니다.")
                return

            # Step 6: Create new tab in MG Summary linked sheet
            print(f"\n[6/6] MG Summary 시트 작업 중...")

            # Find previous month's link
            prev_link = await find_publisher_last_month_link(
                page, MG_SUMMARY_URL, publisher, month, year
            )

            # Copy the previous month's sheet
            await copy_previous_month_sheet(page, prev_link)

            # Rename the tab
            tab_name = await rename_and_setup_new_tab(page, publisher, month, year)

            # Paste data
            await paste_publisher_data(page, headers, data_rows)

            print(f"\n{'=' * 60}")
            print(f"완료!")
            print(f"  새 탭: '{tab_name}'")
            print(f"{'=' * 60}")

            # Keep browser open for user to verify
            print("\n  브라우저에서 결과를 확인하세요.")
            print("  Enter를 누르면 브라우저가 닫힙니다...")
            await asyncio.get_event_loop().run_in_executor(None, input)

        except Exception as e:
            print(f"\n  오류 발생: {e}")
            print("  브라우저를 열어둡니다. 수동으로 확인 후 Enter를 누르세요...")
            await asyncio.get_event_loop().run_in_executor(None, input)
            raise
        finally:
            await context.close()


def main():
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
