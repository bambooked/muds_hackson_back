"""
Instance E 統合テストスイート - 各ポート統合テスト

このテストスイートは、Instance A-Dで実装された各ポートの統合テストを行います。
- Instance A: GoogleDriveInputPort
- Instance B: VectorSearchPort
- Instance C: AuthenticationPort
- Instance D: PaaSOrchestrationPort

実行方法:
```bash
# 統合テストスイート実行
uv run pytest agent/tests/test_instance_e_ports_integration.py -v

# 詳細ログ付き実行
uv run pytest agent/tests/test_instance_e_ports_integration.py -v -s --log-cli-level=INFO

# カバレッジ付き実行
uv run pytest agent/tests/test_instance_e_ports_integration.py --cov=agent.source.interfaces --cov-report=html -v
```
"""

import asyncio
import tempfile
import pytest
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any, List, Optional

# テスト対象のポート実装
from agent.source.interfaces.google_drive_impl import GoogleDrivePortImpl
from agent.source.interfaces.vector_search_impl import ChromaVectorSearchPort
from agent.source.interfaces.auth_implementations import (
    GoogleOAuth2Authentication, 
    DatabaseUserManagement, 
    RoleBasedAuthorization
)
from agent.source.interfaces.paas_orchestration_impl import PaaSOrchestrationImpl
from agent.source.interfaces.data_models import (
    GoogleDriveConfig,
    VectorSearchConfig,
    AuthConfig,
    PaaSConfig,
    UserContext,
    DocumentContent,
    DocumentMetadata,
    SearchRequest,
    SearchMode,
    HealthStatus,
    JobStatus
)


class TestInstanceAGoogleDrivePortIntegration:
    """Instance A - GoogleDrivePort統合テストクラス"""
    
    @pytest.fixture
    def gdrive_config(self):
        """Google Drive設定"""
        return GoogleDriveConfig(
            credentials_path="/tmp/test_credentials.json",
            max_file_size_mb=100,
            supported_mime_types=['application/pdf', 'text/csv', 'application/json']
        )
    
    @pytest.fixture
    def mock_user_context(self):
        """テスト用ユーザーコンテキスト"""
        return UserContext(
            user_id="gdrive_user_123",
            email="test@university.ac.jp",
            permissions=['read', 'write'],
            session_id="gdrive_session_456"
        )
    
    @pytest.mark.asyncio
    async def test_google_drive_port_full_workflow(self, gdrive_config, mock_user_context):
        """Google Drive Port完全ワークフローテスト"""
        print("\n=== Google Drive Port完全ワークフローテスト開始 ===")
        
        # 1. ポート初期化
        gdrive_port = GoogleDrivePortImpl(gdrive_config)
        assert gdrive_port.config == gdrive_config
        print("✓ Google Drive Port初期化成功")
        
        # 2. 認証フローテスト
        with patch('agent.source.interfaces.google_drive_impl.GOOGLE_DRIVE_AVAILABLE', True), \
             patch('agent.source.interfaces.google_drive_impl.build') as mock_build:
            
            # 認証成功モック
            mock_service = MagicMock()
            mock_about = MagicMock()
            mock_about.get.return_value.execute.return_value = {
                'user': {'emailAddress': 'test@university.ac.jp'}
            }
            mock_service.about.return_value = mock_about
            mock_build.return_value = mock_service
            
            auth_result = await gdrive_port.authenticate({
                'token': 'test_token',
                'refresh_token': 'test_refresh_token',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret'
            })
            
            assert auth_result is True
            print("✓ Google Drive認証成功")
        
        # 3. フォルダリストテスト
        with patch.object(gdrive_port, 'service') as mock_service:
            mock_files = MagicMock()
            mock_files.list.return_value.execute.return_value = {
                'files': [
                    {'id': 'folder1', 'name': 'Research Papers', 'mimeType': 'application/vnd.google-apps.folder'},
                    {'id': 'folder2', 'name': 'Datasets', 'mimeType': 'application/vnd.google-apps.folder'}
                ]
            }
            mock_service.files.return_value = mock_files
            
            folders = await gdrive_port.list_folders()
            
            assert len(folders) == 2
            assert folders[0]['name'] == 'Research Papers'
            assert folders[1]['name'] == 'Datasets'
            print("✓ フォルダリスト取得成功")
        
        # 4. ファイル同期テスト
        with patch.object(gdrive_port, '_list_files_in_folder') as mock_list_files, \
             patch.object(gdrive_port, '_process_single_file') as mock_process_file:
            
            # ファイル一覧モック
            mock_list_files.return_value = [
                {'id': 'file1', 'name': 'paper1.pdf', 'mimeType': 'application/pdf', 'size': '1024000'},
                {'id': 'file2', 'name': 'data.csv', 'mimeType': 'text/csv', 'size': '512000'}
            ]
            
            # ファイル処理モック
            mock_process_file.return_value = None
            
            # 同期実行
            job_id = "sync_test_job"
            folder_id = "test_folder_123"
            
            result = await gdrive_port.sync_folder(folder_id, job_id, mock_user_context)
            
            assert result.status == JobStatus.COMPLETED
            assert result.total_files == 2
            assert result.successful_files == 2
            assert result.failed_files == 0
            print("✓ フォルダ同期成功")
        
        print("✓ Google Drive Port完全ワークフローテスト完了")
    
    @pytest.mark.asyncio
    async def test_google_drive_port_error_handling(self, gdrive_config, mock_user_context):
        """Google Drive Portエラーハンドリングテスト"""
        print("\n=== Google Drive Portエラーハンドリングテスト開始 ===")
        
        gdrive_port = GoogleDrivePortImpl(gdrive_config)
        
        # 1. 認証エラーテスト
        with patch('agent.source.interfaces.google_drive_impl.GOOGLE_DRIVE_AVAILABLE', False):
            auth_result = await gdrive_port.authenticate({'token': 'test_token'})
            assert auth_result is False
            print("✓ 認証エラーハンドリング成功")
        
        # 2. 同期エラーテスト
        with patch.object(gdrive_port, '_list_files_in_folder') as mock_list_files:
            # ファイル一覧取得エラー
            mock_list_files.side_effect = Exception("API quota exceeded")
            
            result = await gdrive_port.sync_folder("error_folder", "error_job", mock_user_context)
            
            assert result.status == JobStatus.FAILED
            assert len(result.errors) > 0
            print("✓ 同期エラーハンドリング成功")
        
        print("✓ Google Drive Portエラーハンドリングテスト完了")


class TestInstanceBVectorSearchPortIntegration:
    """Instance B - VectorSearchPort統合テストクラス"""
    
    @pytest.fixture
    def vector_config(self):
        """Vector Search設定"""
        return VectorSearchConfig(
            provider='chroma',
            embedding_model='sentence-transformers/all-MiniLM-L6-v2',
            collection_name='test_collection',
            dimension=384
        )
    
    @pytest.fixture
    def mock_documents(self):
        """テスト用ドキュメントデータ"""
        return [
            DocumentMetadata(
                id="doc1",
                title="機械学習による研究データ分析",
                content_type="paper",
                file_path="/data/paper/ml_research.pdf",
                file_size=2048576,
                created_at=datetime.now(),
                metadata={'authors': ['田中太郎', '佐藤花子'], 'keywords': ['機械学習', '研究データ', '分析']}
            ),
            DocumentMetadata(
                id="doc2",
                title="深層学習データセット",
                content_type="dataset",
                file_path="/data/datasets/deep_learning/data.csv",
                file_size=1024000,
                created_at=datetime.now(),
                metadata={'dataset_type': 'training', 'size': '10000 samples'}
            ),
            DocumentMetadata(
                id="doc3",
                title="AI研究ポスター発表",
                content_type="poster",
                file_path="/data/poster/ai_research.pdf",
                file_size=512000,
                created_at=datetime.now(),
                metadata={'conference': 'AI Conference 2024', 'category': 'research'}
            )
        ]
    
    @pytest.mark.asyncio
    async def test_vector_search_port_full_workflow(self, vector_config, mock_documents):
        """Vector Search Port完全ワークフローテスト"""
        print("\n=== Vector Search Port完全ワークフローテスト開始 ===")
        
        # 1. ポート初期化
        vector_port = ChromaVectorSearchPort(vector_config)
        assert vector_port.config == vector_config
        print("✓ Vector Search Port初期化成功")
        
        # 2. ヘルスチェックテスト
        with patch.object(vector_port, 'client') as mock_client:
            mock_client.heartbeat.return_value = True
            
            health_status = await vector_port.health_check()
            assert health_status == HealthStatus.HEALTHY
            print("✓ ヘルスチェック成功")
        
        # 3. ドキュメントインデックステスト
        with patch.object(vector_port, '_get_embeddings') as mock_embeddings, \
             patch.object(vector_port, 'collection') as mock_collection:
            
            # 埋め込みベクトルモック
            mock_embeddings.return_value = [
                [0.1, 0.2, 0.3] + [0.0] * 381,  # 384次元
                [0.2, 0.3, 0.4] + [0.0] * 381,
                [0.3, 0.4, 0.5] + [0.0] * 381
            ]
            
            # インデックス実行
            await vector_port.index_documents(mock_documents)
            
            # コレクションに追加されたことを確認
            mock_collection.add.assert_called_once()
            print("✓ ドキュメントインデックス成功")
        
        # 4. 検索テスト
        with patch.object(vector_port, '_get_embeddings') as mock_embeddings, \
             patch.object(vector_port, 'collection') as mock_collection:
            
            # クエリ埋め込みモック
            mock_embeddings.return_value = [[0.15, 0.25, 0.35] + [0.0] * 381]
            
            # 検索結果モック
            mock_collection.query.return_value = {
                'ids': [['doc1', 'doc2']],
                'distances': [[0.1, 0.3]],
                'metadatas': [[
                    {'title': '機械学習による研究データ分析', 'content_type': 'paper'},
                    {'title': '深層学習データセット', 'content_type': 'dataset'}
                ]]
            }
            
            # 検索実行
            search_request = SearchRequest(
                query="機械学習 研究データ",
                mode=SearchMode.VECTOR,
                max_results=10
            )
            
            search_result = await vector_port.search(search_request)
            
            assert len(search_result.results) == 2
            assert search_result.results[0].id == 'doc1'
            assert search_result.results[1].id == 'doc2'
            print("✓ ベクトル検索成功")
        
        print("✓ Vector Search Port完全ワークフローテスト完了")
    
    @pytest.mark.asyncio
    async def test_vector_search_port_batch_processing(self, vector_config, mock_documents):
        """Vector Search Portバッチ処理テスト"""
        print("\n=== Vector Search Portバッチ処理テスト開始 ===")
        
        vector_port = ChromaVectorSearchPort(vector_config)
        
        # 大量ドキュメントシミュレーション
        large_document_batch = []
        for i in range(100):
            large_document_batch.append(DocumentMetadata(
                id=f"batch_doc_{i}",
                title=f"バッチドキュメント {i}",
                content_type="paper",
                file_path=f"/data/batch/doc_{i}.pdf",
                file_size=1024000,
                created_at=datetime.now(),
                metadata={'batch_id': i}
            ))
        
        with patch.object(vector_port, '_get_embeddings') as mock_embeddings, \
             patch.object(vector_port, 'collection') as mock_collection:
            
            # 埋め込みベクトルモック（大量）
            mock_embeddings.return_value = [
                [0.1 * i, 0.2 * i, 0.3 * i] + [0.0] * 381
                for i in range(100)
            ]
            
            # バッチインデックス実行
            await vector_port.index_documents(large_document_batch)
            
            # バッチ処理確認
            mock_collection.add.assert_called_once()
            call_args = mock_collection.add.call_args
            assert len(call_args[1]['ids']) == 100
            print("✓ バッチインデックス成功")
        
        print("✓ Vector Search Portバッチ処理テスト完了")


class TestInstanceCAuthenticationPortIntegration:
    """Instance C - AuthenticationPort統合テストクラス"""
    
    @pytest.fixture
    def auth_config(self):
        """Authentication設定"""
        return AuthConfig(
            provider='google',
            session_timeout_hours=24,
            allowed_domains=['university.ac.jp', 'research.org']
        )
    
    @pytest.fixture
    def mock_user_info(self):
        """テスト用ユーザー情報"""
        return {
            'id': 'user123',
            'email': 'test@university.ac.jp',
            'name': 'Test User',
            'verified_email': True,
            'picture': 'https://example.com/picture.jpg'
        }
    
    @pytest.mark.asyncio
    async def test_authentication_port_full_workflow(self, auth_config, mock_user_info):
        """Authentication Port完全ワークフローテスト"""
        print("\n=== Authentication Port完全ワークフローテスト開始 ===")
        
        # 1. 認証プロバイダー初期化
        auth_provider = GoogleOAuth2Authentication(auth_config)
        assert auth_provider.config == auth_config
        print("✓ Authentication Provider初期化成功")
        
        # 2. ユーザー管理初期化
        user_manager = DatabaseUserManagement(auth_config)
        assert user_manager.config == auth_config
        print("✓ User Management初期化成功")
        
        # 3. 認可システム初期化
        authorization = RoleBasedAuthorization(auth_config)
        assert authorization.config == auth_config
        print("✓ Authorization初期化成功")
        
        # 4. 認証フローテスト
        with patch.object(auth_provider, '_verify_google_token') as mock_verify:
            mock_verify.return_value = mock_user_info
            
            # 認証実行
            user_context = await auth_provider.authenticate_user("test_token")
            
            assert user_context is not None
            assert user_context.email == mock_user_info['email']
            assert user_context.user_id == mock_user_info['id']
            print("✓ 認証フロー成功")
        
        # 5. ユーザー管理テスト
        with patch.object(user_manager, '_get_database_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_db.return_value.__enter__.return_value.cursor.return_value = mock_cursor
            
            # ユーザー作成
            await user_manager.create_user(mock_user_info)
            
            # ユーザー取得
            mock_cursor.fetchone.return_value = (
                mock_user_info['id'],
                mock_user_info['email'],
                mock_user_info['name'],
                'user',
                datetime.now()
            )
            
            user_data = await user_manager.get_user(mock_user_info['id'])
            assert user_data is not None
            assert user_data['email'] == mock_user_info['email']
            print("✓ ユーザー管理成功")
        
        # 6. 認可テスト
        user_context = UserContext(
            user_id=mock_user_info['id'],
            email=mock_user_info['email'],
            permissions=['read', 'write'],
            session_id='test_session'
        )
        
        # 権限チェック
        has_read_permission = await authorization.check_permission(user_context, 'read')
        has_admin_permission = await authorization.check_permission(user_context, 'admin')
        
        assert has_read_permission is True
        assert has_admin_permission is False
        print("✓ 認可システム成功")
        
        print("✓ Authentication Port完全ワークフローテスト完了")
    
    @pytest.mark.asyncio
    async def test_authentication_port_security(self, auth_config, mock_user_info):
        """Authentication Portセキュリティテスト"""
        print("\n=== Authentication Portセキュリティテスト開始 ===")
        
        auth_provider = GoogleOAuth2Authentication(auth_config)
        
        # 1. 不正トークンテスト
        with patch.object(auth_provider, '_verify_google_token') as mock_verify:
            mock_verify.side_effect = Exception("Invalid token")
            
            user_context = await auth_provider.authenticate_user("invalid_token")
            assert user_context is None
            print("✓ 不正トークン拒否成功")
        
        # 2. ドメイン制限テスト
        with patch.object(auth_provider, '_verify_google_token') as mock_verify:
            invalid_domain_user = mock_user_info.copy()
            invalid_domain_user['email'] = 'hacker@evil.com'
            mock_verify.return_value = invalid_domain_user
            
            user_context = await auth_provider.authenticate_user("test_token")
            assert user_context is None
            print("✓ ドメイン制限成功")
        
        # 3. セッション管理テスト
        user_manager = DatabaseUserManagement(auth_config)
        
        with patch.object(user_manager, '_get_database_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_db.return_value.__enter__.return_value.cursor.return_value = mock_cursor
            
            # セッション作成
            session_id = await user_manager.create_session(mock_user_info['id'])
            assert session_id is not None
            print("✓ セッション作成成功")
            
            # セッション期限切れシミュレーション
            expired_time = datetime.now() - timedelta(hours=25)  # 24時間 + 1時間
            mock_cursor.fetchone.return_value = (
                session_id,
                mock_user_info['id'],
                expired_time
            )
            
            is_valid = await user_manager.validate_session(session_id)
            assert is_valid is False
            print("✓ セッション期限切れ検出成功")
        
        print("✓ Authentication Portセキュリティテスト完了")


class TestInstanceDPaaSOrchestrationPortIntegration:
    """Instance D - PaaSOrchestrationPort統合テストクラス"""
    
    @pytest.fixture
    def paas_config(self):
        """PaaS設定"""
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
    
    @pytest.mark.asyncio
    async def test_paas_orchestration_port_full_workflow(self, paas_config):
        """PaaS Orchestration Port完全ワークフローテスト"""
        print("\n=== PaaS Orchestration Port完全ワークフローテスト開始 ===")
        
        # 1. オーケストレーター初期化
        orchestrator = PaaSOrchestrationImpl(paas_config)
        assert orchestrator.config == paas_config
        print("✓ PaaS Orchestrator初期化成功")
        
        # 2. システム初期化テスト
        with patch.object(orchestrator, '_initialize_google_drive') as mock_gdrive_init, \
             patch.object(orchestrator, '_initialize_vector_search') as mock_vector_init, \
             patch.object(orchestrator, '_initialize_authentication') as mock_auth_init:
            
            mock_gdrive_init.return_value = True
            mock_vector_init.return_value = True
            mock_auth_init.return_value = True
            
            # 初期化実行
            init_result = await orchestrator.initialize_system()
            
            assert init_result is True
            mock_gdrive_init.assert_called_once()
            mock_vector_init.assert_called_once()
            mock_auth_init.assert_called_once()
            print("✓ システム初期化成功")
        
        # 3. ヘルスチェック統合テスト
        with patch.object(orchestrator, '_check_google_drive_health') as mock_gdrive_health, \
             patch.object(orchestrator, '_check_vector_search_health') as mock_vector_health, \
             patch.object(orchestrator, '_check_authentication_health') as mock_auth_health, \
             patch.object(orchestrator, '_check_existing_system_health') as mock_existing_health:
            
            mock_gdrive_health.return_value = HealthStatus.HEALTHY
            mock_vector_health.return_value = HealthStatus.HEALTHY
            mock_auth_health.return_value = HealthStatus.HEALTHY
            mock_existing_health.return_value = HealthStatus.HEALTHY
            
            # ヘルスチェック実行
            health_status = await orchestrator.check_system_health()
            
            assert health_status == HealthStatus.HEALTHY
            print("✓ 統合ヘルスチェック成功")
        
        # 4. 設定管理テスト
        # 機能有効化/無効化テスト
        original_gdrive_enabled = orchestrator.config.enable_google_drive
        orchestrator.config.enable_google_drive = False
        
        # 無効化された機能のヘルスチェック
        with patch.object(orchestrator, '_check_existing_system_health') as mock_existing_health:
            mock_existing_health.return_value = HealthStatus.HEALTHY
            
            health_status = await orchestrator.check_system_health()
            
            # Google Drive無効でも他の機能で動作継続
            assert health_status == HealthStatus.HEALTHY
            print("✓ 機能無効化時の動作継続成功")
        
        # 設定復元
        orchestrator.config.enable_google_drive = original_gdrive_enabled
        
        # 5. システム統計情報テスト
        with patch.object(orchestrator, '_get_system_statistics') as mock_stats:
            mock_stats.return_value = {
                'total_documents': 32,
                'total_size_mb': 293.8,
                'active_features': ['google_drive', 'vector_search', 'authentication'],
                'uptime_hours': 24.5
            }
            
            stats = await orchestrator.get_system_statistics()
            
            assert stats['total_documents'] == 32
            assert 'google_drive' in stats['active_features']
            assert 'vector_search' in stats['active_features']
            print("✓ システム統計情報取得成功")
        
        print("✓ PaaS Orchestration Port完全ワークフローテスト完了")
    
    @pytest.mark.asyncio
    async def test_paas_orchestration_port_error_recovery(self, paas_config):
        """PaaS Orchestration Portエラー回復テスト"""
        print("\n=== PaaS Orchestration Portエラー回復テスト開始 ===")
        
        orchestrator = PaaSOrchestrationImpl(paas_config)
        
        # 1. 部分的初期化失敗テスト
        with patch.object(orchestrator, '_initialize_google_drive') as mock_gdrive_init, \
             patch.object(orchestrator, '_initialize_vector_search') as mock_vector_init, \
             patch.object(orchestrator, '_initialize_authentication') as mock_auth_init:
            
            mock_gdrive_init.return_value = True
            mock_vector_init.side_effect = Exception("Vector search initialization failed")
            mock_auth_init.return_value = True
            
            # 初期化実行（部分的失敗）
            init_result = await orchestrator.initialize_system()
            
            # 部分的失敗でも継続
            assert init_result is True  # 他の機能は動作継続
            print("✓ 部分的初期化失敗からの回復成功")
        
        # 2. ヘルスチェック障害時の対応テスト
        with patch.object(orchestrator, '_check_google_drive_health') as mock_gdrive_health, \
             patch.object(orchestrator, '_check_vector_search_health') as mock_vector_health, \
             patch.object(orchestrator, '_check_existing_system_health') as mock_existing_health:
            
            mock_gdrive_health.return_value = HealthStatus.UNHEALTHY
            mock_vector_health.side_effect = Exception("Vector search unavailable")
            mock_existing_health.return_value = HealthStatus.HEALTHY
            
            # ヘルスチェック実行
            health_status = await orchestrator.check_system_health()
            
            # 既存システムが健全なら継続動作
            assert health_status == HealthStatus.DEGRADED
            print("✓ 障害時の劣化動作成功")
        
        # 3. 設定変更時の動的再構成テスト
        # 機能の動的無効化
        orchestrator.config.enable_google_drive = False
        orchestrator.config.enable_vector_search = False
        
        with patch.object(orchestrator, '_check_existing_system_health') as mock_existing_health:
            mock_existing_health.return_value = HealthStatus.HEALTHY
            
            # 最小限機能でのヘルスチェック
            health_status = await orchestrator.check_system_health()
            
            assert health_status == HealthStatus.HEALTHY
            print("✓ 動的機能無効化での動作継続成功")
        
        print("✓ PaaS Orchestration Portエラー回復テスト完了")


class TestCrossPortIntegration:
    """クロスポート統合テストクラス"""
    
    @pytest.mark.asyncio
    async def test_all_ports_integration_scenario(self):
        """全ポート統合シナリオテスト"""
        print("\n=== 全ポート統合シナリオテスト開始 ===")
        
        # 設定準備
        paas_config = PaaSConfig(
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
                collection_name='integration_test',
                dimension=384
            ),
            auth=AuthConfig(
                provider='google',
                session_timeout_hours=24,
                allowed_domains=['university.ac.jp']
            )
        )
        
        # 各ポート初期化
        orchestrator = PaaSOrchestrationImpl(paas_config)
        gdrive_port = GoogleDrivePortImpl(paas_config.google_drive)
        vector_port = ChromaVectorSearchPort(paas_config.vector_search)
        auth_provider = GoogleOAuth2Authentication(paas_config.auth)
        
        # 統合シナリオ実行
        print("--- 統合シナリオ: 認証 → Google Drive同期 → ベクトル検索 ---")
        
        # 1. 認証
        with patch.object(auth_provider, '_verify_google_token') as mock_verify:
            mock_verify.return_value = {
                'id': 'integration_user',
                'email': 'integration@university.ac.jp',
                'name': 'Integration Test User'
            }
            
            user_context = await auth_provider.authenticate_user("integration_token")
            assert user_context is not None
            print("  ✓ 認証完了")
        
        # 2. Google Drive同期
        with patch.object(gdrive_port, '_list_files_in_folder') as mock_list_files, \
             patch.object(gdrive_port, '_process_single_file') as mock_process_file:
            
            mock_list_files.return_value = [
                {'id': 'integration_file', 'name': 'integration_test.pdf', 'mimeType': 'application/pdf'}
            ]
            mock_process_file.return_value = None
            
            sync_result = await gdrive_port.sync_folder("integration_folder", "integration_job", user_context)
            assert sync_result.status == JobStatus.COMPLETED
            print("  ✓ Google Drive同期完了")
        
        # 3. ベクトル検索インデックス更新
        test_documents = [
            DocumentMetadata(
                id="integration_doc",
                title="統合テストドキュメント",
                content_type="paper",
                file_path="/data/integration_test.pdf",
                file_size=1024000,
                created_at=datetime.now(),
                metadata={'source': 'google_drive', 'user': user_context.user_id}
            )
        ]
        
        with patch.object(vector_port, '_get_embeddings') as mock_embeddings, \
             patch.object(vector_port, 'collection') as mock_collection:
            
            mock_embeddings.return_value = [[0.1, 0.2, 0.3] + [0.0] * 381]
            
            await vector_port.index_documents(test_documents)
            mock_collection.add.assert_called_once()
            print("  ✓ ベクトル検索インデックス更新完了")
        
        # 4. 統合検索
        with patch.object(vector_port, '_get_embeddings') as mock_embeddings, \
             patch.object(vector_port, 'collection') as mock_collection:
            
            mock_embeddings.return_value = [[0.15, 0.25, 0.35] + [0.0] * 381]
            mock_collection.query.return_value = {
                'ids': [['integration_doc']],
                'distances': [[0.1]],
                'metadatas': [[{'title': '統合テストドキュメント', 'content_type': 'paper'}]]
            }
            
            search_request = SearchRequest(
                query="統合テスト",
                mode=SearchMode.VECTOR,
                max_results=10
            )
            
            search_result = await vector_port.search(search_request)
            assert len(search_result.results) == 1
            print("  ✓ 統合検索完了")
        
        # 5. システム統計情報統合
        with patch.object(orchestrator, '_get_system_statistics') as mock_stats:
            mock_stats.return_value = {
                'total_documents': 33,  # 統合テストで1つ追加
                'total_size_mb': 294.8,
                'active_features': ['google_drive', 'vector_search', 'authentication'],
                'integration_tests_passed': 1
            }
            
            stats = await orchestrator.get_system_statistics()
            assert stats['integration_tests_passed'] == 1
            print("  ✓ システム統計情報統合完了")
        
        print("✓ 全ポート統合シナリオテスト完了")


if __name__ == "__main__":
    """各ポート統合テストスイート実行"""
    print("=== Instance E - 各ポート統合テストスイート実行 ===")
    
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
        
        print(f"\n各ポート統合テストスイート結果: {'SUCCESS' if result.returncode == 0 else 'FAILED'}")
        sys.exit(result.returncode)
        
    except Exception as e:
        print(f"統合テストスイート実行エラー: {e}")
        sys.exit(1)