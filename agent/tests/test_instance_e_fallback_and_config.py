"""
Instance E 統合テストスイート - フォールバック機能と設定管理テスト

このテストスイートは、以下の重要な機能をテストします：
1. フォールバック機能の動作確認
2. 設定による機能ON/OFFの動作確認
3. エラー発生時の回復機能
4. 既存システムとの互換性保持

実行方法:
```bash
# フォールバック・設定テスト実行
uv run pytest agent/tests/test_instance_e_fallback_and_config.py -v

# 詳細ログ付き実行
uv run pytest agent/tests/test_instance_e_fallback_and_config.py -v -s --log-cli-level=INFO

# カバレッジ付き実行
uv run pytest agent/tests/test_instance_e_fallback_and_config.py --cov=agent.source.interfaces --cov-report=html -v
```
"""

import asyncio
import tempfile
import pytest
import json
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any, List, Optional

# テスト対象の統合システム
from agent.source.interfaces.unified_paas_impl import UnifiedPaaSImpl
from agent.source.interfaces.config_manager import PaaSConfigManager, get_config_manager, is_feature_enabled
from agent.source.interfaces.data_models import (
    PaaSConfig,
    SearchMode,
    SearchRequest,
    SearchResult,
    DocumentIngestionRequest,
    DocumentIngestionResult,
    SystemStatistics,
    HealthStatus,
    UserContext,
    DocumentMetadata,
    GoogleDriveConfig,
    VectorSearchConfig,
    AuthConfig
)


class TestFallbackMechanisms:
    """フォールバック機能テストクラス"""
    
    @pytest.fixture
    def full_config(self):
        """全機能有効設定"""
        return PaaSConfig(
            enable_google_drive=True,
            enable_vector_search=True,
            enable_authentication=True,
            enable_monitoring=True,
            google_drive=GoogleDriveConfig(
                credentials_path="/tmp/test_credentials.json",
                max_file_size_mb=100
            ),
            vector_search=VectorSearchConfig(
                provider='chroma',
                embedding_model='sentence-transformers/all-MiniLM-L6-v2',
                collection_name='test_collection',
                dimension=384
            ),
            auth=AuthConfig(
                provider='google',
                session_timeout_hours=24,
                allowed_domains=['university.ac.jp']
            )
        )
    
    @pytest.fixture
    def mock_user_context(self):
        """テスト用ユーザーコンテキスト"""
        return UserContext(
            user_id="fallback_test_user",
            email="test@university.ac.jp",
            permissions=['read', 'write'],
            session_id="fallback_session"
        )
    
    @pytest.mark.asyncio
    async def test_search_fallback_vector_to_keyword(self, full_config, mock_user_context):
        """検索フォールバック: ベクトル検索 → キーワード検索"""
        print("\n=== 検索フォールバックテスト: Vector → Keyword ===")
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=full_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        search_request = SearchRequest(
            query="機械学習 研究データ",
            mode=SearchMode.VECTOR,
            max_results=10
        )
        
        with patch.object(unified_interface, '_search_vector_system') as mock_vector_search, \
             patch.object(unified_interface, '_search_existing_system') as mock_existing_search:
            
            # ベクトル検索でエラー発生
            mock_vector_search.side_effect = Exception("Vector search service unavailable")
            
            # 既存システムでの検索結果（フォールバック）
            fallback_results = [
                DocumentMetadata(
                    id="fallback_doc_1",
                    title="機械学習による研究データ分析手法",
                    content_type="paper",
                    file_path="/data/paper/ml_analysis.pdf",
                    file_size=2048000,
                    created_at=datetime.now(),
                    metadata={'keywords': ['機械学習', '研究データ', '分析']}
                )
            ]
            
            mock_existing_search.return_value = SearchResult(
                results=fallback_results,
                total_results=1,
                search_time_ms=120,
                mode=SearchMode.KEYWORD
            )
            
            # 検索実行（フォールバック発生）
            search_result = await unified_interface.search_documents(search_request, mock_user_context)
            
            # フォールバック確認
            assert search_result.mode == SearchMode.KEYWORD  # ベクトルからキーワードにフォールバック
            assert search_result.total_results == 1
            assert len(search_result.results) == 1
            assert "機械学習" in search_result.results[0].title
            
            print("✅ ベクトル検索エラー時のキーワード検索フォールバック成功")
    
    @pytest.mark.asyncio
    async def test_ingestion_fallback_gdrive_to_upload(self, full_config, mock_user_context):
        """取り込みフォールバック: Google Drive → アップロード"""
        print("\n=== 取り込みフォールバックテスト: Google Drive → Upload ===")
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=full_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        ingestion_request = DocumentIngestionRequest(
            source_type="google_drive",
            source_id="error_folder_123",
            auto_analyze=True,
            metadata={'folder_name': 'Test Folder'}
        )
        
        with patch.object(unified_interface, '_ingest_from_google_drive') as mock_gdrive_ingest, \
             patch.object(unified_interface, '_ingest_from_upload') as mock_upload_ingest:
            
            # Google Drive取り込みでエラー発生
            mock_gdrive_ingest.side_effect = Exception("Google Drive API quota exceeded")
            
            # アップロード取り込みが正常動作（フォールバック）
            mock_upload_ingest.return_value = DocumentIngestionResult(
                job_id="fallback_upload_job",
                status="completed",
                total_files=2,
                processed_files=2,
                failed_files=0,
                processing_time_ms=1500,
                errors=[],
                metadata={'fallback_mode': 'google_drive_to_upload'}
            )
            
            # 取り込み実行（フォールバック発生）
            ingestion_result = await unified_interface.ingest_documents(ingestion_request, mock_user_context)
            
            # フォールバック確認
            assert ingestion_result.status == "completed"
            assert ingestion_result.processed_files == 2
            assert ingestion_result.failed_files == 0
            assert 'fallback_mode' in ingestion_result.metadata
            
            print("✅ Google Drive取り込みエラー時のアップロードフォールバック成功")
    
    @pytest.mark.asyncio
    async def test_health_check_fallback_degraded_operation(self, full_config, mock_user_context):
        """ヘルスチェックフォールバック: 部分的障害 → 劣化動作"""
        print("\n=== ヘルスチェックフォールバックテスト: 部分的障害 → 劣化動作 ===")
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=full_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        with patch.object(unified_interface, '_check_existing_system_health') as mock_existing_health, \
             patch.object(unified_interface, '_check_google_drive_health') as mock_gdrive_health, \
             patch.object(unified_interface, '_check_vector_search_health') as mock_vector_health:
            
            # 一部機能で障害発生
            mock_existing_health.return_value = HealthStatus.HEALTHY  # 既存システムは正常
            mock_gdrive_health.return_value = HealthStatus.UNHEALTHY  # Google Drive障害
            mock_vector_health.side_effect = Exception("Vector search timeout")  # ベクトル検索エラー
            
            # ヘルスチェック実行
            health_status = await unified_interface.check_system_health(mock_user_context)
            
            # 劣化動作確認
            assert health_status == HealthStatus.DEGRADED  # 部分的障害で劣化動作
            
            print("✅ 部分的障害時の劣化動作フォールバック成功")
    
    @pytest.mark.asyncio
    async def test_statistics_fallback_existing_system_only(self, full_config, mock_user_context):
        """統計情報フォールバック: 既存システムのみ"""
        print("\n=== 統計情報フォールバックテスト: 既存システムのみ ===")
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=full_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        with patch.object(unified_interface, '_get_existing_system_stats') as mock_existing_stats, \
             patch.object(unified_interface, '_get_vector_search_stats') as mock_vector_stats, \
             patch.object(unified_interface, '_get_google_drive_stats') as mock_gdrive_stats:
            
            # 既存システム統計は正常
            mock_existing_stats.return_value = {
                'total_documents': 32,
                'datasets': 4,
                'papers': 2,
                'posters': 2,
                'total_size_mb': 293.8
            }
            
            # 新機能の統計取得でエラー発生
            mock_vector_stats.side_effect = Exception("Vector statistics unavailable")
            mock_gdrive_stats.side_effect = Exception("Google Drive statistics unavailable")
            
            # 統計情報取得実行
            stats = await unified_interface.get_system_statistics(mock_user_context)
            
            # フォールバック確認
            assert stats.total_documents == 32
            assert stats.total_size_mb == 293.8
            assert stats.feature_status['google_drive'] == True  # 設定上は有効
            assert stats.feature_status['vector_search'] == True  # 設定上は有効
            # ただし実際の統計は既存システムのみ
            
            print("✅ 新機能統計エラー時の既存システム統計フォールバック成功")


class TestConfigurationManagement:
    """設定管理テストクラス"""
    
    @pytest.fixture
    def minimal_config(self):
        """最小限設定（新機能無効）"""
        return PaaSConfig(
            enable_google_drive=False,
            enable_vector_search=False,
            enable_authentication=False,
            enable_monitoring=False
        )
    
    @pytest.fixture
    def partial_config(self):
        """部分的設定（一部機能有効）"""
        return PaaSConfig(
            enable_google_drive=True,
            enable_vector_search=False,
            enable_authentication=True,
            enable_monitoring=True,
            google_drive=GoogleDriveConfig(
                credentials_path="/tmp/test_credentials.json",
                max_file_size_mb=50
            ),
            auth=AuthConfig(
                provider='google',
                session_timeout_hours=12,
                allowed_domains=['research.org']
            )
        )
    
    @pytest.mark.asyncio
    async def test_minimal_config_existing_system_only(self, minimal_config):
        """最小限設定テスト: 既存システムのみ動作"""
        print("\n=== 最小限設定テスト: 既存システムのみ ===")
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=minimal_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
            
            # 設定確認
            assert unified_interface.config_manager.load_config().enable_google_drive == False
            assert unified_interface.config_manager.load_config().enable_vector_search == False
            assert unified_interface.config_manager.load_config().enable_authentication == False
            
            print("✅ 最小限設定（全新機能無効）確認成功")
        
        # 検索テスト（既存システムのみ）
        user_context = UserContext(
            user_id="minimal_user",
            email="test@example.com",
            permissions=['read'],
            session_id="minimal_session"
        )
        
        search_request = SearchRequest(
            query="test query",
            mode=SearchMode.HYBRID,  # ハイブリッドを要求
            max_results=5
        )
        
        with patch.object(unified_interface, '_search_existing_system') as mock_existing_search:
            # 既存システムでの検索結果のみ
            mock_existing_search.return_value = SearchResult(
                results=[
                    DocumentMetadata(
                        id="existing_doc",
                        title="既存システムドキュメント",
                        content_type="paper",
                        file_path="/data/paper/existing.pdf",
                        file_size=1024000,
                        created_at=datetime.now()
                    )
                ],
                total_results=1,
                search_time_ms=80,
                mode=SearchMode.KEYWORD  # キーワード検索にフォールダウン
            )
            
            search_result = await unified_interface.search_documents(search_request, user_context)
            
            # 既存システムのみで動作確認
            assert search_result.mode == SearchMode.KEYWORD  # ハイブリッドからキーワードにフォールダウン
            assert search_result.total_results == 1
            
            print("✅ 新機能無効時の既存システム検索動作確認成功")
    
    @pytest.mark.asyncio
    async def test_partial_config_selective_features(self, partial_config):
        """部分的設定テスト: 選択的機能有効化"""
        print("\n=== 部分的設定テスト: 選択的機能有効化 ===")
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=partial_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
            
            # 設定確認
            config = unified_interface.config_manager.load_config()
            assert config.enable_google_drive == True   # 有効
            assert config.enable_vector_search == False # 無効
            assert config.enable_authentication == True # 有効
            
            print("✅ 部分的設定（Google Drive + Auth有効、Vector Search無効）確認成功")
        
        # 取り込みテスト（Google Drive有効）
        user_context = UserContext(
            user_id="partial_user",
            email="test@research.org",
            permissions=['read', 'write'],
            session_id="partial_session"
        )
        
        ingestion_request = DocumentIngestionRequest(
            source_type="google_drive",
            source_id="partial_test_folder",
            auto_analyze=True
        )
        
        with patch.object(unified_interface, '_ingest_from_google_drive') as mock_gdrive_ingest:
            mock_gdrive_ingest.return_value = DocumentIngestionResult(
                job_id="partial_gdrive_job",
                status="completed",
                total_files=3,
                processed_files=3,
                failed_files=0,
                processing_time_ms=2000,
                errors=[]
            )
            
            ingestion_result = await unified_interface.ingest_documents(ingestion_request, user_context)
            
            # Google Drive取り込み動作確認
            assert ingestion_result.status == "completed"
            assert ingestion_result.processed_files == 3
            
            print("✅ Google Drive有効時の取り込み動作確認成功")
        
        # 検索テスト（Vector Search無効）
        search_request = SearchRequest(
            query="partial test query",
            mode=SearchMode.VECTOR,  # ベクトル検索を要求
            max_results=10
        )
        
        with patch.object(unified_interface, '_search_existing_system') as mock_existing_search:
            mock_existing_search.return_value = SearchResult(
                results=[],
                total_results=0,
                search_time_ms=60,
                mode=SearchMode.KEYWORD
            )
            
            search_result = await unified_interface.search_documents(search_request, user_context)
            
            # ベクトル検索無効時のフォールバック確認
            assert search_result.mode == SearchMode.KEYWORD  # ベクトルからキーワードにフォールバック
            
            print("✅ Vector Search無効時のキーワード検索フォールバック確認成功")
    
    def test_environment_variable_config_override(self):
        """環境変数による設定オーバーライドテスト"""
        print("\n=== 環境変数設定オーバーライドテスト ===")
        
        # 環境変数設定
        env_vars = {
            'ENABLE_GOOGLE_DRIVE': 'true',
            'ENABLE_VECTOR_SEARCH': 'false',
            'ENABLE_AUTHENTICATION': 'true',
            'GOOGLE_DRIVE_MAX_FILE_SIZE_MB': '200',
            'AUTH_SESSION_TIMEOUT_HOURS': '48'
        }
        
        with patch.dict('os.environ', env_vars, clear=True):
            config_manager = PaaSConfigManager()
            config = config_manager.load_config()
            
            # 環境変数による設定確認
            assert config.enable_google_drive == True
            assert config.enable_vector_search == False
            assert config.enable_authentication == True
            assert config.google_drive.max_file_size_mb == 200
            assert config.auth.session_timeout_hours == 48
            
            print("✅ 環境変数による設定オーバーライド成功")
    
    def test_config_file_override(self):
        """設定ファイルによるオーバーライドテスト"""
        print("\n=== 設定ファイルオーバーライドテスト ===")
        
        # 設定ファイル内容
        config_data = {
            'enable_google_drive': False,  # 環境変数をオーバーライド
            'enable_vector_search': True,
            'enable_authentication': False,
            'google_drive': {
                'max_file_size_mb': 50
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as config_file:
            json.dump(config_data, config_file)
            config_file.flush()
            
            try:
                # 環境変数も設定
                env_vars = {
                    'ENABLE_GOOGLE_DRIVE': 'true',  # これは設定ファイルでオーバーライドされる
                    'ENABLE_AUTHENTICATION': 'true'  # これも設定ファイルでオーバーライドされる
                }
                
                with patch.dict('os.environ', env_vars, clear=True):
                    config_manager = PaaSConfigManager(config_file.name)
                    config = config_manager.load_config()
                    
                    # 設定ファイルが環境変数をオーバーライド
                    assert config.enable_google_drive == False  # 設定ファイル優先
                    assert config.enable_vector_search == True
                    assert config.enable_authentication == False  # 設定ファイル優先
                    assert config.google_drive.max_file_size_mb == 50
                    
                    print("✅ 設定ファイルによる環境変数オーバーライド成功")
                    
            finally:
                Path(config_file.name).unlink(missing_ok=True)
    
    def test_feature_enabled_helper_functions(self):
        """機能有効化ヘルパー関数テスト"""
        print("\n=== 機能有効化ヘルパー関数テスト ===")
        
        env_vars = {
            'ENABLE_GOOGLE_DRIVE': 'true',
            'ENABLE_VECTOR_SEARCH': 'false',
            'ENABLE_AUTHENTICATION': 'true'
        }
        
        with patch.dict('os.environ', env_vars, clear=True):
            # グローバル状態リセット
            with patch('agent.source.interfaces.config_manager._config_manager', None):
                # 機能有効化確認
                assert is_feature_enabled('google_drive') == True
                assert is_feature_enabled('vector_search') == False
                assert is_feature_enabled('authentication') == True
                assert is_feature_enabled('monitoring') == False  # デフォルト値
                
                print("✅ 機能有効化ヘルパー関数動作確認成功")


class TestBackwardCompatibility:
    """後方互換性テストクラス"""
    
    def test_existing_system_preservation(self):
        """既存システム保持テスト"""
        print("\n=== 既存システム保持テスト ===")
        
        # 新機能インポート前の既存システム
        try:
            from agent.source.ui.interface import UserInterface
            ui_before = UserInterface()
            original_methods = set(dir(ui_before))
            print("✅ 既存システム（新機能インポート前）正常動作")
        except Exception as e:
            pytest.fail(f"既存システム動作失敗: {e}")
        
        # 新機能全インポート
        try:
            from agent.source.interfaces import unified_paas_impl
            from agent.source.interfaces import config_manager
            from agent.source.interfaces import data_models
            print("✅ 新機能全インポート成功")
        except Exception as e:
            pytest.fail(f"新機能インポート失敗: {e}")
        
        # 新機能インポート後の既存システム
        try:
            from agent.source.ui.interface import UserInterface
            ui_after = UserInterface()
            after_methods = set(dir(ui_after))
            
            # 既存メソッドが保持されていることを確認
            lost_methods = original_methods - after_methods
            assert len(lost_methods) == 0, f"失われたメソッド: {lost_methods}"
            
            print("✅ 既存システム（新機能インポート後）正常動作・互換性保持")
        except Exception as e:
            pytest.fail(f"後方互換性チェック失敗: {e}")
    
    @pytest.mark.asyncio
    async def test_existing_functionality_unchanged(self):
        """既存機能不変テスト"""
        print("\n=== 既存機能不変テスト ===")
        
        # 既存システムの基本動作確認
        try:
            from agent.source.ui.interface import UserInterface
            
            # UserInterfaceの基本機能テスト
            ui = UserInterface()
            
            # 基本メソッドの存在確認
            assert hasattr(ui, 'search_documents'), "search_documentsメソッドが存在しません"
            assert hasattr(ui, 'get_document_summary'), "get_document_summaryメソッドが存在しません"
            
            # アナライザーの存在確認
            assert hasattr(ui, 'analyzer'), "analyzerが存在しません"
            assert ui.analyzer is not None, "analyzerが初期化されていません"
            
            print("✅ 既存機能の基本構造保持確認成功")
        except Exception as e:
            pytest.fail(f"既存機能確認失敗: {e}")
    
    def test_data_integrity_preservation(self):
        """データ整合性保持テスト"""
        print("\n=== データ整合性保持テスト ===")
        
        # 既存データベーススキーマの確認
        try:
            from agent.source.database.new_repository import (
                DatasetRepository,
                PaperRepository,
                PosterRepository
            )
            
            # リポジトリ初期化確認
            dataset_repo = DatasetRepository()
            paper_repo = PaperRepository()
            poster_repo = PosterRepository()
            
            assert dataset_repo is not None
            assert paper_repo is not None
            assert poster_repo is not None
            
            print("✅ 既存データベース構造保持確認成功")
        except Exception as e:
            pytest.fail(f"データベース構造確認失敗: {e}")


class TestResilienceAndRecovery:
    """復旧性・回復性テストクラス"""
    
    @pytest.mark.asyncio
    async def test_cascading_failure_recovery(self):
        """連鎖障害回復テスト"""
        print("\n=== 連鎖障害回復テスト ===")
        
        # 全新機能が障害状態の設定
        config = PaaSConfig(
            enable_google_drive=True,
            enable_vector_search=True,
            enable_authentication=True,
            enable_monitoring=True,
            google_drive=GoogleDriveConfig(credentials_path="/tmp/test.json"),
            vector_search=VectorSearchConfig(provider='chroma'),
            auth=AuthConfig(provider='google')
        )
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        user_context = UserContext(
            user_id="resilience_user",
            email="test@university.ac.jp",
            permissions=['read'],
            session_id="resilience_session"
        )
        
        # 全新機能で障害発生シミュレーション
        with patch.object(unified_interface, '_check_google_drive_health') as mock_gdrive_health, \
             patch.object(unified_interface, '_check_vector_search_health') as mock_vector_health, \
             patch.object(unified_interface, '_check_authentication_health') as mock_auth_health, \
             patch.object(unified_interface, '_check_existing_system_health') as mock_existing_health:
            
            # 全新機能で障害
            mock_gdrive_health.side_effect = Exception("Google Drive service down")
            mock_vector_health.side_effect = Exception("Vector search cluster unreachable")
            mock_auth_health.side_effect = Exception("Authentication service timeout")
            
            # 既存システムは正常
            mock_existing_health.return_value = HealthStatus.HEALTHY
            
            # ヘルスチェック実行
            health_status = await unified_interface.check_system_health(user_context)
            
            # 既存システムで継続動作確認
            assert health_status in [HealthStatus.DEGRADED, HealthStatus.HEALTHY]
            print("✅ 全新機能障害時の既存システム継続動作確認成功")
        
        # 検索動作確認（既存システムフォールバック）
        with patch.object(unified_interface, '_search_vector_system') as mock_vector_search, \
             patch.object(unified_interface, '_search_existing_system') as mock_existing_search:
            
            mock_vector_search.side_effect = Exception("Vector search unavailable")
            mock_existing_search.return_value = SearchResult(
                results=[
                    DocumentMetadata(
                        id="recovery_doc",
                        title="回復テストドキュメント",
                        content_type="paper",
                        file_path="/data/paper/recovery.pdf",
                        file_size=1024000,
                        created_at=datetime.now()
                    )
                ],
                total_results=1,
                search_time_ms=100,
                mode=SearchMode.KEYWORD
            )
            
            search_request = SearchRequest(
                query="recovery test",
                mode=SearchMode.VECTOR,
                max_results=5
            )
            
            search_result = await unified_interface.search_documents(search_request, user_context)
            
            # フォールバック動作確認
            assert search_result.total_results == 1
            assert search_result.mode == SearchMode.KEYWORD
            print("✅ 連鎖障害時の検索フォールバック動作確認成功")
    
    @pytest.mark.asyncio
    async def test_partial_recovery_behavior(self):
        """部分回復動作テスト"""
        print("\n=== 部分回復動作テスト ===")
        
        config = PaaSConfig(
            enable_google_drive=True,
            enable_vector_search=True,
            enable_authentication=True,
            google_drive=GoogleDriveConfig(credentials_path="/tmp/test.json"),
            vector_search=VectorSearchConfig(provider='chroma'),
            auth=AuthConfig(provider='google')
        )
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        user_context = UserContext(
            user_id="recovery_user",
            email="test@university.ac.jp",
            permissions=['read', 'write'],
            session_id="recovery_session"
        )
        
        # 部分的回復シナリオ（Google Drive回復、Vector Search障害継続）
        with patch.object(unified_interface, '_ingest_from_google_drive') as mock_gdrive_ingest, \
             patch.object(unified_interface, '_search_vector_system') as mock_vector_search, \
             patch.object(unified_interface, '_search_existing_system') as mock_existing_search:
            
            # Google Drive取り込みは正常動作（回復）
            mock_gdrive_ingest.return_value = DocumentIngestionResult(
                job_id="recovery_job",
                status="completed",
                total_files=2,
                processed_files=2,
                failed_files=0,
                processing_time_ms=1200,
                errors=[]
            )
            
            # Vector Searchは障害継続
            mock_vector_search.side_effect = Exception("Vector search still unavailable")
            
            # 既存検索は正常
            mock_existing_search.return_value = SearchResult(
                results=[],
                total_results=0,
                search_time_ms=80,
                mode=SearchMode.KEYWORD
            )
            
            # 取り込みテスト（回復した機能）
            ingestion_request = DocumentIngestionRequest(
                source_type="google_drive",
                source_id="recovery_folder",
                auto_analyze=True
            )
            
            ingestion_result = await unified_interface.ingest_documents(ingestion_request, user_context)
            assert ingestion_result.status == "completed"
            print("✅ 回復した機能（Google Drive）の正常動作確認成功")
            
            # 検索テスト（障害継続機能のフォールバック）
            search_request = SearchRequest(
                query="recovery test search",
                mode=SearchMode.VECTOR,
                max_results=5
            )
            
            search_result = await unified_interface.search_documents(search_request, user_context)
            assert search_result.mode == SearchMode.KEYWORD  # フォールバック継続
            print("✅ 障害継続機能のフォールバック継続確認成功")


if __name__ == "__main__":
    """フォールバック・設定管理テストスイート実行"""
    print("=== Instance E - フォールバック・設定管理テストスイート実行 ===")
    
    import subprocess
    import sys
    
    try:
        # 詳細出力でテスト実行
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            __file__, 
            '-v',
            '-s',  # 出力を表示
            '--tb=short'
        ], cwd=Path(__file__).parent.parent.parent, capture_output=False)
        
        print(f"\nフォールバック・設定管理テストスイート結果: {'SUCCESS' if result.returncode == 0 else 'FAILED'}")
        sys.exit(result.returncode)
        
    except Exception as e:
        print(f"フォールバック・設定管理テストスイート実行エラー: {e}")
        sys.exit(1)