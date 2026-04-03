"""Google Sheets & Drive OAuth 2.0 authentication module."""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import SCOPES, CREDENTIALS_FILE, TOKEN_FILE


def get_credentials():
    """Get or refresh OAuth 2.0 credentials.

    First run requires browser-based authentication.
    Subsequent runs use the saved token.
    """
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_FILE}' not found. "
                    "Download it from Google Cloud Console > APIs & Credentials > OAuth 2.0 Client IDs."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def get_sheets_service(creds=None):
    """Build and return a Google Sheets API v4 service."""
    if creds is None:
        creds = get_credentials()
    return build("sheets", "v4", credentials=creds)


def get_drive_service(creds=None):
    """Build and return a Google Drive API v3 service."""
    if creds is None:
        creds = get_credentials()
    return build("drive", "v3", credentials=creds)
