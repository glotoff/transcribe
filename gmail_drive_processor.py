import os
import time
import base64
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/drive.file']


def authenticate_gmail():
    """Authenticate and return Gmail service."""
    creds = None
    if os.path.exists('token_gmail.json'):
        creds = Credentials.from_authorized_user_file('token_gmail.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token_gmail.json', 'w') as token:
            token.write(creds.to_json())
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


def authenticate_drive():
    """Authenticate and return Drive service."""
    creds = None
    if os.path.exists('token_drive.json'):
        creds = Credentials.from_authorized_user_file('token_drive.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token_drive.json', 'w') as token:
            token.write(creds.to_json())
    
    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


def get_email_attachments(service, message_id):
    """Extract attachments from an email."""
    try:
        message = service.users().messages().get(
            userId='me', 
            id=message_id, 
            format='full'
        ).execute()
        
        attachments = []
        payload = message['payload']
        
        if 'parts' in payload:
            for part in payload['parts']:
                if 'filename' in part and part['filename']:
                    if 'body' in part and 'attachmentId' in part['body']:
                        attachment_id = part['body']['attachmentId']
                        attachment = service.users().messages().attachments().get(
                            userId='me',
                            id=attachment_id,
                            messageId=message_id
                        ).execute()
                        
                        data = base64.urlsafe_b64decode(attachment['data'])
                        attachments.append({
                            'filename': part['filename'],
                            'data': data,
                            'mime_type': part.get('mimeType', 'application/octet-stream')
                        })
        
        return attachments
    except HttpError as error:
        print(f'Error getting attachments: {error}')
        return []


def process_attachment(attachment):
    """Process attachment (placeholder for future implementation)."""
    # TODO: Implement actual processing logic
    print(f"Processing attachment: {attachment['filename']}")
    print(f"Size: {len(attachment['data'])} bytes")
    print(f"Type: {attachment['mime_type']}")
    return attachment['data']


def upload_to_drive(service, folder_id, filename, data, mime_type):
    """Upload a file to Google Drive."""
    try:
        file_metadata = {
            'name': filename,
            'parents': [folder_id] if folder_id else []
        }
        
        media = {
            'mimeType': mime_type,
            'body': data
        }
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        print(f"File uploaded to Drive with ID: {file.get('id')}")
        return file.get('id')
    except HttpError as error:
        print(f'Error uploading to Drive: {error}')
        return None


def get_or_create_drive_folder(service, folder_name):
    """Get or create a folder in Google Drive."""
    try:
        # Search for existing folder
        results = service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        
        files = results.get('files', [])
        
        if files:
            print(f"Using existing folder: {files[0]['name']} (ID: {files[0]['id']})")
            return files[0]['id']
        
        # Create new folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        folder = service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        
        print(f"Created new folder: {folder_name} (ID: {folder.get('id')})")
        return folder.get('id')
    except HttpError as error:
        print(f'Error with Drive folder: {error}')
        return None


def poll_gmail_inbox(poll_interval=20, drive_folder_name='Email Attachments'):
    """Poll Gmail inbox for new emails with attachments and upload to Drive."""
    print("Starting Gmail polling...")
    
    gmail_service = authenticate_gmail()
    drive_service = authenticate_drive()
    
    if not gmail_service or not drive_service:
        print("Failed to authenticate services")
        return
    
    # Get or create Drive folder
    folder_id = get_or_create_drive_folder(drive_service, drive_folder_name)
    if not folder_id:
        print("Failed to get/create Drive folder")
        return
    
    processed_message_ids = set()
    
    while True:
        try:
            # Search for messages with attachments
            results = gmail_service.users().messages().list(
                userId='me',
                q='has:attachment',
                maxResults=10
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                print("No messages with attachments found")
            else:
                print(f"Found {len(messages)} messages with attachments")
            
            for message in messages:
                message_id = message['id']
                
                if message_id in processed_message_ids:
                    continue
                
                print(f"Processing message: {message_id}")
                
                # Get attachments
                attachments = get_email_attachments(gmail_service, message_id)
                
                for attachment in attachments:
                    # Process attachment (placeholder)
                    processed_data = process_attachment(attachment)
                    
                    # Upload to Drive
                    if processed_data:
                        upload_to_drive(
                            drive_service,
                            folder_id,
                            attachment['filename'],
                            processed_data,
                            attachment['mime_type']
                        )
                
                processed_message_ids.add(message_id)
            
            print(f"Waiting {poll_interval} seconds before next poll...")
            time.sleep(poll_interval)
            
        except HttpError as error:
            print(f'Error during polling: {error}')
            time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\nPolling stopped by user")
            break


if __name__ == '__main__':
    poll_gmail_inbox()
