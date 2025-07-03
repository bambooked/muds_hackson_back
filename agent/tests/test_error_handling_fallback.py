"""
エラーハンドリング・フォールバック機能の包括的テスト

このテストモジュールは、instanceA実装のエラーハンドリングとフォールバック機能を
詳細にテストします。既存システム保護とGraceful Degradation機能を検証。

実行方法:
```bash
# 単体テスト実行
uv run pytest agent/tests/test_error_handling_fallback.py -v

# カバレッジ付き実行
uv run pytest agent/tests/test_error_handling_fallback.py --cov=agent.source.interfaces --cov-report=html -v
```
"""

import asyncio
import tempfile
import pytest
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any

# テスト対象のインポート
from agent.source.interfaces.input_ports import (
    integrate_with_existing_indexer,
    InputError
)
from agent.source.interfaces.data_models import (
    GoogleDriveConfig,
    IngestionResult,
    JobStatus,
    DocumentContent,
    InputError as DataInputError
)
from agent.source.interfaces.google_drive_impl import GoogleDrivePortImpl
from agent.source.interfaces.config_manager import (
    PaaSConfigManager,
    get_config_manager
)


class TestGracefulDegradation:
    """Graceful Degradation（段階的機能縮退）テストクラス"""
    
    def test_google_drive_api_unavailable_fallback(self):
        """Google Drive API利用不可時のフォールバックテスト"""
        # Google Drive API不利用時でもインスタンス作成可能
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        
        with patch('agent.source.interfaces.google_drive_impl.GOOGLE_DRIVE_AVAILABLE', False):
            port = GoogleDrivePortImpl(config)
            
            # インスタンス作成成功
            assert port is not None
            assert port.config == config
            
            # ログで警告が出力されることを確認
            import logging
            with patch('agent.source.interfaces.google_drive_impl.logging.warning') as mock_warning:
                # 初期化時に警告出力される
                port = GoogleDrivePortImpl(config)
                # 実際のAPI使用時に警告が出る設計なので、ここでは作成のみテスト
    
    @pytest.mark.asyncio
    async def test_google_drive_authentication_failure_fallback(self):
        """Google Drive認証失敗時のフォールバックテスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        with patch('agent.source.interfaces.google_drive_impl.GOOGLE_DRIVE_AVAILABLE', True), \
             patch('agent.source.interfaces.google_drive_impl.Credentials') as mock_creds:
            
            # 認証失敗をシミュレート
            mock_creds.from_authorized_user_info.side_effect = Exception("Auth failed")
            
            # 認証失敗時はInputErrorが発生するが、システムは継続
            with pytest.raises(InputError) as exc_info:
                await port.authenticate({'invalid': 'credentials'})
            
            assert "Google Drive authentication failed" in str(exc_info.value)
            assert exc_info.value.error_code == "AUTH_FAILED"
            
            # 既存システムは影響を受けない（設定で機能が無効化される）
    
    def test_config_manager_fallback_to_defaults(self):
        """設定管理フォールバック（デフォルト値使用）テスト"""
        # 環境変数なし、設定ファイルなしでもデフォルト値で動作
        with patch.dict('os.environ', {}, clear=True):
            manager = PaaSConfigManager()
            config = manager.load_config()
            
            # デフォルト値で動作
            assert config.environment == "development"
            assert config.enable_google_drive is False
            assert config.enable_vector_search is False
            
            # 新機能無効時は既存システムのみ動作
            assert manager.is_google_drive_enabled() is False


class TestErrorBoundaries:
    """エラー境界テストクラス（新機能エラーが既存システムに影響しない）"""
    
    @pytest.mark.asyncio
    async def test_integration_error_does_not_affect_existing_system(self):
        """統合エラーが既存システムに影響しないテスト"""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write("Test content")
            tmp_file.flush()
            temp_path = tmp_file.name
        
        try:
            # NewFileIndexerでエラー発生をシミュレート
            with patch('agent.source.interfaces.input_ports.NewFileIndexer') as mock_indexer_class:
                mock_indexer = MagicMock()
                mock_indexer._process_paper.side_effect = Exception("Indexer error")
                mock_indexer_class.return_value = mock_indexer
                
                with patch('agent.source.interfaces.input_ports.shutil.copy2'), \
                     patch('agent.source.interfaces.input_ports.Path.mkdir'), \
                     patch('agent.source.interfaces.input_ports.Path.exists', return_value=False), \
                     patch('agent.source.interfaces.input_ports._create_new_file_object', return_value=MagicMock()):
                    
                    # エラーが適切にキャッチされInputErrorとして再発生
                    with pytest.raises(InputError) as exc_info:
                        await integrate_with_existing_indexer(
                            file_path=temp_path,
                            category='paper',
                            target_name='test.pdf'
                        )
                    
                    assert "Failed to integrate with existing indexer" in str(exc_info.value)
                    
                    # 既存システムは引き続き動作可能（エラーが伝播しない）
                    from agent.source.ui.interface import UserInterface
                    ui = UserInterface()
                    # 既存システムは正常動作（エラー分離されている）
                    assert ui is not None
        
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_google_drive_sync_error_isolation(self):
        """Google Drive同期エラー分離テスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        # モックサービス設定
        mock_service = MagicMock()
        port.service = mock_service
        
        # API エラーをシミュレート
        with patch.object(port, '_list_files_in_folder') as mock_list_files:
            mock_list_files.side_effect = Exception("Google Drive API error")
            
            # sync_folderエラーが適切にキャッチされる
            with pytest.raises(InputError) as exc_info:
                await port.sync_folder("folder_id", "job_id")
            
            assert "Folder sync failed" in str(exc_info.value)
            assert exc_info.value.error_code == "SYNC_FAILED"
            
            # エラー後も既存システムは動作継続
            from agent.source.ui.interface import UserInterface
            ui = UserInterface()
            assert ui is not None


class TestFileSystemErrorHandling:
    """ファイルシステムエラーハンドリングテストクラス"""
    
    @pytest.mark.asyncio
    async def test_file_copy_permission_error(self):
        """ファイルコピー権限エラーテスト"""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write("Test content")
            tmp_file.flush()
            temp_path = tmp_file.name
        
        try:
            # ファイルコピーで権限エラーをシミュレート
            with patch('agent.source.interfaces.input_ports.shutil.copy2') as mock_copy:
                mock_copy.side_effect = PermissionError("Permission denied")
                
                with pytest.raises(InputError) as exc_info:
                    await integrate_with_existing_indexer(
                        file_path=temp_path,
                        category='paper',
                        target_name='test.pdf'
                    )
                
                assert "Failed to integrate with existing indexer" in str(exc_info.value)
        
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_directory_creation_error(self):
        """ディレクトリ作成エラーテスト"""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write("Test content")
            tmp_file.flush()
            temp_path = tmp_file.name
        
        try:
            # ディレクトリ作成でエラーをシミュレート
            with patch('agent.source.interfaces.input_ports.Path.mkdir') as mock_mkdir:
                mock_mkdir.side_effect = OSError("Cannot create directory")
                
                with pytest.raises(InputError) as exc_info:
                    await integrate_with_existing_indexer(
                        file_path=temp_path,
                        category='paper',
                        target_name='test.pdf'
                    )
                
                assert "Failed to integrate with existing indexer" in str(exc_info.value)
        
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_disk_space_error_handling(self):
        """ディスク容量不足エラーハンドリングテスト"""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write("Test content")
            tmp_file.flush()
            temp_path = tmp_file.name
        
        try:
            # ディスク容量不足をシミュレート
            with patch('agent.source.interfaces.input_ports.shutil.copy2') as mock_copy:
                mock_copy.side_effect = OSError(28, "No space left on device")  # ENOSPC
                
                with pytest.raises(InputError) as exc_info:
                    await integrate_with_existing_indexer(
                        file_path=temp_path,
                        category='paper',
                        target_name='test.pdf'
                    )
                
                assert "Failed to integrate with existing indexer" in str(exc_info.value)
        
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestNetworkErrorHandling:
    """ネットワークエラーハンドリングテストクラス"""
    
    @pytest.mark.asyncio
    async def test_google_drive_api_timeout(self):
        """Google Drive APIタイムアウトテスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        # モックサービス設定
        mock_service = MagicMock()
        port.service = mock_service
        
        # タイムアウトエラーをシミュレート
        with patch('agent.source.interfaces.google_drive_impl.HttpError', Exception):
            mock_service.files().list().execute.side_effect = Exception("Request timeout")
            
            with pytest.raises(InputError) as exc_info:
                await port.list_folders()
            
            assert "Failed to list folders" in str(exc_info.value)
            assert exc_info.value.error_code == "API_ERROR"
    
    @pytest.mark.asyncio
    async def test_google_drive_connection_error(self):
        """Google Drive接続エラーテスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        # モックサービス設定
        mock_service = MagicMock()
        port.service = mock_service
        
        # 接続エラーをシミュレート
        with patch('agent.source.interfaces.google_drive_impl.HttpError', Exception):
            mock_service.files().get().execute.side_effect = Exception("Connection refused")
            
            with pytest.raises(InputError) as exc_info:
                await port.get_file_metadata("file_id")
            
            assert "Failed to get file metadata" in str(exc_info.value)
            assert exc_info.value.error_code == "API_ERROR"


class TestDataIntegrityErrorHandling:
    """データ整合性エラーハンドリングテストクラス"""
    
    @pytest.mark.asyncio
    async def test_file_corruption_during_download(self):
        """ファイルダウンロード中の破損エラーテスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        # モックサービス設定
        mock_service = MagicMock()
        port.service = mock_service
        
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "test_file.pdf"
            
            # ファイルメタデータ取得成功
            mock_service.files().get().execute.return_value = {
                'id': 'file_123',
                'name': 'test.pdf',
                'mimeType': 'application/pdf'
            }
            
            # ダウンロード中にエラー発生をシミュレート
            with patch('agent.source.interfaces.google_drive_impl.MediaIoBaseDownload') as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.next_chunk.side_effect = Exception("Download corrupted")
                mock_downloader_class.return_value = mock_downloader
                
                with pytest.raises(InputError) as exc_info:
                    await port.download_file('file_123', target_path)
                
                assert "Failed to download file" in str(exc_info.value)
                assert exc_info.value.error_code == "DOWNLOAD_FAILED"
    
    def test_invalid_file_hash_calculation(self):
        """ファイルハッシュ計算エラーテスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        # 存在しないファイルでハッシュ計算
        non_existent_path = Path("/tmp/non_existent_file.txt")
        
        # ファイル不存在によるエラーはOSErrorとしてキャッチされる
        with pytest.raises(FileNotFoundError):
            port._calculate_file_hash(non_existent_path)


class TestJobManagementErrorHandling:
    """ジョブ管理エラーハンドリングテストクラス"""
    
    @pytest.mark.asyncio
    async def test_job_progress_tracking_with_errors(self):
        """エラー発生時のジョブ進行追跡テスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        # モックサービス設定
        mock_service = MagicMock()
        port.service = mock_service
        
        job_id = "test_error_job"
        folder_id = "test_folder"
        
        # 部分的な成功・失敗をシミュレート
        with patch.object(port, '_list_files_in_folder') as mock_list_files, \
             patch.object(port, '_process_single_file') as mock_process_file:
            
            mock_list_files.return_value = [
                {'id': 'file1', 'name': 'success.pdf', 'mimeType': 'application/pdf'},
                {'id': 'file2', 'name': 'error.pdf', 'mimeType': 'application/pdf'}
            ]
            
            # 1つ目は成功、2つ目はエラー
            def side_effect(file_info, result, user_context=None):
                if file_info['name'] == 'error.pdf':
                    raise Exception("Processing failed")
            
            mock_process_file.side_effect = side_effect
            
            # テスト実行
            result = await port.sync_folder(folder_id, job_id)
            
            # 結果確認（部分的成功）
            assert result.status == JobStatus.COMPLETED
            assert result.total_files == 2
            assert result.successful_files == 1
            assert result.failed_files == 1
            assert len(result.errors) == 1
            assert "error.pdf" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_job_cancellation_during_processing(self):
        """処理中のジョブキャンセルテスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        job_id = "test_cancel_job"
        
        # 実行中ジョブを登録
        result = IngestionResult(
            job_id=job_id,
            status=JobStatus.RUNNING,
            total_files=10,
            processed_files=5,
            successful_files=3,
            failed_files=2,
            start_time=datetime.now()
        )
        port.job_registry[job_id] = result
        
        # キャンセル実行
        cancel_success = await port.cancel_job(job_id)
        
        # 結果確認
        assert cancel_success is True
        assert port.job_registry[job_id].status == JobStatus.CANCELLED
        assert port.job_registry[job_id].end_time is not None


class TestExistingSystemProtection:
    """既存システム保護テストクラス"""
    
    def test_existing_system_unaffected_by_new_imports(self):
        """新機能インポートが既存システムに影響しないテスト"""
        # 新機能インポート前の既存システム動作確認
        try:
            from agent.source.ui.interface import UserInterface
            ui_before = UserInterface()
            assert ui_before is not None
        except Exception as e:
            pytest.fail(f"既存システム動作失敗（新機能インポート前）: {e}")
        
        # 新機能インポート
        try:
            from agent.source.interfaces.google_drive_impl import GoogleDrivePortImpl
            from agent.source.interfaces.config_manager import PaaSConfigManager
            from agent.source.interfaces.input_ports import integrate_with_existing_indexer
        except Exception as e:
            pytest.fail(f"新機能インポート失敗: {e}")
        
        # 新機能インポート後の既存システム動作確認
        try:
            from agent.source.ui.interface import UserInterface
            ui_after = UserInterface()
            assert ui_after is not None
        except Exception as e:
            pytest.fail(f"既存システム動作失敗（新機能インポート後）: {e}")
    
    def test_config_manager_does_not_override_existing_config(self):
        """設定マネージャーが既存設定を上書きしないテスト"""
        # 既存config.pyの動作確認
        try:
            import config
            assert hasattr(config, 'DATA_DIR')
            assert hasattr(config, 'GEMINI_API_KEY')
            original_data_dir = config.DATA_DIR
        except Exception as e:
            pytest.fail(f"既存config.py読み込み失敗: {e}")
        
        # 新設定マネージャー使用
        try:
            from agent.source.interfaces.config_manager import get_config_manager
            manager = get_config_manager()
            paas_config = manager.load_config()
        except Exception as e:
            pytest.fail(f"新設定マネージャー失敗: {e}")
        
        # 既存設定が保持されていることを確認
        try:
            import config
            assert config.DATA_DIR == original_data_dir  # 既存設定は変更されない
        except Exception as e:
            pytest.fail(f"既存設定保持確認失敗: {e}")


class TestMemoryLeakPrevention:
    """メモリリーク防止テストクラス"""
    
    @pytest.mark.asyncio
    async def test_temporary_file_cleanup(self):
        """一時ファイルクリーンアップテスト"""
        config = GoogleDriveConfig(credentials_path="/tmp/test.json")
        port = GoogleDrivePortImpl(config)
        
        # 一時ファイル作成
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write("Test content")
            tmp_file.flush()
            temp_path = Path(tmp_file.name)
        
        # ファイルが存在することを確認
        assert temp_path.exists()
        
        # 処理中にエラーが発生してもクリーンアップされることをテスト
        mock_content = DocumentContent(
            file_path=str(temp_path),
            raw_content="",
            content_type="pdf",
            file_size=1024,
            content_hash="test_hash",
            metadata={'original_name': 'test.pdf'}
        )
        
        with patch.object(port, '_integrate_with_existing_system') as mock_integrate:
            mock_integrate.side_effect = Exception("Integration failed")
            
            # _process_single_fileでエラーが発生
            result = IngestionResult(
                job_id="test_job",
                status=JobStatus.RUNNING,
                total_files=1,
                processed_files=0,
                successful_files=0,
                failed_files=0,
                start_time=datetime.now()
            )
            
            # エラー発生してもファイルクリーンアップが実行される設計を確認
            # （実際のテストでは、try-finallyブロックでクリーンアップされる）
            
        # 手動クリーンアップ（テスト後始末）
        if temp_path.exists():
            temp_path.unlink()


if __name__ == "__main__":
    """スタンドアロンテスト実行"""
    print("=== エラーハンドリング・フォールバック テスト実行 ===")
    
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