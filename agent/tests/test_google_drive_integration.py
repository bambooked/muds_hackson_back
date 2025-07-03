"""
Google Drive統合テスト

このテストモジュールは、GoogleDrivePortImpl実装と既存システムとの統合を検証します。
モック使用により、Google Drive API認証なしでテスト実行可能です。

Claude Code実装ガイダンス：
- モック使用で外部API依存を排除
- 既存システムとの統合ポイントを重点テスト
- エラーハンドリングとフォールバック機能確認
- 非破壊的拡張の保証

テスト実行：
```bash
uv run pytest agent/tests/test_google_drive_integration.py -v
```
"""

import asyncio
import tempfile
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any

# テスト対象のインポート
from agent.source.interfaces.data_models import (
    GoogleDriveConfig,
    IngestionResult,
    JobStatus,
    UserContext,
    DocumentContent,
    DocumentMetadata
)
from agent.source.interfaces.google_drive_impl import GoogleDrivePortImpl, create_google_drive_port


class TestGoogleDrivePortImpl:
    """GoogleDrivePortImpl実装テストクラス"""
    
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
    
    @pytest.fixture
    def mock_user_context(self):
        """テスト用ユーザーコンテキスト"""
        return UserContext(
            user_id="test_user_123",
            email="test@university.ac.jp",
            display_name="Test User",
            domain="university.ac.jp",
            roles=["student"],
            permissions={"documents": ["read", "write"]}
        )
    
    @pytest.fixture
    def google_drive_port(self, google_drive_config):
        """テスト用GoogleDrivePortImplインスタンス"""
        return GoogleDrivePortImpl(google_drive_config)
    
    def test_initialization(self, google_drive_port, google_drive_config):
        """初期化テスト"""
        assert google_drive_port.config == google_drive_config
        assert google_drive_port.service is None
        assert google_drive_port.credentials is None
        assert google_drive_port.job_registry == {}
    
    def test_factory_function(self, google_drive_config):
        """ファクトリー関数テスト"""
        port = create_google_drive_port(google_drive_config)
        assert isinstance(port, GoogleDrivePortImpl)
        assert port.config == google_drive_config
    
    @pytest.mark.asyncio
    async def test_authentication_success(self, google_drive_port):
        """認証成功テスト（モック使用）"""
        mock_credentials = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret'
        }
        
        with patch('agent.source.interfaces.google_drive_impl.GOOGLE_DRIVE_AVAILABLE', True), \
             patch('agent.source.interfaces.google_drive_impl.Credentials') as mock_creds, \
             patch('agent.source.interfaces.google_drive_impl.build') as mock_build:
            
            # モック設定
            mock_service = MagicMock()
            mock_about = MagicMock()
            mock_about.get.return_value.execute.return_value = {
                'user': {'emailAddress': 'test@example.com'}
            }
            mock_service.about.return_value = mock_about
            mock_build.return_value = mock_service
            
            # 認証実行
            result = await google_drive_port.authenticate(mock_credentials)
            
            # 結果確認
            assert result is True
            assert google_drive_port.service is not None
    
    @pytest.mark.asyncio
    async def test_authentication_api_unavailable(self, google_drive_port):
        """Google Drive API利用不可時の認証テスト"""
        mock_credentials = {'access_token': 'test_token'}
        
        with patch('agent.source.interfaces.google_drive_impl.GOOGLE_DRIVE_AVAILABLE', False):
            result = await google_drive_port.authenticate(mock_credentials)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_list_folders_success(self, google_drive_port):
        """フォルダ一覧取得成功テスト"""
        # Mock service setup
        mock_service = MagicMock()
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
        mock_service.files.return_value = mock_files
        google_drive_port.service = mock_service
        
        # テスト実行
        folders = await google_drive_port.list_folders()
        
        # 結果確認
        assert len(folders) == 2
        assert folders[0]['id'] == 'folder_1'
        assert folders[0]['name'] == 'Test Folder 1'
        assert folders[0]['type'] == 'folder'
        assert folders[1]['id'] == 'folder_2'
        assert folders[1]['name'] == 'Test Folder 2'
    
    @pytest.mark.asyncio
    async def test_get_file_metadata_success(self, google_drive_port):
        """ファイルメタデータ取得成功テスト"""
        # Mock service setup
        mock_service = MagicMock()
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
        mock_service.files.return_value = mock_files
        google_drive_port.service = mock_service
        
        # テスト実行
        metadata = await google_drive_port.get_file_metadata('file_123')
        
        # 結果確認
        assert metadata['id'] == 'file_123'
        assert metadata['name'] == 'test_document.pdf'
        assert metadata['size'] == 1024000
        assert metadata['mimeType'] == 'application/pdf'
        assert metadata['parents'] == ['folder_456']
    
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
    
    @pytest.mark.asyncio
    async def test_job_management(self, google_drive_port):
        """ジョブ管理機能テスト"""
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
        assert status.total_files == 10
        assert status.processed_files == 5
        
        # ジョブキャンセル
        cancel_result = await google_drive_port.cancel_job(job_id)
        assert cancel_result is True
        assert google_drive_port.job_registry[job_id].status == JobStatus.CANCELLED
        
        # 完了済みジョブのキャンセル（失敗）
        google_drive_port.job_registry[job_id].status = JobStatus.COMPLETED
        cancel_result = await google_drive_port.cancel_job(job_id)
        assert cancel_result is False


class TestGoogleDriveIntegrationWithExistingSystem:
    """既存システムとの統合テストクラス"""
    
    @pytest.fixture
    def google_drive_port(self):
        """統合テスト用GoogleDrivePortImplインスタンス"""
        config = GoogleDriveConfig(
            credentials_path="/tmp/test_credentials.json",
            max_file_size_mb=100
        )
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
            content_hash="test_hash_123"
        )
        
        # UserInterfaceクラスをモック
        with patch('agent.source.interfaces.google_drive_impl.UserInterface') as mock_ui_class:
            mock_ui_instance = MagicMock()
            mock_ui_class.return_value = mock_ui_instance
            
            # 統合テスト実行
            result = await google_drive_port._integrate_with_existing_system(
                test_file_path, mock_content
            )
            
            # 結果確認
            assert result is True
            mock_ui_instance.update_index.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_integrate_with_existing_system_failure(self, google_drive_port):
        """既存システム統合失敗テスト"""
        test_file_path = "/tmp/test_document.pdf"
        
        mock_content = DocumentContent(
            file_path=test_file_path,
            raw_content="",
            content_type="pdf", 
            file_size=1024,
            content_hash="test_hash_123"
        )
        
        # UserInterfaceクラスで例外発生をモック
        with patch('agent.source.interfaces.google_drive_impl.UserInterface') as mock_ui_class:
            mock_ui_instance = MagicMock()
            mock_ui_instance.update_index.side_effect = Exception("Integration failed")
            mock_ui_class.return_value = mock_ui_instance
            
            # 統合テスト実行
            result = await google_drive_port._integrate_with_existing_system(
                test_file_path, mock_content
            )
            
            # 結果確認（失敗）
            assert result is False
    
    @pytest.mark.asyncio
    @patch('agent.source.interfaces.google_drive_impl.UserInterface')
    async def test_sync_folder_integration_flow(self, mock_ui_class, google_drive_port):
        """フォルダ同期時の既存システム統合フローテスト"""
        # Mock設定
        mock_service = MagicMock()
        mock_files = MagicMock()
        
        # ファイル一覧モック
        mock_files.list.return_value.execute.return_value = {
            'files': [
                {
                    'id': 'file_1',
                    'name': 'test.pdf',
                    'size': '1024',
                    'mimeType': 'application/pdf',
                    'createdTime': '2024-01-01T00:00:00Z',
                    'modifiedTime': '2024-01-02T00:00:00Z'
                }
            ]
        }
        
        # ファイルダウンロードモック
        mock_files.get.return_value.execute.return_value = {
            'id': 'file_1',
            'name': 'test.pdf',
            'mimeType': 'application/pdf'
        }
        
        mock_service.files.return_value = mock_files
        google_drive_port.service = mock_service
        
        # UserInterface統合モック
        mock_ui_instance = MagicMock()
        mock_ui_class.return_value = mock_ui_instance
        
        # ファイルダウンロードとファイル操作をモック
        with patch('builtins.open', mock_open()), \
             patch('pathlib.Path.stat') as mock_stat, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.unlink'), \
             patch('pathlib.Path.mkdir'), \
             patch.object(google_drive_port, '_calculate_file_hash', return_value='test_hash'):
            
            mock_stat.return_value.st_size = 1024
            
            # 同期実行
            result = await google_drive_port.sync_folder("test_folder_id", "test_job_123")
            
            # 結果確認
            assert result.status == JobStatus.COMPLETED
            assert result.total_files == 1
            assert result.successful_files == 1
            assert result.failed_files == 0
            
            # 既存システム統合が呼ばれたことを確認
            mock_ui_instance.update_index.assert_called()


class TestGoogleDriveErrorHandling:
    """Google Driveエラーハンドリングテストクラス"""
    
    @pytest.fixture
    def google_drive_port(self):
        """エラーテスト用GoogleDrivePortImplインスタンス"""
        config = GoogleDriveConfig(
            credentials_path="/tmp/test_credentials.json"
        )
        return GoogleDrivePortImpl(config)
    
    @pytest.mark.asyncio
    async def test_list_folders_not_authenticated(self, google_drive_port):
        """未認証状態でのフォルダ一覧取得エラーテスト"""
        from agent.source.interfaces.data_models import InputError
        
        # 未認証状態（service=None）
        with pytest.raises(InputError) as exc_info:
            await google_drive_port.list_folders()
        
        assert "not authenticated" in str(exc_info.value)
        assert exc_info.value.error_code == "NOT_AUTHENTICATED"
    
    @pytest.mark.asyncio
    async def test_download_file_not_authenticated(self, google_drive_port):
        """未認証状態でのファイルダウンロードエラーテスト"""
        from agent.source.interfaces.data_models import InputError
        
        with pytest.raises(InputError) as exc_info:
            await google_drive_port.download_file("file_id", Path("/tmp/test.pdf"))
        
        assert "not authenticated" in str(exc_info.value)
        assert exc_info.value.error_code == "NOT_AUTHENTICATED"
    
    @pytest.mark.asyncio
    async def test_sync_folder_api_error(self, google_drive_port):
        """API エラー時のフォルダ同期テスト"""
        from agent.source.interfaces.data_models import InputError
        
        # Mock service with API error
        mock_service = MagicMock()
        mock_files = MagicMock()
        
        # HttpError をモック
        with patch('agent.source.interfaces.google_drive_impl.HttpError', Exception):
            mock_files.list.side_effect = Exception("API Error")
            mock_service.files.return_value = mock_files
            google_drive_port.service = mock_service
            
            with pytest.raises(InputError) as exc_info:
                await google_drive_port.sync_folder("folder_id", "job_id")
            
            assert "Folder sync failed" in str(exc_info.value)
            assert exc_info.value.error_code == "SYNC_FAILED"


# ========================================
# Integration Test Helper Functions  
# ========================================

def test_import_existing_modules():
    """既存モジュールのインポート可能性テスト"""
    try:
        # 既存システムのインポートテスト
        from agent.source.ui.interface import UserInterface
        from agent.source.indexer.new_indexer import NewFileIndexer
        from agent.source.analyzer.new_analyzer import NewFileAnalyzer
        
        # インスタンス作成テスト
        ui = UserInterface()
        assert ui is not None
        
        print("✅ 既存システムモジュールのインポート成功")
        return True
        
    except ImportError as e:
        print(f"❌ 既存システムモジュールのインポート失敗: {e}")
        return False


def test_interfaces_module_import():
    """interfacesモジュールのインポート可能性テスト"""
    try:
        # 新規インターフェースのインポートテスト
        from agent.source.interfaces.data_models import (
            DocumentContent, DocumentMetadata, GoogleDriveConfig
        )
        from agent.source.interfaces.input_ports import GoogleDrivePort
        from agent.source.interfaces.google_drive_impl import GoogleDrivePortImpl
        
        # 設定とインスタンス作成テスト
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        assert port is not None
        
        print("✅ interfacesモジュールのインポート成功")
        return True
        
    except ImportError as e:
        print(f"❌ interfacesモジュールのインポート失敗: {e}")
        return False


if __name__ == "__main__":
    """スタンドアロンテスト実行"""
    print("=== Google Drive Integration Test ===")
    
    # 基本インポートテスト
    existing_ok = test_import_existing_modules()
    interfaces_ok = test_interfaces_module_import()
    
    if existing_ok and interfaces_ok:
        print("✅ 全ての基本インポートテストが成功しました")
        print("次のコマンドでフルテストを実行してください:")
        print("uv run pytest agent/tests/test_google_drive_integration.py -v")
    else:
        print("❌ 基本インポートテストに失敗しました")
        print("モジュール依存関係を確認してください")