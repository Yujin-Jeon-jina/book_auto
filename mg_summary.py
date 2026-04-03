"""Module for managing the MG Summary spreadsheet.

Workflow:
1. Find the publisher row in the summary sheet
2. Get the previous month's sheet link
3. Copy that sheet as a template
4. Rename the new tab (e.g., '26.03 개념원리')
5. Paste publisher data into the new tab
"""

import re

from config import MG_SUMMARY_SPREADSHEET_ID


def _extract_spreadsheet_id_from_url(url: str) -> str:
    """Extract spreadsheet ID from a Google Sheets URL."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract spreadsheet ID from URL: {url}")


def _extract_gid_from_url(url: str) -> int | None:
    """Extract gid (sheet ID) from a Google Sheets URL."""
    match = re.search(r"gid=(\d+)", url)
    if match:
        return int(match.group(1))
    return None


def find_publisher_last_month_link(sheets_service, publisher: str, target_month: int, target_year: int):
    """Find the publisher in the MG summary and get last month's link.

    Scans the summary sheet for a row matching the publisher name,
    then finds the link for the previous month.

    Returns:
        tuple: (spreadsheet_id, sheet_id, link_url) of the previous month's sheet
    """
    # Calculate previous month
    if target_month == 1:
        prev_month = 12
        prev_year = target_year - 1
    else:
        prev_month = target_month - 1
        prev_year = target_year

    # Read the summary sheet to find publisher and month links
    result = sheets_service.spreadsheets().get(
        spreadsheetId=MG_SUMMARY_SPREADSHEET_ID,
        includeGridData=False,
    ).execute()

    # Get the first sheet name
    first_sheet_title = result["sheets"][0]["properties"]["title"]

    # Read all data
    data_result = sheets_service.spreadsheets().values().get(
        spreadsheetId=MG_SUMMARY_SPREADSHEET_ID,
        range=f"'{first_sheet_title}'!A:Z",
        valueRenderOption="FORMATTED_VALUE",
    ).execute()

    rows = data_result.get("values", [])
    if not rows:
        raise ValueError("MG Summary sheet is empty.")

    # Find header row to locate month columns
    header_row = rows[0]

    # Find the publisher row
    publisher_row_idx = None
    for row_idx, row in enumerate(rows):
        for cell in row:
            if str(cell).strip() == publisher:
                publisher_row_idx = row_idx
                break
        if publisher_row_idx is not None:
            break

    if publisher_row_idx is None:
        raise ValueError(f"Publisher '{publisher}' not found in MG Summary sheet.")

    # Now we need to find the link in the previous month's column
    # Read the rich text / hyperlinks using the spreadsheet get with includeGridData
    sheet_id = result["sheets"][0]["properties"]["sheetId"]

    grid_result = sheets_service.spreadsheets().get(
        spreadsheetId=MG_SUMMARY_SPREADSHEET_ID,
        ranges=[f"'{first_sheet_title}'!A{publisher_row_idx + 1}:Z{publisher_row_idx + 1}"],
        includeGridData=True,
    ).execute()

    row_data = grid_result["sheets"][0]["data"][0].get("rowData", [])
    if not row_data:
        raise ValueError(f"No data found for publisher '{publisher}' row.")

    cells = row_data[0].get("values", [])

    # Look for hyperlinks in the publisher's row
    # Find the cell with a link that corresponds to the previous month
    prev_month_str_patterns = [
        f"{prev_year % 100:02d}.{prev_month:02d}",  # e.g., "26.02"
        f"{prev_year}-{prev_month:02d}",              # e.g., "2026-02"
        f"{prev_month}월",                             # e.g., "2월"
    ]

    # Also read the header row with grid data to match columns
    header_grid_result = sheets_service.spreadsheets().get(
        spreadsheetId=MG_SUMMARY_SPREADSHEET_ID,
        ranges=[f"'{first_sheet_title}'!A1:Z1"],
        includeGridData=True,
    ).execute()

    header_cells = header_grid_result["sheets"][0]["data"][0].get("rowData", [{}])[0].get("values", [])

    # Strategy: find the column for previous month in the header, then get the link from that column
    target_col = None
    for col_idx, hcell in enumerate(header_cells):
        formatted = hcell.get("formattedValue", "")
        for pattern in prev_month_str_patterns:
            if pattern in str(formatted):
                target_col = col_idx
                break
        if target_col is not None:
            break

    # If we couldn't find by header, scan all cells with hyperlinks
    link_url = None
    if target_col is not None and target_col < len(cells):
        cell = cells[target_col]
        hyperlink = cell.get("hyperlink")
        if hyperlink:
            link_url = hyperlink
        # Also check textFormatRuns for embedded links
        if not link_url:
            text_format = cell.get("effectiveFormat", {}).get("textFormat", {})
            link = text_format.get("link", {})
            if link.get("uri"):
                link_url = link["uri"]

    # Fallback: scan all cells for a hyperlink containing previous month info
    if not link_url:
        for col_idx, cell in enumerate(cells):
            hyperlink = cell.get("hyperlink")
            if hyperlink:
                cell_value = cell.get("formattedValue", "")
                for pattern in prev_month_str_patterns:
                    if pattern in str(cell_value):
                        link_url = hyperlink
                        break
            if link_url:
                break

    # Last resort: just find any hyperlink in the row
    if not link_url:
        all_links = []
        for col_idx, cell in enumerate(cells):
            hyperlink = cell.get("hyperlink")
            if hyperlink and "spreadsheets" in str(hyperlink):
                all_links.append((col_idx, hyperlink, cell.get("formattedValue", "")))

        if all_links:
            # Try to match by looking at month-like patterns in nearby cells
            print(f"  Found {len(all_links)} hyperlinks in publisher row. Available links:")
            for col_idx, url, val in all_links:
                print(f"    Column {col_idx}: '{val}' -> {url}")
            # Use the last link (most recent month)
            link_url = all_links[-1][1]
            print(f"  Using last link as previous month template.")

    if not link_url:
        raise ValueError(
            f"Could not find a hyperlink for the previous month "
            f"({prev_year % 100:02d}.{prev_month:02d}) in publisher '{publisher}' row."
        )

    # Extract spreadsheet ID and gid from the link
    linked_spreadsheet_id = _extract_spreadsheet_id_from_url(link_url)
    linked_gid = _extract_gid_from_url(link_url)

    print(f"  Found previous month link: {link_url}")
    return linked_spreadsheet_id, linked_gid, link_url


def copy_sheet_as_template(sheets_service, source_spreadsheet_id: str, source_sheet_id: int | None,
                           dest_spreadsheet_id: str):
    """Copy a sheet from one spreadsheet to another.

    Returns:
        int: The sheet ID of the newly created copy.
    """
    if source_sheet_id is None:
        # Get the first sheet if no specific sheet ID
        source_meta = sheets_service.spreadsheets().get(
            spreadsheetId=source_spreadsheet_id,
            includeGridData=False,
        ).execute()
        source_sheet_id = source_meta["sheets"][0]["properties"]["sheetId"]

    body = {
        "destinationSpreadsheetId": dest_spreadsheet_id,
    }

    response = sheets_service.spreadsheets().sheets().copyTo(
        spreadsheetId=source_spreadsheet_id,
        sheetId=source_sheet_id,
        body=body,
    ).execute()

    new_sheet_id = response["sheetId"]
    print(f"  Copied sheet (new sheet ID: {new_sheet_id})")
    return new_sheet_id


def create_new_month_tab(sheets_service, publisher: str, month: int, year: int, headers, data_rows):
    """Create a new tab in the linked spreadsheet for the current month.

    Instead of copying to a different spreadsheet, this approach:
    1. Finds the previous month's linked spreadsheet
    2. Copies the previous month's sheet within that spreadsheet
    3. Renames it to the new month
    4. Clears old data and pastes new data
    """
    # Find the previous month's link
    linked_spreadsheet_id, linked_gid, link_url = find_publisher_last_month_link(
        sheets_service, publisher, month, year
    )

    # Copy the sheet within the same spreadsheet
    new_sheet_id = copy_sheet_as_template(
        sheets_service,
        source_spreadsheet_id=linked_spreadsheet_id,
        source_sheet_id=linked_gid,
        dest_spreadsheet_id=linked_spreadsheet_id,
    )

    # Rename the new sheet
    tab_name = f"{year % 100:02d}.{month:02d} {publisher}"

    # Move the sheet to the first position and rename it
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=linked_spreadsheet_id,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": new_sheet_id,
                            "title": tab_name,
                            "index": 0,
                        },
                        "fields": "title,index",
                    }
                }
            ]
        },
    ).execute()

    print(f"  Renamed and moved tab to first position: '{tab_name}'")

    # Find the data area to clear and paste
    # First, read the template to understand the layout
    meta = sheets_service.spreadsheets().get(
        spreadsheetId=linked_spreadsheet_id,
        includeGridData=False,
    ).execute()

    # Clear existing data rows (keep headers/formatting from template)
    # We'll find where the data starts by reading the first few rows
    template_data = sheets_service.spreadsheets().values().get(
        spreadsheetId=linked_spreadsheet_id,
        range=f"'{tab_name}'!A1:Z5",
        valueRenderOption="FORMATTED_VALUE",
    ).execute()

    template_rows = template_data.get("values", [])

    # Find the header row in the template that matches our data columns
    data_start_row = 1  # Default: start from row 1
    for row_idx, row in enumerate(template_rows):
        for cell in row:
            cell_str = str(cell).strip().lower()
            if "isbn" in cell_str or "bookname" in cell_str:
                data_start_row = row_idx + 2  # Data starts after header
                break

    # Clear existing data below the header
    clear_range = f"'{tab_name}'!A{data_start_row}:Z1000"
    sheets_service.spreadsheets().values().clear(
        spreadsheetId=linked_spreadsheet_id,
        range=clear_range,
    ).execute()

    # Paste new data
    if data_rows:
        paste_range = f"'{tab_name}'!A{data_start_row}:E{data_start_row + len(data_rows) - 1}"
        sheets_service.spreadsheets().values().update(
            spreadsheetId=linked_spreadsheet_id,
            range=paste_range,
            valueInputOption="USER_ENTERED",
            body={"values": data_rows},
        ).execute()

        print(f"  Pasted {len(data_rows)} rows into '{tab_name}'")
    else:
        print(f"  Warning: No data rows to paste for publisher '{publisher}'")

    # Update the MG Summary with a link to the new tab
    _update_summary_link(sheets_service, publisher, month, year, linked_spreadsheet_id, tab_name)

    return linked_spreadsheet_id, tab_name


def _update_summary_link(sheets_service, publisher: str, month: int, year: int,
                         target_spreadsheet_id: str, tab_name: str):
    """Update the MG Summary sheet with a link to the newly created tab."""
    # Read the summary sheet
    result = sheets_service.spreadsheets().get(
        spreadsheetId=MG_SUMMARY_SPREADSHEET_ID,
        includeGridData=False,
    ).execute()

    first_sheet_title = result["sheets"][0]["properties"]["title"]

    data_result = sheets_service.spreadsheets().values().get(
        spreadsheetId=MG_SUMMARY_SPREADSHEET_ID,
        range=f"'{first_sheet_title}'!A:Z",
        valueRenderOption="FORMATTED_VALUE",
    ).execute()

    rows = data_result.get("values", [])
    header_row = rows[0] if rows else []

    # Find the current month column
    month_str_patterns = [
        f"{year % 100:02d}.{month:02d}",
        f"{year}-{month:02d}",
        f"{month}월",
    ]

    target_col = None
    for col_idx, cell in enumerate(header_row):
        for pattern in month_str_patterns:
            if pattern in str(cell).strip():
                target_col = col_idx
                break
        if target_col is not None:
            break

    # Find publisher row
    publisher_row = None
    for row_idx, row in enumerate(rows):
        for cell in row:
            if str(cell).strip() == publisher:
                publisher_row = row_idx
                break
        if publisher_row is not None:
            break

    if target_col is not None and publisher_row is not None:
        col_letter = chr(ord("A") + target_col) if target_col < 26 else "A"
        cell_ref = f"'{first_sheet_title}'!{col_letter}{publisher_row + 1}"

        link_url = f"https://docs.google.com/spreadsheets/d/{target_spreadsheet_id}/edit#gid=0"
        formula = f'=HYPERLINK("{link_url}", "{tab_name}")'

        sheets_service.spreadsheets().values().update(
            spreadsheetId=MG_SUMMARY_SPREADSHEET_ID,
            range=cell_ref,
            valueInputOption="USER_ENTERED",
            body={"values": [[formula]]},
        ).execute()

        print(f"  Updated MG Summary link at {cell_ref}")
    else:
        print(f"  Warning: Could not find cell to update in MG Summary for {month}월 {publisher}")
