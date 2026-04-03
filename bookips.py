"""Bookips spreadsheet automation via Playwright.

Workflow:
1. Navigate to Bookips spreadsheet, Pivot tab
2. Update year, start date, end date cells
3. Refresh BigQuery data connector (Data > Data connectors > Refresh)
4. Read and copy publisher-specific data
"""

import time
import re


async def navigate_to_pivot_tab(page, bookips_url):
    """Navigate to the Bookips spreadsheet and select the Pivot tab."""
    print("  Navigating to Bookips spreadsheet...")
    await page.goto(bookips_url, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(5000)

    # Try multiple selectors for Google Sheets tab buttons
    tab_selectors = [
        'div.docs-sheet-tab',
        '[id^="sheet-button-"]',
        '.docs-sheet-tab-name',
        '[role="tab"]',
        '.goog-tab',
    ]

    # First, collect all visible tab names for debugging
    all_tab_names = []
    for selector in tab_selectors:
        tabs = page.locator(selector)
        count = await tabs.count()
        if count > 0:
            for i in range(count):
                try:
                    text = (await tabs.nth(i).inner_text()).strip()
                    if text:
                        all_tab_names.append((selector, text))
                except Exception:
                    pass

    if all_tab_names:
        print(f"  Found tabs: {[name for _, name in all_tab_names]}")
    else:
        print("  Warning: No tabs detected with known selectors.")
        # Try to find any clickable element at the bottom with "Pivot" text
        print("  Taking screenshot for debugging...")
        await page.screenshot(path="debug_tabs.png")
        print("  Screenshot saved to debug_tabs.png")

    # Try to click on the Pivot tab
    for selector, name in all_tab_names:
        if "pivot" in name.lower():
            tab = page.locator(selector).filter(has_text=re.compile(r'Pivot', re.IGNORECASE))
            await tab.first.click()
            await page.wait_for_timeout(2000)
            print("  Pivot tab selected.")
            return

    # Fallback: try clicking by visible text anywhere on the page
    pivot_by_text = page.get_by_text("Pivot", exact=True)
    if await pivot_by_text.count() > 0:
        await pivot_by_text.first.click()
        await page.wait_for_timeout(2000)
        print("  Pivot tab selected (by text).")
        return

    raise Exception(
        f"Pivot tab not found. Detected tabs: {[name for _, name in all_tab_names]}. "
        "Check debug_tabs.png for the current page state."
    )


async def update_pivot_parameters(page, year: int, start_date: str, end_date: str):
    """Update year, start date, end date in the Pivot tab using keyboard navigation.

    Finds cells by searching for the labels, then updates adjacent cells.
    """
    print(f"  Updating Pivot parameters: year={year}, start={start_date}, end={end_date}")

    # Use Ctrl+H (Find and Replace) or Ctrl+F (Find) to locate cells
    # Strategy: Use the Name Box (cell reference box) to navigate directly
    # But first, we need to find where the parameters are.

    # Use Ctrl+F to find '연도' label
    params = [
        ("연도", str(year)),
        ("시작일", start_date),
        ("종료일", end_date),
    ]

    for label, value in params:
        await _find_and_update_adjacent_cell(page, label, value)

    print("  Pivot parameters updated.")


async def _find_and_update_adjacent_cell(page, label: str, value: str):
    """Find a cell with the given label text and update the cell to its right."""
    # Open Find dialog
    await page.keyboard.press("Control+f" if not _is_mac(page) else "Meta+f")
    await page.wait_for_timeout(500)

    # Type the label to search
    find_input = page.locator('input[name="findInput"]').or_(
        page.locator('.docs-findinput-input')
    )
    await find_input.fill(label)
    await page.wait_for_timeout(300)

    # Press Enter to find
    await find_input.press("Enter")
    await page.wait_for_timeout(500)

    # Close Find dialog
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)

    # Move to the cell to the right (the value cell)
    await page.keyboard.press("Tab")
    await page.wait_for_timeout(200)

    # Type the new value
    await page.keyboard.type(str(value), delay=50)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(300)

    print(f"    {label} = {value}")


async def refresh_data_connectors(page):
    """Refresh BigQuery data connectors via menu: Data > Data connectors > Refresh."""
    print("  Refreshing data connectors...")

    # Click Data menu
    data_menu = page.locator('#docs-data-menu').or_(
        page.locator('div[id="docs-data-menu"]')
    ).or_(
        page.get_by_text("데이터", exact=True).first
    ).or_(
        page.get_by_text("Data", exact=True).first
    )

    await data_menu.click()
    await page.wait_for_timeout(1000)

    # Click Data connectors
    connectors = page.get_by_text("데이터 커넥터").or_(
        page.get_by_text("Data connectors")
    )
    await connectors.first.click()
    await page.wait_for_timeout(1000)

    # Click Refresh options / 새로고침 옵션
    refresh_option = page.get_by_text("새로고침 옵션").or_(
        page.get_by_text("Refresh options")
    ).or_(
        page.get_by_text("새로고침")
    )
    await refresh_option.first.click()
    await page.wait_for_timeout(1000)

    # Click 전체 새로고침 / Refresh all
    refresh_all = page.get_by_text("전체 새로고침").or_(
        page.get_by_text("Refresh all")
    )
    await refresh_all.first.click()
    await page.wait_for_timeout(2000)

    # Wait for refresh to complete (look for completion indicator)
    print("  Waiting for data refresh to complete...")
    # Wait up to 60 seconds for refresh
    for i in range(12):
        await page.wait_for_timeout(5000)
        # Check if a loading spinner or progress bar is still visible
        spinner = page.locator('.docs-loading-indicator').or_(
            page.locator('[aria-label="Loading"]')
        )
        if await spinner.count() == 0:
            break
        print(f"    Still refreshing... ({(i+1)*5}s)")

    print("  Data connectors refreshed.")


async def get_publisher_data(page, publisher: str):
    """Read all data rows for the given publisher from the Pivot tab.

    Uses Ctrl+F to find publisher rows, then copies them.

    Returns:
        list[list[str]]: The copied data rows including headers.
    """
    print(f"  Extracting data for publisher: '{publisher}'...")

    # Strategy: Select all data, copy to clipboard, then filter in Python
    # First, go to cell A1
    await page.keyboard.press("Control+Home" if not _is_mac(page) else "Meta+Home")
    await page.wait_for_timeout(500)

    # Select all data with Ctrl+Shift+End
    await page.keyboard.press("Control+Shift+End" if not _is_mac(page) else "Meta+Shift+End")
    await page.wait_for_timeout(500)

    # Copy to clipboard
    await page.keyboard.press("Control+c" if not _is_mac(page) else "Meta+c")
    await page.wait_for_timeout(1000)

    # Get clipboard content
    clipboard_text = await page.evaluate("navigator.clipboard.readText()")

    if not clipboard_text:
        raise Exception("Failed to copy data from the spreadsheet. Clipboard is empty.")

    # Parse TSV data
    lines = clipboard_text.strip().split("\n")
    if not lines:
        raise Exception("No data found in the Pivot tab.")

    headers = lines[0].split("\t")

    # Find publisher column index
    publisher_col = None
    for idx, h in enumerate(headers):
        if h.strip() == "publisher":
            publisher_col = idx
            break

    if publisher_col is None:
        raise Exception(f"'publisher' column not found. Headers: {headers}")

    # Filter rows by publisher
    filtered_rows = []
    for line in lines[1:]:
        cols = line.split("\t")
        if len(cols) > publisher_col and cols[publisher_col].strip() == publisher:
            filtered_rows.append(cols)

    print(f"  Found {len(filtered_rows)} rows for publisher '{publisher}'")

    # Find the required column indices
    required = ["isbn", "contractedBook.bookName", "COUNTUNIQUE of userHash", "MAX of 단가"]
    col_indices = {}
    for col_name in required:
        for idx, h in enumerate(headers):
            if h.strip() == col_name:
                col_indices[col_name] = idx
                break

    # Build output: required columns + calculated column
    output_headers = required + ["(사용자 수) * (단가)"]
    output_rows = []
    for row in filtered_rows:
        output_row = []
        for col_name in required:
            idx = col_indices.get(col_name)
            if idx is not None and idx < len(row):
                output_row.append(row[idx].strip())
            else:
                output_row.append("")

        # Calculate (사용자 수) * (단가)
        try:
            user_count = float(output_row[2]) if output_row[2] else 0
            unit_price = float(output_row[3]) if output_row[3] else 0
            output_row.append(str(int(user_count * unit_price)))
        except (ValueError, TypeError):
            output_row.append("0")

        output_rows.append(output_row)

    return output_headers, output_rows


def _is_mac(page):
    """Check if running on macOS (for keyboard shortcuts)."""
    # In Playwright, we can't easily detect OS from the page object.
    # Default to checking via platform
    import sys
    return sys.platform == "darwin"
