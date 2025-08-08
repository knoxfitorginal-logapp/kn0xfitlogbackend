import os
import json
import io
from datetime import datetime

# Google Drive configuration
SCOPES = ['https://www.googleapis.com/auth/drive']

# Load credentials from environment or config file
def get_credentials():
    """Get Google Drive API credentials"""
    try:
        # Try to load from environment variable first
        creds_json = os.environ.get('GOOGLE_DRIVE_CREDENTIALS')
        if creds_json:
            from google.oauth2.service_account import Credentials
            creds_info = json.loads(creds_json)
            return Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        
        # Try to load from config file
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.py')
        if os.path.exists(config_path):
            import sys
            sys.path.append(os.path.dirname(config_path))
            try:
                import config
                if hasattr(config, 'GOOGLE_DRIVE_CREDENTIALS'):
                    from google.oauth2.service_account import Credentials
                    return Credentials.from_service_account_info(config.GOOGLE_DRIVE_CREDENTIALS, scopes=SCOPES)
            except ImportError:
                pass
        
        # Return None if no credentials found
        return None
        
    except Exception as e:
        print(f"Error loading Google Drive credentials: {e}")
        return None

class GoogleDriveService:
    def __init__(self):
        self.credentials = get_credentials()
        self.service = None
        
        if self.credentials:
            try:
                from googleapiclient.discovery import build
                self.service = build('drive', 'v3', credentials=self.credentials)
                print("Google Drive service initialized successfully")
            except Exception as e:
                print(f"Error initializing Google Drive service: {e}")
        else:
            print("Google Drive credentials not found - service will be disabled")
    
    def is_available(self):
        """Check if Google Drive service is available"""
        return self.service is not None
    
    def create_user_folder(self, user_email):
        """Create a folder for the user if it doesn't exist, under the specified parent folder"""
        if not self.is_available():
            return None
            
        try:
            import config
            parent_folder_id = getattr(config, 'DRIVE_FOLDER_ID', None)
            
            if not parent_folder_id:
                print("DRIVE_FOLDER_ID not found in config.py. Creating user folder under root.")
                # If no parent folder ID is specified, create directly under root
                folder_name = f"KN0X-FIT_{user_email}"
                query = f"name=\'{folder_name}\' and mimeType=\'application/vnd.google-apps.folder\' and \'root\' in parents"
            else:
                print(f"Using DRIVE_FOLDER_ID: {parent_folder_id} as parent for user folders.")
                folder_name = f"KN0X-FIT_{user_email}"
                query = f"name=\'{folder_name}\' and mimeType=\'application/vnd.google-apps.folder\' and \'{parent_folder_id}\' in parents"

            results = self.service.files().list(q=query, fields="files(id)").execute()
            
            if results["files"]:
                return results["files"][0]["id"]
            
            # Create new folder
            folder_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder"
            }
            if parent_folder_id:
                folder_metadata["parents"] = [parent_folder_id]
            
            folder = self.service.files().create(body=folder_metadata, fields="id").execute()
            return folder["id"]
            
        except Exception as e:
            print(f"Error creating user folder: {e}")
            return None
    
    def upload_file(self, file_path, user_email, upload_type, original_filename, metadata=None):
        """Upload a file to Google Drive"""
        if not self.is_available():
            print("Google Drive service not available for upload.")
            return None
            
        try:
            from googleapiclient.http import MediaIoBaseUpload
            
            # Get or create user folder
            folder_id = self.create_user_folder(user_email)
            if not folder_id:
                print(f"Could not get or create folder for user {user_email}. Upload aborted.")
                return None
            
            # Prepare file metadata
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            drive_filename = f"{upload_type}_{timestamp}_{original_filename}"
            
            file_metadata = {
                'name': drive_filename,
                'parents': [folder_id],
                'description': json.dumps(metadata) if metadata else None
            }
            
            # Upload file
            with open(file_path, 'rb') as file_data:
                media = MediaIoBaseUpload(
                    io.BytesIO(file_data.read()),
                    mimetype='image/jpeg',
                    resumable=True
                )
                
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,name,webViewLink'
                ).execute()
                
                return {
                    'id': file['id'],
                    'name': file['name'],
                    'web_view_link': file.get('webViewLink')
                }
                
        except Exception as e:
            print(f"Error uploading file to Google Drive: {e}")
            return None
    
    def delete_file(self, file_id):
        """Delete a file from Google Drive"""
        if not self.is_available():
            return False
            
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting file from Google Drive: {e}")
            return False
    
    def upload_user_report(self, user_email, report_data):
        """Upload user progress report as JSON"""
        if not self.is_available():
            return None
            
        try:
            from googleapiclient.http import MediaIoBaseUpload
            
            # Get or create user folder
            folder_id = self.create_user_folder(user_email)
            if not folder_id:
                return None
            
            # Prepare report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"progress_report_{timestamp}.json"
            
            file_metadata = {
                'name': report_filename,
                'parents': [folder_id],
                'description': f"Progress report for {user_email} generated on {datetime.now().isoformat()}"
            }
            
            # Convert report to JSON
            report_json = json.dumps(report_data, indent=2, default=str)
            
            media = MediaIoBaseUpload(
                io.BytesIO(report_json.encode('utf-8')),
                mimetype='application/json',
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink'
            ).execute()
            
            return {
                'id': file['id'],
                'name': file['name'],
                'web_view_link': file.get('webViewLink')
            }
            
        except Exception as e:
            print(f"Error uploading report to Google Drive: {e}")
            return None

# Global service instance
drive_service = GoogleDriveService()

