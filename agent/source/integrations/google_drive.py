"""
Google Drive連携機能
研究データの自動同期とバックアップ機能を提供
"""

import os
import json
import time
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging
from datetime import datetime, timedelta

try:
    from googleapiclient.discovery import build
    from google.oauth2.service_account import Credentials
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials as UserCredentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

logger = logging.getLogger(__name__)

class GoogleDriveIntegration:
    """Google Drive連携クラス"""
    
    def __init__(self):
        self.enabled = os.getenv('ENABLE_GOOGLE_DRIVE', 'false').lower() == 'true'
        self.credentials_path = os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH', 'credentials/google_drive_credentials.json')
        self.folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID', None)
        self.max_file_size_mb = int(os.getenv('GOOGLE_DRIVE_MAX_FILE_SIZE_MB', '500'))
        self.sync_interval = int(os.getenv('GOOGLE_DRIVE_SYNC_INTERVAL', '300'))
        self.auto_upload = os.getenv('GOOGLE_DRIVE_AUTO_UPLOAD', 'true').lower() == 'true'
        self.backup_enabled = os.getenv('GOOGLE_DRIVE_BACKUP_ENABLED', 'true').lower() == 'true'
        
        self.service = None
        self.last_sync = None
        
        if not GOOGLE_DRIVE_AVAILABLE:
            logger.warning("Google Drive API libraries not installed. Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
            self.enabled = False
        
        if self.enabled:
            self._initialize_service()
    
    def _initialize_service(self) -> bool:
        """Google Drive APIサービスを初期化"""
        try:
            if not os.path.exists(self.credentials_path):
                logger.error(f"Google Drive credentials file not found: {self.credentials_path}")
                self.enabled = False
                return False
            
            # 認証ファイルの内容を確認
            with open(self.credentials_path, 'r') as f:
                creds_data = json.load(f)
            
            # サービスアカウント認証またはOAuthクライアント認証を判定
            if 'type' in creds_data and creds_data['type'] == 'service_account':
                # サービスアカウント認証
                creds = Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/drive']
                )
            elif 'installed' in creds_data or 'web' in creds_data:
                # OAuthクライアント認証（開発用）
                logger.warning("OAuth client credentials detected. For production, use service account credentials.")
                
                # 一時的にサービス無効化（OAuth フローが必要）
                logger.info("Google Drive integration disabled. OAuth flow required for client credentials.")
                self.enabled = False
                return False
            else:
                logger.error("Invalid credentials file format")
                self.enabled = False
                return False
            
            self.service = build('drive', 'v3', credentials=creds)
            logger.info("Google Drive API service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            self.enabled = False
            return False
    
    def is_enabled(self) -> bool:
        """Google Drive連携が有効かどうか"""
        return self.enabled and self.service is not None
    
    def upload_file(self, file_path: str, parent_folder_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """ファイルをGoogle Driveにアップロード"""
        if not self.is_enabled():
            return None
        
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                logger.error(f"File not found: {file_path}")
                return None
            
            # ファイルサイズチェック
            file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                logger.warning(f"File too large: {file_size_mb:.2f}MB > {self.max_file_size_mb}MB")
                return None
            
            # メタデータ設定
            file_metadata = {
                'name': file_path_obj.name,
                'description': f'Research data uploaded from {os.getenv("ENVIRONMENT", "development")} environment'
            }
            
            if parent_folder_id or self.folder_id:
                file_metadata['parents'] = [parent_folder_id or self.folder_id]
            
            # ファイルアップロード
            media = MediaFileUpload(file_path, resumable=True)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,createdTime'
            ).execute()
            
            logger.info(f"File uploaded successfully: {file.get('name')} (ID: {file.get('id')})")
            return file
            
        except Exception as e:
            logger.error(f"Failed to upload file {file_path}: {e}")
            return None
    
    def download_file(self, file_id: str, local_path: str) -> bool:
        """Google Driveからファイルをダウンロード"""
        if not self.is_enabled():
            return False
        
        try:
            # ファイル情報取得
            file_metadata = self.service.files().get(fileId=file_id).execute()
            
            # ダウンロード
            request = self.service.files().get_media(fileId=file_id)
            
            with open(local_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            
            logger.info(f"File downloaded: {file_metadata.get('name')} -> {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            return False
    
    def list_files(self, folder_id: Optional[str] = None, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Google Drive内のファイル一覧を取得"""
        if not self.is_enabled():
            return []
        
        try:
            # クエリ構築
            search_query = []
            if folder_id or self.folder_id:
                search_query.append(f"'{folder_id or self.folder_id}' in parents")
            if query:
                search_query.append(query)
            
            results = self.service.files().list(
                q=' and '.join(search_query) if search_query else None,
                pageSize=100,
                fields="nextPageToken, files(id, name, size, createdTime, modifiedTime, mimeType)"
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Found {len(files)} files in Google Drive")
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    def sync_folder(self, local_folder: str, drive_folder_id: Optional[str] = None) -> Dict[str, int]:
        """ローカルフォルダとGoogle Driveを同期"""
        if not self.is_enabled():
            return {'uploaded': 0, 'downloaded': 0, 'errors': 0}
        
        stats = {'uploaded': 0, 'downloaded': 0, 'errors': 0}
        
        try:
            local_path = Path(local_folder)
            if not local_path.exists():
                logger.error(f"Local folder not found: {local_folder}")
                return stats
            
            # Google Drive内のファイル一覧取得
            drive_files = self.list_files(drive_folder_id)
            drive_file_names = {f['name']: f for f in drive_files}
            
            # ローカルファイルをアップロード
            for file_path in local_path.rglob('*'):
                if file_path.is_file():
                    file_name = file_path.name
                    
                    # Google Driveに存在しない場合はアップロード
                    if file_name not in drive_file_names:
                        if self.upload_file(str(file_path), drive_folder_id):
                            stats['uploaded'] += 1
                        else:
                            stats['errors'] += 1
            
            self.last_sync = datetime.now()
            logger.info(f"Sync completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            stats['errors'] += 1
            return stats
    
    def create_backup(self, backup_name: Optional[str] = None) -> Optional[str]:
        """データベースとファイルのバックアップを作成"""
        if not self.is_enabled() or not self.backup_enabled:
            return None
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = backup_name or f"research_data_backup_{timestamp}"
            
            # バックアップフォルダ作成
            backup_metadata = {
                'name': backup_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'description': f'Research data backup created at {datetime.now().isoformat()}'
            }
            
            if self.folder_id:
                backup_metadata['parents'] = [self.folder_id]
            
            backup_folder = self.service.files().create(body=backup_metadata).execute()
            backup_folder_id = backup_folder.get('id')
            
            # データベースファイルをバックアップ
            db_path = os.getenv('DATABASE_PATH', 'agent/database/research_data.db')
            if os.path.exists(db_path):
                self.upload_file(db_path, backup_folder_id)
            
            # データフォルダをバックアップ
            data_dir = os.getenv('DATA_DIR_PATH', 'data')
            if os.path.exists(data_dir):
                self.sync_folder(data_dir, backup_folder_id)
            
            logger.info(f"Backup created: {backup_name} (ID: {backup_folder_id})")
            return backup_folder_id
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return None
    
    def should_sync(self) -> bool:
        """同期が必要かどうかを判定"""
        if not self.is_enabled() or not self.auto_upload:
            return False
        
        if self.last_sync is None:
            return True
        
        return datetime.now() - self.last_sync > timedelta(seconds=self.sync_interval)
    
    def get_storage_info(self) -> Optional[Dict[str, Any]]:
        """Google Driveストレージ情報を取得"""
        if not self.is_enabled():
            return None
        
        try:
            about = self.service.about().get(fields="storageQuota").execute()
            quota = about.get('storageQuota', {})
            
            return {
                'limit': int(quota.get('limit', 0)),
                'usage': int(quota.get('usage', 0)),
                'usage_in_drive': int(quota.get('usageInDrive', 0)),
                'usage_in_drive_trash': int(quota.get('usageInDriveTrash', 0))
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
            return None

# グローバルインスタンス
google_drive = GoogleDriveIntegration()