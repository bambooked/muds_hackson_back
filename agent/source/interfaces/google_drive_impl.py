"""
Google Drive連携の具体的実装

このモジュールは、GoogleDrivePortインターフェースの具体的実装を提供します。
Google Drive API v3を使用してファイル・フォルダの操作を行い、
既存NewFileIndexerシステムとシームレスに統合します。

Claude Code実装ガイダンス：
- 非破壊的拡張：既存システム無変更
- エラー時フォールバック：既存システム継続
- 非同期処理：パフォーマンス最適化
- 設定制御：機能ON/OFF可能

必要パッケージ：
- google-api-python-client
- google-auth-oauthlib
- google-auth
"""

import asyncio
import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

# Google Drive API imports (認証設定後に有効化)
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseDownload
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logging.warning("Google Drive API libraries not available. Install: pip install google-api-python-client google-auth-oauthlib")

from .input_ports import GoogleDrivePort
from .data_models import (
    DocumentContent,
    DocumentMetadata,
    IngestionResult,
    UserContext,
    JobStatus,
    GoogleDriveConfig,
    InputError
)


class GoogleDrivePortImpl(GoogleDrivePort):
    """
    Google Drive連携の具体的実装クラス
    
    主要機能：
    1. OAuth2認証による安全なAPI接続
    2. フォルダ・ファイル一覧取得
    3. ファイルダウンロードと一時保存
    4. 既存NewFileIndexerとの統合
    5. プログレス追跡とエラーハンドリング
    """
    
    def __init__(self, config: GoogleDriveConfig):
        """
        初期化
        
        Args:
            config: Google Drive設定
        """
        self.config = config
        self.service = None
        self.credentials = None
        self.job_registry: Dict[str, IngestionResult] = {}
        
        # 既存システムとの統合用
        self._indexer = None
        
        if not GOOGLE_DRIVE_AVAILABLE:
            logging.warning("Google Drive API not available - running in mock mode")
    
    async def authenticate(
        self, 
        credentials: Dict[str, Any],
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        Google Drive認証実装
        
        Args:
            credentials: OAuth2認証情報
            user_context: ユーザーコンテキスト
            
        Returns:
            bool: 認証成功可否
        """
        if not GOOGLE_DRIVE_AVAILABLE:
            logging.warning("Google Drive API not available - authentication skipped")
            return False
            
        try:
            # OAuth2フロー実装
            if 'token' in credentials:
                # 既存トークンを使用
                self.credentials = Credentials.from_authorized_user_info(
                    credentials, self.config.scopes
                )
            else:
                # 新規認証フロー
                flow = Flow.from_client_config(
                    credentials['client_config'],
                    scopes=self.config.scopes
                )
                flow.redirect_uri = credentials.get('redirect_uri', 'urn:ietf:wg:oauth:2.0:oob')
                
                # 認証URL生成（実際の認証はユーザーが実行）
                auth_url, _ = flow.authorization_url(prompt='consent')
                logging.info(f"Authentication URL: {auth_url}")
                
                # 仮実装：開発時は事前設定済みトークンを使用
                if 'access_token' in credentials:
                    self.credentials = Credentials(
                        token=credentials['access_token'],
                        refresh_token=credentials.get('refresh_token'),
                        token_uri='https://oauth2.googleapis.com/token',
                        client_id=credentials.get('client_id'),
                        client_secret=credentials.get('client_secret'),
                        scopes=self.config.scopes
                    )
            
            # トークン更新チェック
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            
            # Google Drive APIサービス構築
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            # 接続テスト
            test_result = self.service.about().get(fields='user').execute()
            logging.info(f"Google Drive authentication successful for: {test_result.get('user', {}).get('emailAddress', 'Unknown')}")
            
            return True
            
        except Exception as e:
            logging.error(f"Google Drive authentication failed: {e}")
            raise InputError(f"Google Drive authentication failed: {e}", "AUTH_FAILED")
    
    async def list_folders(
        self,
        parent_folder_id: Optional[str] = None,
        user_context: Optional[UserContext] = None
    ) -> List[Dict[str, Any]]:
        """
        フォルダ一覧取得実装
        
        Args:
            parent_folder_id: 親フォルダID（Noneの場合はルート）
            user_context: ユーザーコンテキスト
            
        Returns:
            List[Dict]: フォルダ情報一覧
        """
        if not self.service:
            raise InputError("Google Drive not authenticated", "NOT_AUTHENTICATED")
        
        try:
            # クエリ構築
            query = "mimeType='application/vnd.google-apps.folder'"
            if parent_folder_id:
                query += f" and '{parent_folder_id}' in parents"
            else:
                query += " and 'root' in parents"
            
            # フォルダ一覧取得
            results = self.service.files().list(
                q=query,
                fields='nextPageToken, files(id, name, createdTime, modifiedTime, parents)'
            ).execute()
            
            folders = []
            for item in results.get('files', []):
                folders.append({
                    'id': item['id'],
                    'name': item['name'],
                    'type': 'folder',
                    'created_time': item.get('createdTime'),
                    'modified_time': item.get('modifiedTime'),
                    'parent_id': parent_folder_id
                })
            
            logging.info(f"Found {len(folders)} folders in parent: {parent_folder_id or 'root'}")
            return folders
            
        except HttpError as e:
            logging.error(f"Failed to list folders: {e}")
            raise InputError(f"Failed to list folders: {e}", "API_ERROR")
    
    async def sync_folder(
        self,
        folder_id: str,
        job_id: str,
        user_context: Optional[UserContext] = None,
        recursive: bool = True
    ) -> IngestionResult:
        """
        フォルダ同期実装
        
        重要：既存NewFileIndexerとの統合を実現
        
        Args:
            folder_id: Google DriveフォルダID
            job_id: ジョブ追跡用ID
            user_context: ユーザーコンテキスト
            recursive: サブフォルダも同期するか
            
        Returns:
            IngestionResult: 同期結果
        """
        if not self.service:
            raise InputError("Google Drive not authenticated", "NOT_AUTHENTICATED")
        
        # ジョブ初期化
        result = IngestionResult(
            job_id=job_id,
            status=JobStatus.RUNNING,
            total_files=0,
            processed_files=0,
            successful_files=0,
            failed_files=0,
            start_time=datetime.now(),
            metadata={'folder_id': folder_id, 'recursive': recursive}
        )
        self.job_registry[job_id] = result
        
        try:
            # 1. フォルダ内ファイル一覧取得
            files = await self._list_files_in_folder(folder_id, recursive)
            result.total_files = len(files)
            
            logging.info(f"Found {len(files)} files in folder {folder_id}")
            
            # 2. サポート形式でフィルタリング
            supported_files = []
            for file_info in files:
                if self._is_supported_mime_type(file_info.get('mimeType', '')):
                    supported_files.append(file_info)
                else:
                    logging.info(f"Skipping unsupported file: {file_info['name']} ({file_info.get('mimeType', 'unknown')})")
            
            result.total_files = len(supported_files)
            logging.info(f"Processing {len(supported_files)} supported files")
            
            # 3. 各ファイルをダウンロード・処理
            for file_info in supported_files:
                try:
                    await self._process_single_file(file_info, result, user_context)
                    result.successful_files += 1
                except Exception as e:
                    error_msg = f"Failed to process {file_info['name']}: {e}"
                    result.errors.append(error_msg)
                    result.failed_files += 1
                    logging.error(error_msg)
                finally:
                    result.processed_files += 1
                    # プログレス更新
                    self.job_registry[job_id] = result
            
            # ジョブ完了
            result.status = JobStatus.COMPLETED
            result.end_time = datetime.now()
            
            logging.info(f"Folder sync completed: {result.successful_files}/{result.total_files} files processed successfully")
            return result
            
        except Exception as e:
            result.status = JobStatus.FAILED
            result.end_time = datetime.now()
            result.errors.append(f"Folder sync failed: {e}")
            logging.error(f"Folder sync failed: {e}")
            raise InputError(f"Folder sync failed: {e}", "SYNC_FAILED")
    
    async def download_file(
        self,
        file_id: str,
        target_path: Path,
        user_context: Optional[UserContext] = None
    ) -> DocumentContent:
        """
        ファイルダウンロード実装
        
        Args:
            file_id: Google DriveファイルID
            target_path: 保存先パス
            user_context: ユーザーコンテキスト
            
        Returns:
            DocumentContent: ダウンロードしたファイル情報
        """
        if not self.service:
            raise InputError("Google Drive not authenticated", "NOT_AUTHENTICATED")
        
        try:
            # ファイルメタデータ取得
            file_metadata = self.service.files().get(fileId=file_id).execute()
            
            # ファイルダウンロード
            request = self.service.files().get_media(fileId=file_id)
            
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target_path, 'wb') as file_handle:
                downloader = MediaIoBaseDownload(file_handle, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            
            # ファイル情報読み取り
            file_size = target_path.stat().st_size
            
            # コンテンツハッシュ計算
            content_hash = self._calculate_file_hash(target_path)
            
            # DocumentContent作成
            document_content = DocumentContent(
                file_path=str(target_path),
                raw_content="",  # バイナリファイルのため空
                content_type=self._get_content_type_from_mime(file_metadata.get('mimeType', '')),
                file_size=file_size,
                content_hash=content_hash,
                metadata={
                    'google_drive_id': file_id,
                    'original_name': file_metadata.get('name'),
                    'mime_type': file_metadata.get('mimeType'),
                    'created_time': file_metadata.get('createdTime'),
                    'modified_time': file_metadata.get('modifiedTime')
                }
            )
            
            logging.info(f"Downloaded file: {file_metadata.get('name')} -> {target_path}")
            return document_content
            
        except HttpError as e:
            logging.error(f"Failed to download file {file_id}: {e}")
            raise InputError(f"Failed to download file: {e}", "DOWNLOAD_FAILED")
    
    async def get_file_metadata(
        self,
        file_id: str,
        user_context: Optional[UserContext] = None
    ) -> Dict[str, Any]:
        """
        ファイルメタデータ取得実装
        
        Args:
            file_id: Google DriveファイルID
            user_context: ユーザーコンテキスト
            
        Returns:
            Dict: ファイルメタデータ
        """
        if not self.service:
            raise InputError("Google Drive not authenticated", "NOT_AUTHENTICATED")
        
        try:
            file_metadata = self.service.files().get(
                fileId=file_id,
                fields='id, name, size, mimeType, createdTime, modifiedTime, parents'
            ).execute()
            
            return {
                'id': file_metadata['id'],
                'name': file_metadata['name'],
                'size': int(file_metadata.get('size', 0)),
                'mimeType': file_metadata.get('mimeType'),
                'createdTime': file_metadata.get('createdTime'),
                'modifiedTime': file_metadata.get('modifiedTime'),
                'parents': file_metadata.get('parents', [])
            }
            
        except HttpError as e:
            logging.error(f"Failed to get file metadata {file_id}: {e}")
            raise InputError(f"Failed to get file metadata: {e}", "API_ERROR")
    
    # ========================================
    # Helper Methods
    # ========================================
    
    async def _list_files_in_folder(
        self, 
        folder_id: str, 
        recursive: bool = True
    ) -> List[Dict[str, Any]]:
        """フォルダ内ファイル一覧取得（再帰対応）"""
        files = []
        
        # 直下のファイル取得
        query = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder'"
        results = self.service.files().list(
            q=query,
            fields='nextPageToken, files(id, name, size, mimeType, createdTime, modifiedTime, parents)'
        ).execute()
        
        files.extend(results.get('files', []))
        
        # 再帰処理
        if recursive:
            # サブフォルダ取得
            subfolders = await self.list_folders(folder_id)
            for subfolder in subfolders:
                subfolder_files = await self._list_files_in_folder(subfolder['id'], recursive)
                files.extend(subfolder_files)
        
        return files
    
    def _is_supported_mime_type(self, mime_type: str) -> bool:
        """サポート対象ファイル形式チェック"""
        return mime_type in self.config.supported_mime_types
    
    def _get_content_type_from_mime(self, mime_type: str) -> str:
        """MIMEタイプからコンテンツタイプ変換"""
        mime_mapping = {
            'application/pdf': 'pdf',
            'text/csv': 'csv',
            'application/json': 'json',
            'text/plain': 'txt',
            'application/jsonl': 'jsonl'
        }
        return mime_mapping.get(mime_type, 'unknown')
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """ファイルハッシュ計算"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    async def _process_single_file(
        self,
        file_info: Dict[str, Any],
        result: IngestionResult,
        user_context: Optional[UserContext] = None
    ) -> None:
        """単一ファイルの処理（ダウンロード + 既存システム統合）"""
        file_id = file_info['id']
        file_name = file_info['name']
        
        # 一時ファイルパス生成
        temp_dir = Path(f"/tmp/paas_temp/{result.job_id}")
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file_path = temp_dir / file_name
        
        try:
            # 1. ファイルダウンロード
            document_content = await self.download_file(file_id, temp_file_path, user_context)
            
            # 2. 既存システムとの統合
            success = await self._integrate_with_existing_system(
                str(temp_file_path),
                document_content,
                user_context
            )
            
            if success:
                # DocumentMetadata作成
                doc_metadata = DocumentMetadata(
                    id=0,  # 既存システムで設定される
                    category=self._determine_category(file_name),
                    file_path=str(temp_file_path),
                    file_name=file_name,
                    file_size=document_content.file_size,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    content_hash=document_content.content_hash,
                    source_type='google_drive',
                    external_id=file_id
                )
                result.processed_documents.append(doc_metadata)
                
                logging.info(f"Successfully processed: {file_name}")
            else:
                raise Exception("Failed to integrate with existing system")
                
        finally:
            # 一時ファイル削除
            if temp_file_path.exists():
                temp_file_path.unlink()
    
    async def _integrate_with_existing_system(
        self,
        file_path: str,
        document_content: DocumentContent,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """既存NewFileIndexerシステムとの統合"""
        try:
            # 統合ヘルパー関数を使用（input_ports.pyで定義済み）
            from .input_ports import integrate_with_existing_indexer
            
            # カテゴリ判定（メタデータから）
            category = None
            original_name = document_content.metadata.get('original_name', document_content.file_path)
            
            # Google Driveメタデータから詳細カテゴリ判定
            mime_type = document_content.metadata.get('mime_type', '')
            if mime_type in ['text/csv', 'application/json']:
                category = 'dataset'
            elif mime_type == 'application/pdf':
                # ファイル名でより詳細に判定
                category = self._determine_category(original_name)
            
            # 統合実行
            success = await integrate_with_existing_indexer(
                file_path=file_path,
                category=category,
                target_name=original_name
            )
            
            if success:
                logging.info(f"Successfully integrated with existing system: {original_name} -> {category}")
                return True
            else:
                logging.error(f"Failed to integrate with existing system: {original_name}")
                return False
            
        except Exception as e:
            logging.error(f"Failed to integrate with existing system: {e}")
            return False
    
    def _determine_category(self, file_name: str) -> str:
        """ファイル名からカテゴリ判定"""
        file_name_lower = file_name.lower()
        
        if any(keyword in file_name_lower for keyword in ['dataset', 'data', '.csv', '.json', '.jsonl']):
            return 'dataset'
        elif any(keyword in file_name_lower for keyword in ['paper', 'thesis', 'research']):
            return 'paper'
        elif any(keyword in file_name_lower for keyword in ['poster', 'presentation']):
            return 'poster'
        else:
            # デフォルトはファイル拡張子で判定
            if file_name_lower.endswith('.pdf'):
                return 'paper'  # PDFは論文として扱う
            else:
                return 'dataset'
    
    # ========================================
    # Job Management Methods
    # ========================================
    
    async def get_job_status(self, job_id: str) -> Optional[IngestionResult]:
        """ジョブ状況取得"""
        return self.job_registry.get(job_id)
    
    async def cancel_job(self, job_id: str) -> bool:
        """ジョブキャンセル"""
        if job_id in self.job_registry:
            result = self.job_registry[job_id]
            if result.status == JobStatus.RUNNING:
                result.status = JobStatus.CANCELLED
                result.end_time = datetime.now()
                return True
        return False


# ========================================
# Factory Function
# ========================================

def create_google_drive_port(config: GoogleDriveConfig) -> GoogleDrivePortImpl:
    """
    GoogleDrivePort実装インスタンス作成
    
    Claude Code使用例：
    ```python
    from .data_models import GoogleDriveConfig
    from .google_drive_impl import create_google_drive_port
    
    config = GoogleDriveConfig(
        credentials_path="/path/to/credentials.json",
        max_file_size_mb=100
    )
    
    google_drive_port = create_google_drive_port(config)
    await google_drive_port.authenticate(credentials_dict)
    
    result = await google_drive_port.sync_folder("folder_id", "job_123")
    ```
    """
    return GoogleDrivePortImpl(config)