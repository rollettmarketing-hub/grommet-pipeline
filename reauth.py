#!/usr/bin/env python3
"""
Run this script once to re-authenticate with Google.
It will open a browser, you log in, then it saves a fresh token.json
and prints the value to paste into Railway's GOOGLE_TOKEN_JSON env var.
"""
import os, json

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

BASE_DIR = os.path.dirname(__file__)
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'token.json')

print("Starting Google OAuth flow...")
print("A browser window will open — log in and grant access.\n")

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_FILE, 'w') as f:
    f.write(creds.to_json())

print("\n✅ token.json saved!\n")
print("=" * 60)
print("Copy the value below into Railway → Variables → GOOGLE_TOKEN_JSON:")
print("=" * 60)
print(creds.to_json())
print("=" * 60)
