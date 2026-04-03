"""Configuration for publisher settlement automation."""

# Google Sheets IDs
BOOKIPS_SPREADSHEET_ID = "1xtT0DcS8A3lGCSZPcpvggo4pzZhmF2w1QWeIEo_BNVU"
MG_SUMMARY_SPREADSHEET_ID = "1u18mFtPXz84Yx0vgyu4w0RvxVf2lL0CF_Cz0PCYHdcw"

# OAuth scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# OAuth credentials file path
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
