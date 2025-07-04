"""
Instance E 統合テストスイート - UnifiedPaaSInterface完全テスト

このテストスイートは、Instance E（統合テスト・デプロイ）の責任範囲として
UnifiedPaaSInterfaceの全機能を統合的にテストします。

実行方法:
```bash
# 統合テストスイート実行
uv run pytest agent/tests/test_instance_e_unified_integration.py -v

# 詳細ログ付き実行
uv run pytest agent/tests/test_instance_e_unified_integration.py -v -s --log-cli-level=INFO

# カバレッジ付き実行
uv run pytest agent/tests/test_instance_e_unified_integration.py --cov=agent.source.interfaces --cov-report=html -v
```
"""

import asyncio
import tempfile
import pytest
import json
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any, List, Optional

# テスト対象のUnifiedPaaSInterface
from agent.source.interfaces.unified_paas_impl import UnifiedPaaSImpl
from agent.source.interfaces.data_models import (
    PaaSConfig,
    SearchMode,
    SearchRequest,
    SearchResultCollection,
    DocumentIngestionRequest,
    DocumentIngestionResult,
    SystemStatistics,
    HealthStatus,
    UserContext,
    DocumentContent,
    DocumentMetadata,
    GoogleDriveConfig,
    VectorSearchConfig,
    AuthConfig
)
from agent.source.interfaces.config_manager import PaaSConfigManager


class TestUnifiedPaaSInterfaceIntegration:
    """UnifiedPaaSInterface統合テストクラス"""
    
    @pytest.fixture
    def full_config(self):
        """完全な統合テスト用設定"""
        return {
            'enable_google_drive': True,
            'enable_vector_search': True,
            'enable_authentication': True,
            'enable_monitoring': True,
            'google_drive': GoogleDriveConfig(
                credentials_path="/tmp/test_credentials.json",
                max_file_size_mb=100,
                supported_mime_types=['application/pdf', 'text/csv', 'application/json']
            ),
            'vector_search': VectorSearchConfig(
                provider='chroma',
                embedding_model='sentence-transformers/all-MiniLM-L6-v2',
                collection_name='research_documents'
            ),
            'auth': AuthConfig(
                provider='google',
                client_id='test_client_id',
                client_secret='test_client_secret', 
                redirect_uri='http://localhost:8000/auth/callback',
                allowed_domains=['university.ac.jp', 'research.org'],
                session_timeout_minutes=1440  # 24 hours
            )
        }
    
    @pytest.fixture
    def minimal_config(self):
        """最小限の統合テスト用設定（既存システムのみ）"""
        return {
            'enable_google_drive': False,
            'enable_vector_search': False,
            'enable_authentication': False,
            'enable_monitoring': False
        }
    
    @pytest.fixture
    def mock_user_context(self):
        """テスト用ユーザーコンテキスト"""
        return UserContext(
            user_id="test_user_123",
            email="test@university.ac.jp",
            permissions=['read', 'write', 'admin'],
            session_id="test_session_456"
        )
    
    @pytest.mark.asyncio
    async def test_unified_interface_full_feature_integration(self, full_config, mock_user_context):
        """UnifiedPaaSInterface全機能統合テスト"""
        print("\n=== UnifiedPaaSInterface全機能統合テスト開始 ===")
        
        # 1. 設定管理とインターフェース初期化
        config_manager = PaaSConfigManager()
        paas_config = PaaSConfig(**full_config)
        
        with patch.object(config_manager, 'load_config', return_value=paas_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
            
            # 初期化確認
            assert unified_interface.config_manager == config_manager
            print("✓ UnifiedPaaSInterface初期化成功")
        
        # 2. システム統計情報取得テスト
        with patch.object(unified_interface, '_get_existing_system_stats') as mock_existing_stats, \
             patch.object(unified_interface, '_get_vector_search_stats') as mock_vector_stats, \
             patch.object(unified_interface, '_get_google_drive_stats') as mock_gdrive_stats:
            
            # 模擬統計データ設定
            mock_existing_stats.return_value = {
                'total_documents': 32,
                'datasets': 4,
                'papers': 2,
                'posters': 2,
                'total_size_mb': 293.8
            }
            mock_vector_stats.return_value = {
                'total_embeddings': 28,
                'last_update': '2024-07-04T10:00:00Z'
            }
            mock_gdrive_stats.return_value = {
                'connected_folders': 3,
                'last_sync': '2024-07-04T09:30:00Z'
            }
            
            # 統計情報取得
            stats = await unified_interface.get_system_statistics(mock_user_context)
            
            # 統計データ確認
            assert isinstance(stats, SystemStatistics)
            assert stats.total_documents == 32
            assert stats.total_size_mb == 293.8
            assert stats.feature_status['google_drive'] == True
            assert stats.feature_status['vector_search'] == True
            print("✓ システム統計情報取得成功")
        
        # 3. ヘルスチェック統合テスト
        with patch.object(unified_interface, '_check_existing_system_health') as mock_existing_health, \
             patch.object(unified_interface, '_check_vector_search_health') as mock_vector_health, \
             patch.object(unified_interface, '_check_google_drive_health') as mock_gdrive_health:
            
            # 模擬ヘルスチェック結果
            mock_existing_health.return_value = HealthStatus.HEALTHY
            mock_vector_health.return_value = HealthStatus.HEALTHY
            mock_gdrive_health.return_value = HealthStatus.HEALTHY
            
            # ヘルスチェック実行
            health_status = await unified_interface.check_system_health(mock_user_context)
            
            # 結果確認
            assert health_status == HealthStatus.HEALTHY
            print("✓ システムヘルスチェック成功")
        
        print("✓ UnifiedPaaSInterface全機能統合テスト完了")
    
    @pytest.mark.asyncio
    async def test_unified_document_search_integration(self, full_config, mock_user_context):
        """統合ドキュメント検索テスト"""
        print("\n=== 統合ドキュメント検索テスト開始 ===")
        
        config_manager = PaaSConfigManager()
        paas_config = PaaSConfig(**full_config)
        
        with patch.object(config_manager, 'load_config', return_value=paas_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        # 検索クエリ設定
        search_request = SearchRequest(
            query="研究データ 機械学習",
            mode=SearchMode.HYBRID,
            max_results=10,
            include_metadata=True
        )
        
        # 各検索モードのテスト
        search_modes = [
            (SearchMode.KEYWORD_ONLY, "キーワード検索"),
            (SearchMode.SEMANTIC_ONLY, "ベクトル検索"),
            (SearchMode.HYBRID, "ハイブリッド検索")
        ]
        
        for mode, mode_name in search_modes:
            print(f"\n--- {mode_name}テスト ---")
            
            search_request.mode = mode
            
            with patch.object(unified_interface, '_search_existing_system') as mock_existing_search, \
                 patch.object(unified_interface, '_search_vector_system') as mock_vector_search:
                
                # 模擬検索結果
                mock_existing_results = [
                    DocumentMetadata(
                        id="doc_1",
                        title="機械学習による研究データ分析",
                        content_type="paper",
                        file_path="/data/paper/ml_research.pdf",
                        file_size=2048576,
                        created_at=datetime.now(),
                        metadata={'authors': ['田中太郎', '佐藤花子']}
                    ),
                    DocumentMetadata(
                        id="doc_2",
                        title="データセット: 機械学習実験結果",
                        content_type="dataset",
                        file_path="/data/datasets/ml_experiment/data.csv",
                        file_size=1024000,
                        created_at=datetime.now(),
                        metadata={'dataset_type': 'experimental'}
                    )
                ]
                
                mock_vector_results = [
                    DocumentMetadata(
                        id="doc_3",
                        title="深層学習アルゴリズムの比較研究",
                        content_type="paper",
                        file_path="/data/paper/deep_learning.pdf",
                        file_size=3072000,
                        created_at=datetime.now(),
                        metadata={'similarity_score': 0.85}
                    )
                ]
                
                if mode == SearchMode.KEYWORD_ONLY:
                    mock_existing_search.return_value = SearchResultCollection(
                        results=mock_existing_results,
                        total_results=2,
                        search_time_ms=150,
                        mode=mode
                    )
                    mock_vector_search.return_value = SearchResultCollection(results=[], total_results=0, search_time_ms=0, mode=mode)
                elif mode == SearchMode.SEMANTIC_ONLY:
                    mock_existing_search.return_value = SearchResultCollection(results=[], total_results=0, search_time_ms=0, mode=mode)
                    mock_vector_search.return_value = SearchResultCollection(
                        results=mock_vector_results,
                        total_results=1,
                        search_time_ms=200,
                        mode=mode
                    )
                else:  # HYBRID
                    mock_existing_search.return_value = SearchResultCollection(
                        results=mock_existing_results,
                        total_results=2,
                        search_time_ms=150,
                        mode=mode
                    )
                    mock_vector_search.return_value = SearchResultCollection(
                        results=mock_vector_results,
                        total_results=1,
                        search_time_ms=200,
                        mode=mode
                    )
                
                # 検索実行
                search_result = await unified_interface.search_documents(search_request, mock_user_context)
                
                # 結果確認
                assert isinstance(search_result, SearchResultCollection)
                assert search_result.mode == mode
                
                if mode == SearchMode.KEYWORD_ONLY:
                    assert search_result.total_results == 2
                    assert len(search_result.results) == 2
                elif mode == SearchMode.SEMANTIC_ONLY:
                    assert search_result.total_results == 1
                    assert len(search_result.results) == 1
                else:  # HYBRID
                    assert search_result.total_results == 3  # 両方の結果をマージ
                    assert len(search_result.results) == 3
                
                print(f"  ✓ {mode_name}: {search_result.total_results}件検索成功")
        
        print("✓ 統合ドキュメント検索テスト完了")
    
    @pytest.mark.asyncio
    async def test_unified_document_ingestion_integration(self, full_config, mock_user_context):
        """統合ドキュメント取り込みテスト"""
        print("\n=== 統合ドキュメント取り込みテスト開始 ===")
        
        config_manager = PaaSConfigManager()
        paas_config = PaaSConfig(**full_config)
        
        with patch.object(config_manager, 'load_config', return_value=paas_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        # 取り込みリクエスト設定
        ingestion_request = DocumentIngestionRequest(
            source_type="google_drive",
            source_id="folder_12345",
            auto_analyze=True,
            metadata={
                'folder_name': 'Research Papers 2024',
                'sync_mode': 'incremental'
            }
        )
        
        # 取り込み処理のモック
        with patch.object(unified_interface, '_ingest_from_google_drive') as mock_gdrive_ingest, \
             patch.object(unified_interface, '_ingest_from_upload') as mock_upload_ingest:
            
            # Google Drive取り込み結果設定
            mock_gdrive_ingest.return_value = DocumentIngestionResult(
                job_id="ingest_job_123",
                status="completed",
                total_files=5,
                processed_files=5,
                failed_files=0,
                processing_time_ms=3000,
                errors=[]
            )
            
            # 取り込み実行
            ingestion_result = await unified_interface.ingest_documents(ingestion_request, mock_user_context)
            
            # 結果確認
            assert isinstance(ingestion_result, DocumentIngestionResult)
            assert ingestion_result.status == "completed"
            assert ingestion_result.total_files == 5
            assert ingestion_result.processed_files == 5
            assert ingestion_result.failed_files == 0
            assert len(ingestion_result.errors) == 0
            
            print(f"✓ Google Drive取り込み成功: {ingestion_result.processed_files}/{ingestion_result.total_files}ファイル")
        
        # アップロード取り込みテスト
        upload_request = DocumentIngestionRequest(
            source_type="upload",
            source_id="upload_batch_789",
            auto_analyze=True,
            metadata={
                'upload_session': 'session_456',
                'category': 'dataset'
            }
        )
        
        with patch.object(unified_interface, '_ingest_from_upload') as mock_upload_ingest:
            
            mock_upload_ingest.return_value = DocumentIngestionResult(
                job_id="upload_job_456",
                status="completed",
                total_files=2,
                processed_files=2,
                failed_files=0,
                processing_time_ms=1500,
                errors=[]
            )
            
            upload_result = await unified_interface.ingest_documents(upload_request, mock_user_context)
            
            assert upload_result.status == "completed"
            assert upload_result.processed_files == 2
            print(f"✓ アップロード取り込み成功: {upload_result.processed_files}/{upload_result.total_files}ファイル")
        
        print("✓ 統合ドキュメント取り込みテスト完了")
    
    @pytest.mark.asyncio
    async def test_fallback_mechanism_integration(self, minimal_config, mock_user_context):
        """フォールバック機能統合テスト"""
        print("\n=== フォールバック機能統合テスト開始 ===")
        
        # 最小限設定（新機能無効）でのテスト
        config_manager = PaaSConfigManager()
        paas_config = PaaSConfig(**minimal_config)
        
        with patch.object(config_manager, 'load_config', return_value=paas_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        # 1. 検索フォールバックテスト
        search_request = SearchRequest(
            query="研究データ",
            mode=SearchMode.HYBRID,  # 高機能モードを要求
            max_results=10
        )
        
        with patch.object(unified_interface, '_search_existing_system') as mock_existing_search:
            
            # 既存システムでの検索結果
            mock_existing_search.return_value = SearchResult(
                results=[
                    DocumentMetadata(
                        id="fallback_doc_1",
                        title="フォールバック検索結果",
                        content_type="paper",
                        file_path="/data/paper/fallback.pdf",
                        file_size=1024000,
                        created_at=datetime.now()
                    )
                ],
                total_results=1,
                search_time_ms=100,
                mode=SearchMode.KEYWORD  # 既存システムのキーワード検索にフォールバック
            )
            
            # 検索実行
            search_result = await unified_interface.search_documents(search_request, mock_user_context)
            
            # フォールバック確認
            assert search_result.mode == SearchMode.KEYWORD  # ハイブリッドからキーワードにフォールバック
            assert search_result.total_results == 1
            print("✓ 検索フォールバック成功: HYBRID → KEYWORD")
        
        # 2. 取り込みフォールバックテスト
        ingestion_request = DocumentIngestionRequest(
            source_type="google_drive",  # 無効化された機能を要求
            source_id="folder_123",
            auto_analyze=True
        )
        
        with patch.object(unified_interface, '_ingest_from_upload') as mock_upload_fallback:
            
            # アップロード取り込みにフォールバック
            mock_upload_fallback.return_value = DocumentIngestionResult(
                job_id="fallback_job_789",
                status="completed",
                total_files=1,
                processed_files=1,
                failed_files=0,
                processing_time_ms=500,
                errors=[]
            )
            
            # 取り込み実行（フォールバック）
            ingestion_result = await unified_interface.ingest_documents(ingestion_request, mock_user_context)
            
            # フォールバック確認
            assert ingestion_result.status == "completed"
            assert ingestion_result.processed_files == 1
            print("✓ 取り込みフォールバック成功: Google Drive → Upload")
        
        # 3. 統計情報フォールバックテスト
        with patch.object(unified_interface, '_get_existing_system_stats') as mock_existing_stats:
            
            mock_existing_stats.return_value = {
                'total_documents': 32,
                'datasets': 4,
                'papers': 2,
                'posters': 2,
                'total_size_mb': 293.8
            }
            
            # 統計情報取得
            stats = await unified_interface.get_system_statistics(mock_user_context)
            
            # フォールバック確認（新機能の統計はNoneまたはデフォルト値）
            assert stats.total_documents == 32
            assert stats.feature_status['google_drive'] == False
            assert stats.feature_status['vector_search'] == False
            print("✓ 統計情報フォールバック成功: 既存システムのみ")
        
        print("✓ フォールバック機能統合テスト完了")
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, full_config, mock_user_context):
        """エラーハンドリングと回復テスト"""
        print("\n=== エラーハンドリングと回復テスト開始 ===")
        
        config_manager = PaaSConfigManager()
        paas_config = PaaSConfig(**full_config)
        
        with patch.object(config_manager, 'load_config', return_value=paas_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        # 1. 検索エラー回復テスト
        search_request = SearchRequest(
            query="test query",
            mode=SearchMode.VECTOR,
            max_results=10
        )
        
        with patch.object(unified_interface, '_search_vector_system') as mock_vector_search, \
             patch.object(unified_interface, '_search_existing_system') as mock_existing_search:
            
            # ベクトル検索でエラー発生
            mock_vector_search.side_effect = Exception("Vector search service unavailable")
            
            # 既存システムでの検索結果（フォールバック）
            mock_existing_search.return_value = SearchResult(
                results=[
                    DocumentMetadata(
                        id="recovery_doc_1",
                        title="回復検索結果",
                        content_type="paper",
                        file_path="/data/paper/recovery.pdf",
                        file_size=1024000,
                        created_at=datetime.now()
                    )
                ],
                total_results=1,
                search_time_ms=120,
                mode=SearchMode.KEYWORD
            )
            
            # 検索実行（エラー回復）
            search_result = await unified_interface.search_documents(search_request, mock_user_context)
            
            # エラー回復確認
            assert search_result.mode == SearchMode.KEYWORD  # ベクトル検索からキーワード検索にフォールバック
            assert search_result.total_results == 1
            print("✓ 検索エラー回復成功: Vector検索エラー → Keyword検索フォールバック")
        
        # 2. 取り込みエラー回復テスト
        ingestion_request = DocumentIngestionRequest(
            source_type="google_drive",
            source_id="folder_error",
            auto_analyze=True
        )
        
        with patch.object(unified_interface, '_ingest_from_google_drive') as mock_gdrive_ingest:
            
            # Google Drive取り込みでエラー発生
            mock_gdrive_ingest.return_value = DocumentIngestionResult(
                job_id="error_recovery_job",
                status="partial_failure",
                total_files=5,
                processed_files=3,
                failed_files=2,
                processing_time_ms=4000,
                errors=[
                    "Failed to download file_1.pdf: Network timeout",
                    "Failed to process file_2.csv: Invalid format"
                ]
            )
            
            # 取り込み実行（部分的失敗）
            ingestion_result = await unified_interface.ingest_documents(ingestion_request, mock_user_context)
            
            # 部分的失敗処理確認
            assert ingestion_result.status == "partial_failure"
            assert ingestion_result.processed_files == 3
            assert ingestion_result.failed_files == 2
            assert len(ingestion_result.errors) == 2
            print(f"✓ 取り込みエラー回復成功: {ingestion_result.processed_files}件成功, {ingestion_result.failed_files}件失敗")
        
        # 3. ヘルスチェックエラー回復テスト
        with patch.object(unified_interface, '_check_vector_search_health') as mock_vector_health, \
             patch.object(unified_interface, '_check_existing_system_health') as mock_existing_health:
            
            # ベクトル検索ヘルスチェックでエラー
            mock_vector_health.side_effect = Exception("Vector search health check failed")
            mock_existing_health.return_value = HealthStatus.HEALTHY
            
            # ヘルスチェック実行
            health_status = await unified_interface.check_system_health(mock_user_context)
            
            # 部分的ヘルス確認
            assert health_status == HealthStatus.DEGRADED  # 一部機能に問題があるが動作継続
            print("✓ ヘルスチェックエラー回復成功: 一部機能エラー → DEGRADED状態")
        
        print("✓ エラーハンドリングと回復テスト完了")
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_stress(self, full_config, mock_user_context):
        """並行操作ストレステスト"""
        print("\n=== 並行操作ストレステスト開始 ===")
        
        config_manager = PaaSConfigManager()
        paas_config = PaaSConfig(**full_config)
        
        with patch.object(config_manager, 'load_config', return_value=paas_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        # 並行検索タスク作成
        search_tasks = []
        for i in range(10):
            search_request = SearchRequest(
                query=f"test query {i}",
                mode=SearchMode.KEYWORD,
                max_results=5
            )
            search_tasks.append(unified_interface.search_documents(search_request, mock_user_context))
        
        # 並行統計情報取得タスク
        stats_tasks = []
        for i in range(5):
            stats_tasks.append(unified_interface.get_system_statistics(mock_user_context))
        
        # 並行ヘルスチェックタスク
        health_tasks = []
        for i in range(3):
            health_tasks.append(unified_interface.check_system_health(mock_user_context))
        
        # モック設定
        with patch.object(unified_interface, '_search_existing_system') as mock_search, \
             patch.object(unified_interface, '_get_existing_system_stats') as mock_stats, \
             patch.object(unified_interface, '_check_existing_system_health') as mock_health:
            
            # 検索結果モック
            mock_search.return_value = SearchResult(
                results=[],
                total_results=0,
                search_time_ms=50,
                mode=SearchMode.KEYWORD
            )
            
            # 統計情報モック
            mock_stats.return_value = {
                'total_documents': 32,
                'datasets': 4,
                'papers': 2,
                'posters': 2,
                'total_size_mb': 293.8
            }
            
            # ヘルスチェックモック
            mock_health.return_value = HealthStatus.HEALTHY
            
            # 全タスクを並行実行
            all_tasks = search_tasks + stats_tasks + health_tasks
            start_time = datetime.now()
            
            results = await asyncio.gather(*all_tasks, return_exceptions=True)
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            # 結果確認
            successful_tasks = sum(1 for result in results if not isinstance(result, Exception))
            failed_tasks = len(results) - successful_tasks
            
            assert successful_tasks >= len(all_tasks) * 0.9  # 90%以上成功
            assert execution_time < 5.0  # 5秒以内で完了
            
            print(f"✓ 並行操作ストレステスト完了: {successful_tasks}/{len(all_tasks)}タスク成功, 実行時間: {execution_time:.2f}秒")
        
        print("✓ 並行操作ストレステスト完了")


if __name__ == "__main__":
    """UnifiedPaaSInterface統合テストスイート実行"""
    print("=== Instance E - UnifiedPaaSInterface統合テストスイート実行 ===")
    
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
        
        print(f"\nUnifiedPaaSInterface統合テストスイート結果: {'SUCCESS' if result.returncode == 0 else 'FAILED'}")
        sys.exit(result.returncode)
        
    except Exception as e:
        print(f"統合テストスイート実行エラー: {e}")
        sys.exit(1)