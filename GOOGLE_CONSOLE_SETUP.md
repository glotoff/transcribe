# Google Console Configuration Guide

This guide explains how to configure Google Cloud Console to enable Gmail and Drive API access for this application.

## Prerequisites

- A Google account
- Google Cloud Console access

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown at the top
3. Click "New Project"
4. Enter a project name (e.g., "GmailDriveProcessor")
5. Click "Create"
6. Wait for the project to be created, then select it from the dropdown

## Step 2: Enable APIs

1. In the Cloud Console, go to "APIs & Services" > "Library"
2. Search for "Gmail API"
3. Click on it and click "Enable"
4. Search for "Google Drive API"
5. Click on it and click "Enable"

## Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" > "OAuth consent screen"
2. Choose "External" (for personal use) and click "Create"
3. Fill in the required fields:
   - **App name**: Gmail Drive Processor
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
4. Click "Save and Continue"
5. Skip the "Scopes" section (click "Save and Continue")
6. Skip the "Test users" section (click "Save and Continue")
7. Click "Back to Dashboard"

## Step 4: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. Select "Desktop application" as the application type
4. Enter a name (e.g., "Gmail Drive Client")
5. Click "Create"
6. A dialog will appear with your client ID and client secret
7. Click "Download JSON" to download the credentials file
8. Rename the downloaded file to `credentials.json`
9. Move `credentials.json` to your project directory (same folder as `gmail_drive_processor.py`)

## Step 5: Grant Access (First Run)

When you run the application for the first time:

1. The application will open a browser window
2. Sign in to your Google account (if not already signed in)
3. Review the permissions requested:
   - Read your Gmail messages
   - Create and upload files to your Google Drive
4. Click "Allow"
5. The application will save a token file (`token_gmail.json` and `token_drive.json`) for future use

## Step 6: Run the Application

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the Gmail polling script:
```bash
python gmail_drive_processor.py
```

Or integrate it into your main application by importing and calling the functions.

## Important Notes

- **Security**: Never commit `credentials.json`, `token_gmail.json`, or `token_drive.json` to version control
- Add these files to your `.gitignore`:
  ```
  credentials.json
  token_gmail.json
  token_drive.json
  ```
- The tokens will automatically refresh when they expire
- If you need to re-authenticate, delete the token files and run the application again

## Troubleshooting

### "Invalid client secret" error
- Ensure `credentials.json` is in the correct directory
- Verify the file is not corrupted (check it's valid JSON)

### "Access blocked" error
- Go to OAuth consent screen in Google Console
- Add your email as a test user
- Or publish the app for production use

### API quota exceeded
- Check your API usage in Google Console
- Consider increasing quotas if needed

## Scopes Used

The application requests the following OAuth scopes:
- `https://www.googleapis.com/auth/gmail.readonly` - Read Gmail messages
- `https://www.googleapis.com/auth/drive.file` - Create and access files in Drive (limited to files created by this app)
