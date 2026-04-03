"""Module for extracting publisher data from the 2004 Bookips spreadsheet.

Workflow:
1. Update Pivot tab with year, start date, end date
2. Refresh BigQuery data connector
3. Read and filter data by publisher
"""

import time

from config import BOOKIPS_SPREADSHEET_ID

# Column headers we need from the Pivot tab
REQUIRED_COLUMNS = [
    "isbn",
    "contractedBook.bookName",
    "COUNTUNIQUE of userHash",
    "MAX of 단가",
]


def _find_pivot_sheet_id(sheets_service):
    """Find the sheet ID of the 'Pivot' tab."""
    spreadsheet = sheets_service.spreadsheets().get(
        spreadsheetId=BOOKIPS_SPREADSHEET_ID
    ).execute()

    for sheet in spreadsheet["sheets"]:
        title = sheet["properties"]["title"]
        if title.lower() == "pivot":
            return sheet["properties"]["sheetId"]

    raise ValueError("'Pivot' tab not found in the Bookips spreadsheet.")


def _find_data_source_ids(sheets_service):
    """Find all data source IDs for BigQuery connectors."""
    spreadsheet = sheets_service.spreadsheets().get(
        spreadsheetId=BOOKIPS_SPREADSHEET_ID,
        includeGridData=False,
    ).execute()

    data_source_ids = []
    for ds in spreadsheet.get("dataSources", []):
        data_source_ids.append(ds["dataSourceId"])

    return data_source_ids


def update_pivot_parameters(sheets_service, year: int, start_date: str, end_date: str):
    """Update the year, start date, and end date in the Pivot tab.

    Finds the cells containing the parameter labels and updates the adjacent cells.
    """
    # Read current Pivot tab data to find parameter cells
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=BOOKIPS_SPREADSHEET_ID,
        range="Pivot!A1:Z10",
    ).execute()

    rows = result.get("values", [])

    # Find parameter positions by scanning for labels
    updates = []
    for row_idx, row in enumerate(rows):
        for col_idx, cell in enumerate(row):
            cell_str = str(cell).strip()
            if cell_str == "연도":
                updates.append({
                    "range": f"Pivot!{_col_letter(col_idx + 1)}{row_idx + 1}",
                    "values": [[year]],
                })
            elif cell_str == "시작일":
                updates.append({
                    "range": f"Pivot!{_col_letter(col_idx + 1)}{row_idx + 1}",
                    "values": [[start_date]],
                })
            elif cell_str == "종료일":
                updates.append({
                    "range": f"Pivot!{_col_letter(col_idx + 1)}{row_idx + 1}",
                    "values": [[end_date]],
                })

    if not updates:
        raise ValueError(
            "Could not find '연도', '시작일', '종료일' labels in Pivot tab. "
            "Please check the spreadsheet layout."
        )

    sheets_service.spreadsheets().values().batchUpdate(
        spreadsheetId=BOOKIPS_SPREADSHEET_ID,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": updates,
        },
    ).execute()

    print(f"  Updated Pivot parameters: year={year}, start={start_date}, end={end_date}")


def refresh_data_connectors(sheets_service):
    """Refresh all BigQuery data connectors in the spreadsheet."""
    data_source_ids = _find_data_source_ids(sheets_service)

    if not data_source_ids:
        print("  Warning: No data sources found. Skipping refresh.")
        return

    requests = []
    for ds_id in data_source_ids:
        requests.append({
            "refreshDataSource": {
                "dataSourceId": ds_id,
                "force": True,
            }
        })

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=BOOKIPS_SPREADSHEET_ID,
        body={"requests": requests},
    ).execute()

    # Wait for refresh to complete
    print(f"  Refreshed {len(data_source_ids)} data source(s). Waiting for completion...")
    time.sleep(5)


def get_publisher_data(sheets_service, publisher: str):
    """Read Pivot tab data and filter by publisher.

    Returns:
        tuple: (headers, rows) where headers is a list of column names
               and rows is a list of lists containing the filtered data.
    """
    # Read all data from Pivot tab
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=BOOKIPS_SPREADSHEET_ID,
        range="Pivot!A:Z",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()

    all_rows = result.get("values", [])
    if not all_rows:
        raise ValueError("No data found in Pivot tab.")

    # Find header row and column indices
    header_row = all_rows[0]
    publisher_col = None
    column_indices = {}

    for idx, col_name in enumerate(header_row):
        col_str = str(col_name).strip()
        if col_str == "publisher":
            publisher_col = idx
        if col_str in REQUIRED_COLUMNS:
            column_indices[col_str] = idx

    if publisher_col is None:
        raise ValueError("'publisher' column not found in Pivot tab headers.")

    # Filter rows by publisher
    filtered_rows = []
    for row in all_rows[1:]:
        if len(row) > publisher_col and str(row[publisher_col]).strip() == publisher:
            filtered_row = []
            for col_name in REQUIRED_COLUMNS:
                col_idx = column_indices.get(col_name)
                if col_idx is not None and col_idx < len(row):
                    filtered_row.append(row[col_idx])
                else:
                    filtered_row.append("")
            # Calculate (사용자 수) * (단가)
            try:
                user_count_idx = column_indices.get("COUNTUNIQUE of userHash")
                unit_price_idx = column_indices.get("MAX of 단가")
                user_count = float(row[user_count_idx]) if user_count_idx is not None and user_count_idx < len(row) else 0
                unit_price = float(row[unit_price_idx]) if unit_price_idx is not None and unit_price_idx < len(row) else 0
                filtered_row.append(user_count * unit_price)
            except (ValueError, TypeError):
                filtered_row.append(0)

            filtered_rows.append(filtered_row)

    output_headers = REQUIRED_COLUMNS + ["(사용자 수) * (단가)"]

    print(f"  Found {len(filtered_rows)} rows for publisher '{publisher}'")
    return output_headers, filtered_rows


def _col_letter(col_index: int) -> str:
    """Convert a 0-based column index to a column letter (A, B, ..., Z, AA, ...)."""
    result = ""
    while col_index >= 0:
        result = chr(col_index % 26 + ord("A")) + result
        col_index = col_index // 26 - 1
    return result
