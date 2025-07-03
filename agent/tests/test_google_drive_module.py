"""
google_drive_impl.pyモジュールの包括的テスト

このテストモジュールは、GoogleDrivePortImpl実装の詳細なテストを提供します。
Google Drive API不要でモックを使用した包括的テストを実装。

実行方法:
```bash
# 単体テスト実行
uv run pytest agent/tests/test_google_drive_module.py -v

# カバレッジ付き実行
uv run pytest agent/tests/test_google_drive_module.py --cov=agent.source.interfaces.google_drive_impl --cov-report=html -v
```
"""

import asyncio
import tempfile
import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any

# テスト対象のインポート
from agent.source.interfaces.data_models import (
    GoogleDriveConfig,
    IngestionResult,
    JobStatus,
    UserContext,
    DocumentContent,
    DocumentMetadata,
    InputError
)
from agent.source.interfaces.google_drive_impl import (
    GoogleDrivePortImpl,
    create_google_drive_port
)


class TestGoogleDrivePortImplInitialization:
    """GoogleDrivePortImpl初期化テストクラス"""
    
    @pytest.fixture
    def google_drive_config(self):
        """テスト用Google Drive設定"""
        return GoogleDriveConfig(
            credentials_path="/tmp/test_credentials.json",
            max_file_size_mb=50,
            supported_mime_types=[
                'application/pdf',
                'text/csv',
                'application/json',
                'text/plain'
            ],
            sync_interval_minutes=30,
            batch_size=5
        )
    
    def test_initialization_success(self, google_drive_config):
        """正常初期化テスト"""
        port = GoogleDrivePortImpl(google_drive_config)
        
        assert port.config == google_drive_config
        assert port.service is None
        assert port.credentials is None
        assert port.job_registry == {}
        assert port._indexer is None
    
    def test_factory_function_success(self, google_drive_config):
        """ファクトリー関数テスト"""
        port = create_google_drive_port(google_drive_config)
        
        assert isinstance(port, GoogleDrivePortImpl)
        assert port.config == google_drive_config


class TestGoogleDriveAuthentication:
    """Google Drive認証テストクラス"""
    
    @pytest.fixture
    def google_drive_port(self):
        """テスト用GoogleDrivePortImplインスタンス"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        return GoogleDrivePortImpl(config)
    
    @pytest.mark.asyncio
    async def test_authentication_api_unavailable(self, google_drive_port):
        """Google Drive API利用不可時の認証テスト"""
        with patch('agent.source.interfaces.google_drive_impl.GOOGLE_DRIVE_AVAILABLE', False):
            result = await google_drive_port.authenticate({})
            assert result is False
    
    @pytest.mark.asyncio
    async def test_authentication_with_existing_token(self, google_drive_port):
        """既存トークンでの認証テスト"""
        mock_credentials = {
            'token': 'existing_access_token',
            'refresh_token': 'refresh_token',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret'
        }
        
        with patch('agent.source.interfaces.google_drive_impl.GOOGLE_DRIVE_AVAILABLE', True), \
             patch('agent.source.interfaces.google_drive_impl.Credentials') as mock_creds_class, \
             patch('agent.source.interfaces.google_drive_impl.build') as mock_build:
            
            # モック設定
            mock_creds = MagicMock()
            mock_creds.expired = False
            mock_creds_class.from_authorized_user_info.return_value = mock_creds
            
            mock_service = MagicMock()
            mock_about = MagicMock()
            mock_about.get.return_value.execute.return_value = {
                'user': {'emailAddress': 'test@example.com'}
            }
            mock_service.about.return_value = mock_about
            mock_build.return_value = mock_service
            
            # テスト実行
            result = await google_drive_port.authenticate(mock_credentials)
            
            # 結果確認
            assert result is True
            assert google_drive_port.service is not None
            assert google_drive_port.credentials is not None
    
    @pytest.mark.asyncio
    async def test_authentication_with_expired_token(self, google_drive_port):
        """期限切れトークンでの認証テスト"""
        mock_credentials = {
            'token': 'expired_access_token',
            'refresh_token': 'refresh_token'
        }
        
        with patch('agent.source.interfaces.google_drive_impl.GOOGLE_DRIVE_AVAILABLE', True), \
             patch('agent.source.interfaces.google_drive_impl.Credentials') as mock_creds_class, \
             patch('agent.source.interfaces.google_drive_impl.Request') as mock_request, \
             patch('agent.source.interfaces.google_drive_impl.build') as mock_build:
            
            # モック設定
            mock_creds = MagicMock()
            mock_creds.expired = True
            mock_creds.refresh_token = 'refresh_token'
            mock_creds_class.from_authorized_user_info.return_value = mock_creds
            
            mock_service = MagicMock()
            mock_about = MagicMock()
            mock_about.get.return_value.execute.return_value = {
                'user': {'emailAddress': 'test@example.com'}
            }
            mock_service.about.return_value = mock_about
            mock_build.return_value = mock_service
            
            # テスト実行
            result = await google_drive_port.authenticate(mock_credentials)
            
            # 結果確認
            assert result is True
            mock_creds.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_authentication_failure(self, google_drive_port):
        """認証失敗テスト"""
        mock_credentials = {'invalid': 'data'}
        
        with patch('agent.source.interfaces.google_drive_impl.GOOGLE_DRIVE_AVAILABLE', True), \
             patch('agent.source.interfaces.google_drive_impl.Credentials') as mock_creds_class:
            
            # 例外発生をモック
            mock_creds_class.from_authorized_user_info.side_effect = Exception("Authentication failed")
            
            with pytest.raises(InputError) as exc_info:
                await google_drive_port.authenticate(mock_credentials)
            
            assert "Google Drive authentication failed" in str(exc_info.value)
            assert exc_info.value.error_code == "AUTH_FAILED"


class TestGoogleDriveFolderOperations:
    """Google Driveフォルダ操作テストクラス"""
    
    @pytest.fixture
    def authenticated_port(self):
        """認証済みGoogleDrivePortImplインスタンス"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        # モックサービス設定
        mock_service = MagicMock()
        port.service = mock_service
        
        return port
    
    @pytest.mark.asyncio
    async def test_list_folders_success(self, authenticated_port):
        """フォルダ一覧取得成功テスト"""
        # モック設定
        mock_files = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {
            'files': [
                {
                    'id': 'folder_1',
                    'name': 'Test Folder 1',
                    'createdTime': '2024-01-01T00:00:00Z',
                    'modifiedTime': '2024-01-02T00:00:00Z'
                },
                {
                    'id': 'folder_2',
                    'name': 'Test Folder 2',
                    'createdTime': '2024-01-03T00:00:00Z',
                    'modifiedTime': '2024-01-04T00:00:00Z'
                }
            ]
        }
        mock_files.list.return_value = mock_list
        authenticated_port.service.files.return_value = mock_files
        
        # テスト実行
        folders = await authenticated_port.list_folders()
        
        # 結果確認
        assert len(folders) == 2
        assert folders[0]['id'] == 'folder_1'
        assert folders[0]['name'] == 'Test Folder 1'
        assert folders[0]['type'] == 'folder'
        assert folders[1]['id'] == 'folder_2'
        assert folders[1]['name'] == 'Test Folder 2'
    
    @pytest.mark.asyncio
    async def test_list_folders_with_parent(self, authenticated_port):
        """親フォルダ指定でのフォルダ一覧取得テスト"""
        # モック設定
        mock_files = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {'files': []}
        mock_files.list.return_value = mock_list
        authenticated_port.service.files.return_value = mock_files
        
        # テスト実行
        await authenticated_port.list_folders(parent_folder_id='parent_123')
        
        # クエリ確認
        call_args = mock_files.list.call_args
        query = call_args[1]['q']
        assert "'parent_123' in parents" in query
        assert "mimeType='application/vnd.google-apps.folder'" in query
    
    @pytest.mark.asyncio
    async def test_list_folders_not_authenticated(self):
        """未認証状態でのフォルダ一覧取得エラーテスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        with pytest.raises(InputError) as exc_info:
            await port.list_folders()
        
        assert "not authenticated" in str(exc_info.value)
        assert exc_info.value.error_code == "NOT_AUTHENTICATED"


class TestGoogleDriveFileOperations:
    """Google Driveファイル操作テストクラス"""
    
    @pytest.fixture
    def authenticated_port(self):
        """認証済みGoogleDrivePortImplインスタンス"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        mock_service = MagicMock()
        port.service = mock_service
        
        return port
    
    @pytest.mark.asyncio
    async def test_get_file_metadata_success(self, authenticated_port):
        """ファイルメタデータ取得成功テスト"""
        # モック設定
        mock_files = MagicMock()
        mock_get = MagicMock()
        mock_get.execute.return_value = {
            'id': 'file_123',
            'name': 'test_document.pdf',
            'size': '1024000',
            'mimeType': 'application/pdf',
            'createdTime': '2024-01-01T00:00:00Z',
            'modifiedTime': '2024-01-02T00:00:00Z',
            'parents': ['folder_456']
        }
        mock_files.get.return_value = mock_get
        authenticated_port.service.files.return_value = mock_files
        
        # テスト実行
        metadata = await authenticated_port.get_file_metadata('file_123')
        
        # 結果確認
        assert metadata['id'] == 'file_123'
        assert metadata['name'] == 'test_document.pdf'
        assert metadata['size'] == 1024000
        assert metadata['mimeType'] == 'application/pdf'
        assert metadata['parents'] == ['folder_456']
    
    @pytest.mark.asyncio
    async def test_download_file_success(self, authenticated_port):
        """ファイルダウンロード成功テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "downloaded_file.pdf"
            
            # モック設定
            mock_files = MagicMock()
            
            # ファイルメタデータ取得のモック
            mock_get = MagicMock()
            mock_get.execute.return_value = {
                'id': 'file_123',
                'name': 'test_document.pdf',
                'mimeType': 'application/pdf',
                'createdTime': '2024-01-01T00:00:00Z',
                'modifiedTime': '2024-01-02T00:00:00Z'
            }
            
            # ファイルダウンロードのモック
            mock_get_media = MagicMock()
            
            mock_files.get.return_value = mock_get
            mock_files.get_media.return_value = mock_get_media
            authenticated_port.service.files.return_value = mock_files
            
            # MediaIoBaseDownloadのモック
            with patch('agent.source.interfaces.google_drive_impl.MediaIoBaseDownload') as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.next_chunk.side_effect = [
                    (MagicMock(resumable_progress=50), False),
                    (MagicMock(resumable_progress=100), True)
                ]
                mock_downloader_class.return_value = mock_downloader
                
                # テスト用ファイル作成
                target_path.write_text("test content")
                
                # テスト実行
                document_content = await authenticated_port.download_file('file_123', target_path)
                
                # 結果確認
                assert isinstance(document_content, DocumentContent)
                assert document_content.file_path == str(target_path)
                assert document_content.content_type == 'pdf'
                assert document_content.file_size > 0
                assert len(document_content.content_hash) == 64  # SHA256ハッシュ
                assert document_content.metadata['google_drive_id'] == 'file_123'
                assert document_content.metadata['original_name'] == 'test_document.pdf'


class TestGoogleDriveFolderSync:
    """Google Driveフォルダ同期テストクラス"""
    
    @pytest.fixture
    def authenticated_port(self):
        """認証済みGoogleDrivePortImplインスタンス"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        mock_service = MagicMock()
        port.service = mock_service
        
        return port
    
    @pytest.mark.asyncio
    async def test_sync_folder_success(self, authenticated_port):
        """フォルダ同期成功テスト"""
        job_id = "test_sync_job_123"
        folder_id = "test_folder_456"
        
        # モック設定
        with patch.object(authenticated_port, '_list_files_in_folder') as mock_list_files, \
             patch.object(authenticated_port, '_process_single_file') as mock_process_file:
            
            # ファイル一覧のモック
            mock_list_files.return_value = [
                {
                    'id': 'file_1',
                    'name': 'test.pdf',
                    'size': '1024',
                    'mimeType': 'application/pdf'
                },
                {
                    'id': 'file_2',
                    'name': 'data.csv',
                    'size': '2048',
                    'mimeType': 'text/csv'
                }
            ]
            
            # ファイル処理成功のモック
            mock_process_file.return_value = None
            
            # テスト実行
            result = await authenticated_port.sync_folder(folder_id, job_id)
            
            # 結果確認
            assert isinstance(result, IngestionResult)
            assert result.job_id == job_id
            assert result.status == JobStatus.COMPLETED
            assert result.total_files == 2
            assert result.successful_files == 2
            assert result.failed_files == 0
            assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_sync_folder_with_unsupported_files(self, authenticated_port):
        """サポートされていないファイルを含むフォルダ同期テスト"""
        job_id = "test_sync_job_123"
        folder_id = "test_folder_456"
        
        with patch.object(authenticated_port, '_list_files_in_folder') as mock_list_files:
            # ファイル一覧のモック（サポート対象外ファイル含む）
            mock_list_files.return_value = [
                {
                    'id': 'file_1',
                    'name': 'test.pdf',
                    'size': '1024',
                    'mimeType': 'application/pdf'  # サポート対象
                },
                {
                    'id': 'file_2',
                    'name': 'image.jpg',
                    'size': '2048', 
                    'mimeType': 'image/jpeg'  # サポート対象外
                }
            ]
            
            # テスト実行
            result = await authenticated_port.sync_folder(folder_id, job_id)
            
            # 結果確認（サポート対象ファイルのみ処理）
            assert result.total_files == 1  # PDFのみ
    
    @pytest.mark.asyncio
    async def test_sync_folder_not_authenticated(self):
        """未認証状態でのフォルダ同期エラーテスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        with pytest.raises(InputError) as exc_info:
            await port.sync_folder("folder_id", "job_id")
        
        assert "not authenticated" in str(exc_info.value)
        assert exc_info.value.error_code == "NOT_AUTHENTICATED"


class TestGoogleDriveHelperMethods:
    """Google Driveヘルパーメソッドテストクラス"""
    
    @pytest.fixture
    def google_drive_port(self):
        """テスト用GoogleDrivePortImplインスタンス"""
        config = GoogleDriveConfig(
            credentials_path="/tmp/test.json",
            supported_mime_types=[
                'application/pdf',
                'text/csv',
                'application/json'
            ]
        )
        return GoogleDrivePortImpl(config)
    
    def test_is_supported_mime_type(self, google_drive_port):
        """サポート対象ファイル形式チェックテスト"""
        # サポート対象
        assert google_drive_port._is_supported_mime_type('application/pdf') is True
        assert google_drive_port._is_supported_mime_type('text/csv') is True
        assert google_drive_port._is_supported_mime_type('application/json') is True
        
        # 非サポート対象
        assert google_drive_port._is_supported_mime_type('image/jpeg') is False
        assert google_drive_port._is_supported_mime_type('video/mp4') is False
        assert google_drive_port._is_supported_mime_type('application/unknown') is False
    
    def test_get_content_type_from_mime(self, google_drive_port):
        """MIMEタイプからコンテンツタイプ変換テスト"""
        assert google_drive_port._get_content_type_from_mime('application/pdf') == 'pdf'
        assert google_drive_port._get_content_type_from_mime('text/csv') == 'csv'
        assert google_drive_port._get_content_type_from_mime('application/json') == 'json'
        assert google_drive_port._get_content_type_from_mime('text/plain') == 'txt'
        assert google_drive_port._get_content_type_from_mime('unknown/type') == 'unknown'
    
    def test_determine_category(self, google_drive_port):
        """ファイル名からカテゴリ判定テスト"""
        # データセット
        assert google_drive_port._determine_category('data.csv') == 'dataset'
        assert google_drive_port._determine_category('dataset_sample.json') == 'dataset'
        assert google_drive_port._determine_category('research_data.jsonl') == 'dataset'
        
        # 論文
        assert google_drive_port._determine_category('research_paper.pdf') == 'paper'
        assert google_drive_port._determine_category('thesis_document.pdf') == 'paper'
        
        # ポスター
        assert google_drive_port._determine_category('conference_poster.pdf') == 'poster'
        assert google_drive_port._determine_category('presentation_slides.pdf') == 'poster'
        
        # デフォルト（PDF）
        assert google_drive_port._determine_category('unknown.pdf') == 'paper'
    
    def test_calculate_file_hash(self, google_drive_port):
        """ファイルハッシュ計算テスト"""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp_file:
            tmp_file.write("Test content for hash calculation")
            tmp_file.flush()
            
            hash_value = google_drive_port._calculate_file_hash(Path(tmp_file.name))
            
            # SHA256ハッシュ値の検証（64文字の16進数）
            assert len(hash_value) == 64
            assert all(c in '0123456789abcdef' for c in hash_value)
            
            # 同じ内容であれば同じハッシュ値
            hash_value2 = google_drive_port._calculate_file_hash(Path(tmp_file.name))
            assert hash_value == hash_value2
            
            # クリーンアップ
            Path(tmp_file.name).unlink()


class TestGoogleDriveJobManagement:
    """Google Driveジョブ管理テストクラス"""
    
    @pytest.fixture
    def google_drive_port(self):
        """テスト用GoogleDrivePortImplインスタンス"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        return GoogleDrivePortImpl(config)
    
    @pytest.mark.asyncio
    async def test_job_status_management(self, google_drive_port):
        """ジョブ状況管理テスト"""
        job_id = "test_job_123"
        
        # 初期状態：ジョブ不存在
        status = await google_drive_port.get_job_status(job_id)
        assert status is None
        
        # ジョブ登録
        result = IngestionResult(
            job_id=job_id,
            status=JobStatus.RUNNING,
            total_files=10,
            processed_files=5,
            successful_files=3,
            failed_files=2,
            start_time=datetime.now()
        )
        google_drive_port.job_registry[job_id] = result
        
        # ジョブ状況取得
        status = await google_drive_port.get_job_status(job_id)
        assert status is not None
        assert status.job_id == job_id
        assert status.status == JobStatus.RUNNING
        assert status.progress_percentage == 50.0  # 5/10 * 100
    
    @pytest.mark.asyncio
    async def test_job_cancellation(self, google_drive_port):
        """ジョブキャンセルテスト"""
        job_id = "test_job_123"
        
        # 実行中ジョブを登録
        result = IngestionResult(
            job_id=job_id,
            status=JobStatus.RUNNING,
            total_files=10,
            processed_files=3,
            successful_files=2,
            failed_files=1,
            start_time=datetime.now()
        )
        google_drive_port.job_registry[job_id] = result
        
        # ジョブキャンセル
        cancel_result = await google_drive_port.cancel_job(job_id)
        assert cancel_result is True
        assert google_drive_port.job_registry[job_id].status == JobStatus.CANCELLED
        assert google_drive_port.job_registry[job_id].end_time is not None
    
    @pytest.mark.asyncio
    async def test_job_cancellation_completed_job(self, google_drive_port):
        """完了済みジョブのキャンセル（失敗）テスト"""
        job_id = "test_job_123"
        
        # 完了済みジョブを登録
        result = IngestionResult(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            total_files=10,
            processed_files=10,
            successful_files=10,
            failed_files=0,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        google_drive_port.job_registry[job_id] = result
        
        # ジョブキャンセル（失敗）
        cancel_result = await google_drive_port.cancel_job(job_id)
        assert cancel_result is False
        assert google_drive_port.job_registry[job_id].status == JobStatus.COMPLETED


class TestGoogleDriveIntegrationWithExistingSystem:
    """既存システム統合テストクラス"""
    
    @pytest.fixture
    def google_drive_port(self):
        """テスト用GoogleDrivePortImplインスタンス"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        return GoogleDrivePortImpl(config)
    
    @pytest.mark.asyncio
    async def test_integrate_with_existing_system_success(self, google_drive_port):
        """既存システム統合成功テスト"""
        test_file_path = "/tmp/test_document.pdf"
        
        mock_content = DocumentContent(
            file_path=test_file_path,
            raw_content="",
            content_type="pdf",
            file_size=1024,
            content_hash="test_hash_123",
            metadata={
                'original_name': 'research_paper.pdf',
                'mime_type': 'application/pdf',
                'google_drive_id': 'file_123'
            }
        )
        
        # integrate_with_existing_indexer関数をモック
        with patch('agent.source.interfaces.google_drive_impl.integrate_with_existing_indexer') as mock_integrate:
            mock_integrate.return_value = True
            
            # 統合テスト実行
            result = await google_drive_port._integrate_with_existing_system(
                test_file_path, mock_content
            )
            
            # 結果確認
            assert result is True
            mock_integrate.assert_called_once_with(
                file_path=test_file_path,
                category='paper',  # PDFはpaperと判定される
                target_name='research_paper.pdf'
            )
    
    @pytest.mark.asyncio
    async def test_integrate_with_existing_system_csv_file(self, google_drive_port):
        """CSVファイルの既存システム統合テスト"""
        test_file_path = "/tmp/test_data.csv"
        
        mock_content = DocumentContent(
            file_path=test_file_path,
            raw_content="",
            content_type="csv",
            file_size=2048,
            content_hash="test_hash_456",
            metadata={
                'original_name': 'sample_dataset.csv',
                'mime_type': 'text/csv',
                'google_drive_id': 'file_456'
            }
        )
        
        with patch('agent.source.interfaces.google_drive_impl.integrate_with_existing_indexer') as mock_integrate:
            mock_integrate.return_value = True
            
            result = await google_drive_port._integrate_with_existing_system(
                test_file_path, mock_content
            )
            
            assert result is True
            mock_integrate.assert_called_once_with(
                file_path=test_file_path,
                category='dataset',  # CSVはdatasetと判定される
                target_name='sample_dataset.csv'
            )
    
    @pytest.mark.asyncio
    async def test_integrate_with_existing_system_failure(self, google_drive_port):
        """既存システム統合失敗テスト"""
        test_file_path = "/tmp/test_document.pdf"
        
        mock_content = DocumentContent(
            file_path=test_file_path,
            raw_content="",
            content_type="pdf",
            file_size=1024,
            content_hash="test_hash_123",
            metadata={'original_name': 'test.pdf'}
        )
        
        with patch('agent.source.interfaces.google_drive_impl.integrate_with_existing_indexer') as mock_integrate:
            mock_integrate.side_effect = Exception("Integration failed")
            
            result = await google_drive_port._integrate_with_existing_system(
                test_file_path, mock_content
            )
            
            assert result is False


class TestGoogleDriveErrorHandling:
    """Google Driveエラーハンドリングテストクラス"""
    
    @pytest.fixture
    def google_drive_port(self):
        """テスト用GoogleDrivePortImplインスタンス"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        return GoogleDrivePortImpl(config)
    
    @pytest.mark.asyncio
    async def test_download_file_not_authenticated(self, google_drive_port):
        """未認証状態でのファイルダウンロードエラーテスト"""
        with pytest.raises(InputError) as exc_info:
            await google_drive_port.download_file("file_id", Path("/tmp/test.pdf"))
        
        assert "not authenticated" in str(exc_info.value)
        assert exc_info.value.error_code == "NOT_AUTHENTICATED"
    
    @pytest.mark.asyncio
    async def test_get_file_metadata_api_error(self):
        """API エラー時のファイルメタデータ取得テスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        # Mock service with API error
        mock_service = MagicMock()
        mock_files = MagicMock()
        
        # HttpError をモック
        with patch('agent.source.interfaces.google_drive_impl.HttpError', Exception):
            mock_files.get.side_effect = Exception("API Error")
            mock_service.files.return_value = mock_files
            port.service = mock_service
            
            with pytest.raises(InputError) as exc_info:
                await port.get_file_metadata("file_id")
            
            assert "Failed to get file metadata" in str(exc_info.value)
            assert exc_info.value.error_code == "API_ERROR"


if __name__ == "__main__":
    """スタンドアロンテスト実行"""
    print("=== google_drive_impl.py モジュールテスト実行 ===")
    
    # テスト実行
    import subprocess
    import sys
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            __file__, 
            '-v', 
            '--tb=short'
        ], cwd=Path(__file__).parent.parent.parent, capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        print(f"\nテスト結果: {'SUCCESS' if result.returncode == 0 else 'FAILED'}")
        sys.exit(result.returncode)
        
    except Exception as e:
        print(f"テスト実行エラー: {e}")
        sys.exit(1)