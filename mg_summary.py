"""MG Summary spreadsheet automation via Playwright.

Workflow:
1. Navigate to MG Summary spreadsheet
2. Find the publisher row
3. Get the previous month's linked sheet URL
4. Open that sheet and duplicate the tab
5. Rename the new tab (e.g., '26.03 개념원리')
6. Clear old data and paste new publisher data
"""

import re


async def find_publisher_last_month_link(page, mg_summary_url, publisher: str,
                                          target_month: int, target_year: int):
    """Find the publisher in MG Summary and get the previous month's sheet link.

    Returns:
        str: URL of the previous month's sheet
    """
    # Calculate previous month
    if target_month == 1:
        prev_month = 12
        prev_year = target_year - 1
    else:
        prev_month = target_month - 1
        prev_year = target_year

    prev_month_label = f"{prev_year % 100:02d}.{prev_month:02d}"

    print(f"  Looking for '{publisher}' previous month ({prev_month_label}) link...")

    # Navigate to MG Summary
    await page.goto(mg_summary_url, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(3000)

    # Use Ctrl+F to find the publisher
    is_mac = _is_mac()
    await page.keyboard.press("Meta+f" if is_mac else "Control+f")
    await page.wait_for_timeout(500)

    find_input = page.locator('input[name="findInput"]').or_(
        page.locator('.docs-findinput-input')
    )
    await find_input.fill(publisher)
    await find_input.press("Enter")
    await page.wait_for_timeout(1000)

    # Close find dialog
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)

    # Now we need to find the previous month's link in this row
    # Strategy: Read the entire row, find the cell with a hyperlink for prev month
    # First, go to beginning of the row
    await page.keyboard.press("Home")
    await page.wait_for_timeout(300)

    # Select entire row
    await page.keyboard.press("Shift+Control+End" if not is_mac else "Shift+Meta+End")
    await page.wait_for_timeout(300)

    # Copy row data
    await page.keyboard.press("Meta+c" if is_mac else "Control+c")
    await page.wait_for_timeout(500)

    clipboard_text = await page.evaluate("navigator.clipboard.readText()")

    # Now we need to find the hyperlink. Google Sheets doesn't copy hyperlinks to clipboard as text.
    # Alternative approach: Navigate cell by cell to find the link

    # Go back to the publisher cell
    await page.keyboard.press("Home")
    await page.wait_for_timeout(200)

    # We need to find the column with the previous month header
    # Go to row 1 to check headers
    await page.keyboard.press("Meta+Home" if is_mac else "Control+Home")
    await page.wait_for_timeout(300)

    # Select all header row
    await page.keyboard.press("Shift+Meta+Right" if is_mac else "Shift+Control+Right")
    await page.wait_for_timeout(300)
    await page.keyboard.press("Meta+c" if is_mac else "Control+c")
    await page.wait_for_timeout(500)

    header_text = await page.evaluate("navigator.clipboard.readText()")
    header_cells = header_text.strip().split("\t")

    # Find the previous month column
    prev_month_col = None
    prev_month_patterns = [prev_month_label, f"{prev_month}월", f"{prev_year}-{prev_month:02d}"]

    for idx, cell in enumerate(header_cells):
        for pattern in prev_month_patterns:
            if pattern in cell.strip():
                prev_month_col = idx
                break
        if prev_month_col is not None:
            break

    if prev_month_col is None:
        # Try finding "Link" column or similar
        for idx, cell in enumerate(header_cells):
            if "link" in cell.strip().lower():
                prev_month_col = idx
                break

    # Navigate to the publisher's row and the target column
    # First find publisher again
    await page.keyboard.press("Meta+f" if is_mac else "Control+f")
    await page.wait_for_timeout(500)
    find_input = page.locator('input[name="findInput"]').or_(
        page.locator('.docs-findinput-input')
    )
    await find_input.fill(publisher)
    await find_input.press("Enter")
    await page.wait_for_timeout(500)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)

    # Navigate to the target column
    if prev_month_col is not None:
        # Go to beginning of row then move right to the target column
        await page.keyboard.press("Home")
        await page.wait_for_timeout(200)
        for _ in range(prev_month_col):
            await page.keyboard.press("ArrowRight")
            await page.wait_for_timeout(100)
    else:
        print(f"  Warning: Could not find previous month column. Searching for Link column...")
        # Navigate right from publisher cell looking for a link
        await page.keyboard.press("Home")
        await page.wait_for_timeout(200)

    # Try to extract the hyperlink from the current cell
    link_url = await _get_cell_hyperlink(page)

    if not link_url:
        # Scan across the row for a hyperlink
        await page.keyboard.press("Home")
        await page.wait_for_timeout(200)
        for i in range(20):  # Check up to 20 columns
            link_url = await _get_cell_hyperlink(page)
            if link_url and "spreadsheets" in link_url:
                print(f"  Found link in column {i}")
                break
            await page.keyboard.press("ArrowRight")
            await page.wait_for_timeout(200)
            link_url = None

    if not link_url:
        raise Exception(
            f"Could not find a hyperlink for previous month ({prev_month_label}) "
            f"in publisher '{publisher}' row."
        )

    print(f"  Found previous month link: {link_url}")
    return link_url


async def _get_cell_hyperlink(page):
    """Try to extract a hyperlink from the currently selected cell."""
    # Right-click to open context menu and look for "Edit link" or check cell info
    # Alternative: Use the formula bar to check for HYPERLINK formula

    # Read the formula bar
    formula_bar = page.locator('#t-formula-bar-input-container').or_(
        page.locator('.cell-input')
    ).or_(
        page.locator('[id="t-formula-bar-input"]')
    )

    formula_text = ""
    try:
        formula_text = await formula_bar.inner_text()
    except Exception:
        pass

    # Check if it contains a HYPERLINK formula
    match = re.search(r'HYPERLINK\s*\(\s*"([^"]+)"', formula_text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Check for plain URL in cell
    url_match = re.search(r'https?://docs\.google\.com/spreadsheets/d/[a-zA-Z0-9_-]+', formula_text)
    if url_match:
        return url_match.group(0)

    return None


async def copy_previous_month_sheet(page, source_url: str):
    """Open the source sheet and duplicate the first tab.

    Returns the page object (now on the source sheet).
    """
    print(f"  Opening previous month sheet...")
    await page.goto(source_url, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(3000)

    # Right-click on the first tab to duplicate it
    first_tab = page.locator('div.docs-sheet-tab').first.or_(
        page.locator('[id^="sheet-button-"]').first
    )

    # Right-click to get context menu
    await first_tab.click(button="right")
    await page.wait_for_timeout(500)

    # Click "Duplicate" / "복제"
    duplicate_option = page.get_by_text("복제").or_(
        page.get_by_text("Duplicate")
    )
    await duplicate_option.first.click()
    await page.wait_for_timeout(2000)

    print("  Previous month sheet duplicated.")


async def rename_and_setup_new_tab(page, publisher: str, month: int, year: int):
    """Rename the duplicated tab to the new month format and move it to the first position.

    Tab name format: 'YY.MM publisher' (e.g., '26.03 개념원리')
    """
    tab_name = f"{year % 100:02d}.{month:02d} {publisher}"
    print(f"  Renaming tab to '{tab_name}'...")

    # The duplicated tab should be selected and usually named "Copy of ..."
    # Double-click on the active tab to rename it
    # Find the tab that starts with "Copy of" or "사본"
    copy_tab = page.locator('div.docs-sheet-tab').filter(
        has_text=re.compile(r'(Copy of|사본)', re.IGNORECASE)
    )

    if await copy_tab.count() > 0:
        await copy_tab.first.dblclick()
    else:
        # The newly created tab is likely the last one and selected
        active_tab = page.locator('div.docs-sheet-active-tab').or_(
            page.locator('.docs-sheet-tab.docs-sheet-active-tab')
        )
        await active_tab.first.dblclick()

    await page.wait_for_timeout(500)

    # Clear existing name and type new name
    is_mac = _is_mac()
    await page.keyboard.press("Meta+a" if is_mac else "Control+a")
    await page.keyboard.type(tab_name, delay=30)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(500)

    # Move the tab to the first position by dragging or using right-click menu
    # Right-click on the tab
    renamed_tab = page.locator('div.docs-sheet-tab').filter(has_text=tab_name)
    if await renamed_tab.count() > 0:
        await renamed_tab.first.click(button="right")
        await page.wait_for_timeout(500)

        # Look for "Move left" option and click it multiple times
        # Or use "Move to beginning" if available
        move_option = page.get_by_text("모든 시트의 앞으로 이동").or_(
            page.get_by_text("Move to beginning")
        ).or_(
            page.get_by_text("왼쪽으로 이동")
        ).or_(
            page.get_by_text("Move left")
        )

        try:
            await move_option.first.click()
            await page.wait_for_timeout(500)
        except Exception:
            print("  Note: Could not auto-move tab. You may need to move it manually.")

    print(f"  Tab renamed to '{tab_name}'")
    return tab_name


async def paste_publisher_data(page, headers: list, data_rows: list):
    """Clear the existing data area and paste new publisher data."""
    if not data_rows:
        print("  No data to paste.")
        return

    print(f"  Pasting {len(data_rows)} rows of data...")
    is_mac = _is_mac()

    # Go to the first data cell (find where data starts)
    # Navigate to A1 first
    await page.keyboard.press("Meta+Home" if is_mac else "Control+Home")
    await page.wait_for_timeout(300)

    # Find the header row that contains 'isbn' to know where data starts
    await page.keyboard.press("Meta+f" if is_mac else "Control+f")
    await page.wait_for_timeout(500)
    find_input = page.locator('input[name="findInput"]').or_(
        page.locator('.docs-findinput-input')
    )
    await find_input.fill("isbn")
    await find_input.press("Enter")
    await page.wait_for_timeout(500)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)

    # Move down one row (to the first data row)
    await page.keyboard.press("Home")
    await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(200)

    # Select from current position to the end of data area and clear it
    await page.keyboard.press(
        "Shift+Meta+End" if is_mac else "Shift+Control+End"
    )
    await page.wait_for_timeout(200)
    await page.keyboard.press("Delete")
    await page.wait_for_timeout(300)

    # Go back to the first data cell
    await page.keyboard.press("Meta+f" if is_mac else "Control+f")
    await page.wait_for_timeout(500)
    find_input = page.locator('input[name="findInput"]').or_(
        page.locator('.docs-findinput-input')
    )
    await find_input.fill("isbn")
    await find_input.press("Enter")
    await page.wait_for_timeout(500)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    await page.keyboard.press("Home")
    await page.keyboard.press("ArrowDown")
    await page.wait_for_timeout(200)

    # Build TSV text from data rows and paste it
    tsv_lines = []
    for row in data_rows:
        tsv_lines.append("\t".join(str(cell) for cell in row))
    tsv_text = "\n".join(tsv_lines)

    # Write to clipboard and paste
    await page.evaluate(f"navigator.clipboard.writeText({repr(tsv_text)})")
    await page.wait_for_timeout(200)
    await page.keyboard.press("Meta+v" if is_mac else "Control+v")
    await page.wait_for_timeout(2000)

    print(f"  Data pasted successfully ({len(data_rows)} rows)")


def _is_mac():
    import sys
    return sys.platform == "darwin"
