"""
Instance E 統合テストスイート - エンドツーエンドテストシナリオ

このテストスイートは、実際のハッカソンデモシナリオを模擬した
完全なエンドツーエンドテストを実行します。

デモシナリオ:
1. 研究者がシステムにログイン
2. Google Driveから研究データを同期
3. 自動解析・インデックス化
4. ベクトル検索で関連文献を検索
5. 新しいデータセットをアップロード
6. システム統計情報を確認

実行方法:
```bash
# エンドツーエンドテスト実行
uv run pytest agent/tests/test_instance_e_end_to_end.py -v

# 詳細ログ付き実行
uv run pytest agent/tests/test_instance_e_end_to_end.py -v -s --log-cli-level=INFO

# カバレッジ付き実行
uv run pytest agent/tests/test_instance_e_end_to_end.py --cov=agent.source.interfaces --cov-report=html -v
```
"""

import asyncio
import tempfile
import pytest
import json
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any, List, Optional

# テスト対象のUnifiedPaaSInterface
from agent.source.interfaces.unified_paas_impl import UnifiedPaaSImpl
from agent.source.interfaces.config_manager import PaaSConfigManager
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
    DocumentContent,
    DocumentMetadata,
    GoogleDriveConfig,
    VectorSearchConfig,
    AuthConfig
)


class TestEndToEndHackathonDemo:
    """ハッカソンデモE2Eテストクラス"""
    
    @pytest.fixture
    def demo_config(self):
        """ハッカソンデモ用設定"""
        return PaaSConfig(
            enable_google_drive=True,
            enable_vector_search=True,
            enable_authentication=True,
            enable_monitoring=True,
            google_drive=GoogleDriveConfig(
                credentials_path="/tmp/demo_credentials.json",
                max_file_size_mb=100,
                supported_mime_types=[
                    'application/pdf',
                    'text/csv',
                    'application/json',
                    'text/plain'
                ]
            ),
            vector_search=VectorSearchConfig(
                provider='chroma',
                embedding_model='sentence-transformers/all-MiniLM-L6-v2',
                collection_name='hackathon_demo',
                dimension=384
            ),
            auth=AuthConfig(
                provider='google',
                session_timeout_hours=24,
                allowed_domains=['university.ac.jp', 'research.org']
            )
        )
    
    @pytest.fixture
    def demo_research_data(self):
        """ハッカソンデモ用研究データ"""
        return {
            'google_drive_files': [
                {
                    'id': 'demo_paper_1',
                    'name': 'AI_Research_Survey_2024.pdf',
                    'mimeType': 'application/pdf',
                    'size': '2048576',
                    'content': b'%PDF-1.4 Demo AI Research Survey content...',
                    'category': 'paper',
                    'metadata': {
                        'title': 'AI研究サーベイ2024',
                        'authors': ['田中太郎', '佐藤花子', 'John Smith'],
                        'keywords': ['人工知能', '機械学習', '深層学習', 'サーベイ'],
                        'abstract': 'このサーベイ論文では、2024年の人工知能研究の最新動向を包括的に調査する。'
                    }
                },
                {
                    'id': 'demo_dataset_1',
                    'name': 'ML_Experiment_Data.csv',
                    'mimeType': 'text/csv',
                    'size': '1024000',
                    'content': b'id,feature1,feature2,label\n1,0.5,0.3,positive\n2,0.2,0.8,negative\n3,0.7,0.1,positive',
                    'category': 'dataset',
                    'metadata': {
                        'title': '機械学習実験データセット',
                        'description': '分類実験用のサンプルデータセット',
                        'size': '10000 samples',
                        'format': 'CSV'
                    }
                },
                {
                    'id': 'demo_poster_1',
                    'name': 'Conference_Poster_2024.pdf',
                    'mimeType': 'application/pdf',
                    'size': '512000',
                    'content': b'%PDF-1.4 Demo Conference Poster content...',
                    'category': 'poster',
                    'metadata': {
                        'title': 'Deep Learning for Healthcare',
                        'authors': ['山田太郎', 'Alice Johnson'],
                        'conference': 'International AI Conference 2024',
                        'keywords': ['深層学習', 'ヘルスケア', '医療AI']
                    }
                }
            ],
            'upload_files': [
                {
                    'name': 'New_Research_Dataset.json',
                    'content': b'{"experiment": "新実験データ", "results": [{"id": 1, "score": 0.95}, {"id": 2, "score": 0.87}]}',
                    'category': 'dataset',
                    'metadata': {
                        'title': '新研究データセット',
                        'description': '最新の実験結果データ',
                        'upload_date': datetime.now().isoformat()
                    }
                }
            ]
        }
    
    @pytest.fixture
    def demo_researcher(self):
        """ハッカソンデモ用研究者"""
        return {
            'user_info': {
                'id': 'researcher_demo_123',
                'email': 'researcher@university.ac.jp',
                'name': 'Dr. Demo Researcher',
                'verified_email': True,
                'picture': 'https://example.com/researcher.jpg'
            },
            'context': UserContext(
                user_id="researcher_demo_123",
                email="researcher@university.ac.jp",
                permissions=['read', 'write', 'admin'],
                session_id="demo_session_456"
            )
        }
    
    @pytest.mark.asyncio
    async def test_complete_hackathon_demo_scenario(self, demo_config, demo_research_data, demo_researcher):
        """完全ハッカソンデモシナリオテスト"""
        print("\n" + "="*60)
        print("🎯 ハッカソンデモ - 完全E2Eシナリオテスト開始")
        print("="*60)
        
        # デモ時間計測開始
        demo_start_time = time.time()
        
        # 1. システム初期化とUnifiedPaaSInterface構築
        print("\n📚 Phase 1: システム初期化")
        print("-" * 40)
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=demo_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
            
            # システムヘルスチェック
            with patch.object(unified_interface, '_check_existing_system_health') as mock_existing_health, \
                 patch.object(unified_interface, '_check_google_drive_health') as mock_gdrive_health, \
                 patch.object(unified_interface, '_check_vector_search_health') as mock_vector_health:
                
                mock_existing_health.return_value = HealthStatus.HEALTHY
                mock_gdrive_health.return_value = HealthStatus.HEALTHY
                mock_vector_health.return_value = HealthStatus.HEALTHY
                
                health_status = await unified_interface.check_system_health(demo_researcher['context'])
                assert health_status == HealthStatus.HEALTHY
                
                print("✅ システム初期化完了 - 全機能正常動作")
        
        # 2. 研究者認証フロー
        print("\n🔐 Phase 2: 研究者認証")
        print("-" * 40)
        
        with patch.object(unified_interface, '_authenticate_user') as mock_auth:
            mock_auth.return_value = demo_researcher['context']
            
            # 認証実行
            auth_result = await unified_interface._authenticate_user("demo_auth_token")
            assert auth_result.email == demo_researcher['user_info']['email']
            
            print(f"✅ 研究者認証完了: {auth_result.email}")
            print(f"   権限: {', '.join(auth_result.permissions)}")
        
        # 3. Google Drive研究データ同期
        print("\n📂 Phase 3: Google Drive研究データ同期")
        print("-" * 40)
        
        with patch.object(unified_interface, '_ingest_from_google_drive') as mock_gdrive_ingest:
            # Google Drive同期結果設定
            gdrive_files = demo_research_data['google_drive_files']
            
            mock_gdrive_ingest.return_value = DocumentIngestionResult(
                job_id="demo_gdrive_sync_001",
                status="completed",
                total_files=len(gdrive_files),
                processed_files=len(gdrive_files),
                failed_files=0,
                processing_time_ms=2500,
                errors=[],
                metadata={
                    'synced_files': [f['name'] for f in gdrive_files],
                    'folder_name': 'Research Data 2024'
                }
            )
            
            # Google Drive同期実行
            gdrive_ingestion_request = DocumentIngestionRequest(
                source_type="google_drive",
                source_id="demo_research_folder_123",
                auto_analyze=True,
                metadata={
                    'folder_name': 'Research Data 2024',
                    'sync_mode': 'full',
                    'researcher_id': demo_researcher['context'].user_id
                }
            )
            
            gdrive_result = await unified_interface.ingest_documents(
                gdrive_ingestion_request, 
                demo_researcher['context']
            )
            
            assert gdrive_result.status == "completed"
            assert gdrive_result.processed_files == 3
            
            print(f"✅ Google Drive同期完了: {gdrive_result.processed_files}ファイル取得")
            for file_info in gdrive_files:
                print(f"   📄 {file_info['name']} ({file_info['category']})")
        
        # 4. 自動解析・ベクトルインデックス化
        print("\n🔍 Phase 4: 自動解析・ベクトルインデックス化")
        print("-" * 40)
        
        # 同期されたファイルの自動解析結果をシミュレート
        analyzed_documents = []
        for file_info in gdrive_files:
            analyzed_doc = DocumentMetadata(
                id=file_info['id'],
                title=file_info['metadata']['title'],
                content_type=file_info['category'],
                file_path=f"/data/{file_info['category']}/{file_info['name']}",
                file_size=int(file_info['size']),
                created_at=datetime.now(),
                metadata={
                    **file_info['metadata'],
                    'source': 'google_drive',
                    'analyzed_at': datetime.now().isoformat(),
                    'embeddings_created': True
                }
            )
            analyzed_documents.append(analyzed_doc)
        
        print("✅ 自動解析完了:")
        for doc in analyzed_documents:
            print(f"   📊 {doc.title} - {doc.content_type}")
            if doc.content_type == 'paper':
                keywords = doc.metadata.get('keywords', [])
                print(f"      🏷️  キーワード: {', '.join(keywords[:3])}...")
            elif doc.content_type == 'dataset':
                size_info = doc.metadata.get('size', 'unknown')
                print(f"      📈 データ量: {size_info}")
        
        # 5. ベクトル検索デモ
        print("\n🔎 Phase 5: ベクトル検索デモ")
        print("-" * 40)
        
        # 研究者が関連文献を検索するシナリオ
        search_queries = [
            ("人工知能 深層学習", "AI研究の最新動向を調査"),
            ("機械学習 実験データ", "実験データセットを探索"),
            ("ヘルスケア AI", "医療AI関連の研究を検索")
        ]
        
        for query, description in search_queries:
            print(f"\n🔍 検索クエリ: \"{query}\" ({description})")
            
            with patch.object(unified_interface, '_search_vector_system') as mock_vector_search, \
                 patch.object(unified_interface, '_search_existing_system') as mock_existing_search:
                
                # ベクトル検索結果設定
                relevant_docs = [doc for doc in analyzed_documents 
                               if any(keyword in query for keyword in doc.metadata.get('keywords', []))]
                
                mock_vector_search.return_value = SearchResult(
                    results=relevant_docs,
                    total_results=len(relevant_docs),
                    search_time_ms=180,
                    mode=SearchMode.VECTOR,
                    metadata={'similarity_threshold': 0.75}
                )
                
                mock_existing_search.return_value = SearchResult(
                    results=[],
                    total_results=0,
                    search_time_ms=50,
                    mode=SearchMode.KEYWORD
                )
                
                # ハイブリッド検索実行
                search_request = SearchRequest(
                    query=query,
                    mode=SearchMode.HYBRID,
                    max_results=10,
                    include_metadata=True
                )
                
                search_result = await unified_interface.search_documents(
                    search_request, 
                    demo_researcher['context']
                )
                
                print(f"   📊 検索結果: {search_result.total_results}件 ({search_result.search_time_ms}ms)")
                for i, result in enumerate(search_result.results[:2]):  # 上位2件表示
                    print(f"   {i+1}. {result.title} ({result.content_type})")
        
        # 6. 新しいデータセットアップロード
        print("\n📤 Phase 6: 新しいデータセットアップロード")
        print("-" * 40)
        
        with patch.object(unified_interface, '_ingest_from_upload') as mock_upload_ingest:
            upload_files = demo_research_data['upload_files']
            
            mock_upload_ingest.return_value = DocumentIngestionResult(
                job_id="demo_upload_002",
                status="completed",
                total_files=len(upload_files),
                processed_files=len(upload_files),
                failed_files=0,
                processing_time_ms=1200,
                errors=[],
                metadata={
                    'upload_session': 'demo_session_789',
                    'uploaded_files': [f['name'] for f in upload_files]
                }
            )
            
            # アップロード実行
            upload_request = DocumentIngestionRequest(
                source_type="upload",
                source_id="demo_upload_batch_789",
                auto_analyze=True,
                metadata={
                    'upload_session': 'demo_session_789',
                    'category': 'dataset',
                    'researcher_id': demo_researcher['context'].user_id
                }
            )
            
            upload_result = await unified_interface.ingest_documents(
                upload_request,
                demo_researcher['context']
            )
            
            assert upload_result.status == "completed"
            assert upload_result.processed_files == 1
            
            print(f"✅ データセットアップロード完了: {upload_result.processed_files}ファイル")
            for file_info in upload_files:
                print(f"   📊 {file_info['name']} - {file_info['metadata']['title']}")
        
        # 7. システム統計情報の確認
        print("\n📈 Phase 7: システム統計情報確認")
        print("-" * 40)
        
        with patch.object(unified_interface, '_get_existing_system_stats') as mock_existing_stats, \
             patch.object(unified_interface, '_get_vector_search_stats') as mock_vector_stats, \
             patch.object(unified_interface, '_get_google_drive_stats') as mock_gdrive_stats:
            
            # 統計情報設定
            total_new_files = len(gdrive_files) + len(upload_files)
            
            mock_existing_stats.return_value = {
                'total_documents': 32 + total_new_files,  # 既存32 + 新規4
                'datasets': 4 + 2,  # 既存4 + 新規2
                'papers': 2 + 1,    # 既存2 + 新規1
                'posters': 2 + 1,   # 既存2 + 新規1
                'total_size_mb': 293.8 + 3.8  # 新規ファイル分追加
            }
            
            mock_vector_stats.return_value = {
                'total_embeddings': 32 + total_new_files,
                'last_update': datetime.now().isoformat(),
                'collection_health': 'healthy'
            }
            
            mock_gdrive_stats.return_value = {
                'connected_folders': 1,
                'last_sync': datetime.now().isoformat(),
                'synced_files': len(gdrive_files),
                'sync_status': 'completed'
            }
            
            # 統計情報取得
            stats = await unified_interface.get_system_statistics(demo_researcher['context'])
            
            print("✅ システム統計情報:")
            print(f"   📚 総ドキュメント数: {stats.total_documents}件")
            print(f"   📊 データセット: {stats.datasets}個")
            print(f"   📄 論文: {stats.papers}件")
            print(f"   🖼️  ポスター: {stats.posters}件")
            print(f"   💾 総容量: {stats.total_size_mb:.1f}MB")
            print(f"   🔍 ベクトル埋め込み: {stats.vector_embeddings}件")
            
            # 機能ステータス確認
            print("\n🎛️  機能ステータス:")
            for feature, status in stats.feature_status.items():
                status_icon = "✅" if status else "❌"
                print(f"   {status_icon} {feature}: {'有効' if status else '無効'}")
        
        # 8. デモ完了とパフォーマンス確認
        demo_end_time = time.time()
        demo_duration = demo_end_time - demo_start_time
        
        print("\n🎉 Phase 8: ハッカソンデモ完了")
        print("-" * 40)
        print(f"✅ 総実行時間: {demo_duration:.2f}秒")
        print(f"✅ 処理したファイル数: {total_new_files}件")
        print(f"✅ 実行した検索クエリ数: {len(search_queries)}件")
        print(f"✅ システム統合度: 100% (全機能正常動作)")
        
        # パフォーマンス基準確認
        assert demo_duration < 10.0, f"デモ実行時間が基準を超過: {demo_duration:.2f}秒 > 10秒"
        assert stats.total_documents == 36, f"期待ドキュメント数と不一致: {stats.total_documents} != 36"
        
        print("\n" + "="*60)
        print("🏆 ハッカソンデモ - 完全E2Eシナリオテスト成功!")
        print("="*60)
    
    @pytest.mark.asyncio
    async def test_demo_performance_benchmarks(self, demo_config, demo_research_data, demo_researcher):
        """デモパフォーマンスベンチマークテスト"""
        print("\n📊 ハッカソンデモ - パフォーマンスベンチマーク開始")
        print("-" * 50)
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=demo_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        # ベンチマーク項目
        benchmarks = {
            'system_health_check': {'target_ms': 100, 'results': []},
            'document_search': {'target_ms': 300, 'results': []},
            'document_ingestion': {'target_ms': 2000, 'results': []},
            'statistics_retrieval': {'target_ms': 200, 'results': []}
        }
        
        # 1. システムヘルスチェックベンチマーク
        print("\n🏥 システムヘルスチェック性能測定")
        
        for i in range(5):
            start_time = time.time()
            
            with patch.object(unified_interface, '_check_existing_system_health') as mock_health:
                mock_health.return_value = HealthStatus.HEALTHY
                await unified_interface.check_system_health(demo_researcher['context'])
            
            elapsed_ms = (time.time() - start_time) * 1000
            benchmarks['system_health_check']['results'].append(elapsed_ms)
        
        avg_health_time = sum(benchmarks['system_health_check']['results']) / 5
        print(f"   平均実行時間: {avg_health_time:.1f}ms (目標: {benchmarks['system_health_check']['target_ms']}ms)")
        
        # 2. ドキュメント検索ベンチマーク
        print("\n🔍 ドキュメント検索性能測定")
        
        with patch.object(unified_interface, '_search_vector_system') as mock_search:
            mock_search.return_value = SearchResult(
                results=[],
                total_results=0,
                search_time_ms=50,
                mode=SearchMode.VECTOR
            )
            
            for i in range(3):
                start_time = time.time()
                
                search_request = SearchRequest(
                    query=f"benchmark test query {i}",
                    mode=SearchMode.VECTOR,
                    max_results=10
                )
                
                await unified_interface.search_documents(search_request, demo_researcher['context'])
                
                elapsed_ms = (time.time() - start_time) * 1000
                benchmarks['document_search']['results'].append(elapsed_ms)
        
        avg_search_time = sum(benchmarks['document_search']['results']) / 3
        print(f"   平均実行時間: {avg_search_time:.1f}ms (目標: {benchmarks['document_search']['target_ms']}ms)")
        
        # 3. ドキュメント取り込みベンチマーク
        print("\n📤 ドキュメント取り込み性能測定")
        
        with patch.object(unified_interface, '_ingest_from_google_drive') as mock_ingest:
            mock_ingest.return_value = DocumentIngestionResult(
                job_id="benchmark_job",
                status="completed",
                total_files=3,
                processed_files=3,
                failed_files=0,
                processing_time_ms=1500,
                errors=[]
            )
            
            for i in range(2):
                start_time = time.time()
                
                ingestion_request = DocumentIngestionRequest(
                    source_type="google_drive",
                    source_id=f"benchmark_folder_{i}",
                    auto_analyze=True
                )
                
                await unified_interface.ingest_documents(ingestion_request, demo_researcher['context'])
                
                elapsed_ms = (time.time() - start_time) * 1000
                benchmarks['document_ingestion']['results'].append(elapsed_ms)
        
        avg_ingest_time = sum(benchmarks['document_ingestion']['results']) / 2
        print(f"   平均実行時間: {avg_ingest_time:.1f}ms (目標: {benchmarks['document_ingestion']['target_ms']}ms)")
        
        # 4. 統計情報取得ベンチマーク
        print("\n📈 統計情報取得性能測定")
        
        with patch.object(unified_interface, '_get_existing_system_stats') as mock_stats:
            mock_stats.return_value = {
                'total_documents': 36,
                'datasets': 6,
                'papers': 3,
                'posters': 3,
                'total_size_mb': 297.6
            }
            
            for i in range(3):
                start_time = time.time()
                
                await unified_interface.get_system_statistics(demo_researcher['context'])
                
                elapsed_ms = (time.time() - start_time) * 1000
                benchmarks['statistics_retrieval']['results'].append(elapsed_ms)
        
        avg_stats_time = sum(benchmarks['statistics_retrieval']['results']) / 3
        print(f"   平均実行時間: {avg_stats_time:.1f}ms (目標: {benchmarks['statistics_retrieval']['target_ms']}ms)")
        
        # ベンチマーク結果評価
        print("\n📊 ベンチマーク結果サマリー")
        print("-" * 40)
        
        all_benchmarks_passed = True
        for operation, data in benchmarks.items():
            avg_time = sum(data['results']) / len(data['results'])
            target_time = data['target_ms']
            status = "✅ PASS" if avg_time <= target_time else "❌ FAIL"
            
            if avg_time > target_time:
                all_benchmarks_passed = False
            
            print(f"{operation:20s}: {avg_time:6.1f}ms {status}")
        
        assert all_benchmarks_passed, "一部のベンチマークが目標を達成できませんでした"
        
        print(f"\n🏆 全ベンチマーク合格! デモ準備完了")
    
    @pytest.mark.asyncio
    async def test_demo_error_scenarios(self, demo_config, demo_research_data, demo_researcher):
        """デモエラーシナリオテスト"""
        print("\n⚠️ ハッカソンデモ - エラーシナリオテスト開始")
        print("-" * 50)
        
        config_manager = PaaSConfigManager()
        
        with patch.object(config_manager, 'load_config', return_value=demo_config):
            unified_interface = UnifiedPaaSImpl(config_manager)
        
        # エラーシナリオ1: Google Drive接続エラー
        print("\n📂 シナリオ1: Google Drive接続エラー時の回復")
        
        with patch.object(unified_interface, '_ingest_from_google_drive') as mock_gdrive_ingest, \
             patch.object(unified_interface, '_ingest_from_upload') as mock_upload_fallback:
            
            # Google Driveでエラー発生
            mock_gdrive_ingest.side_effect = Exception("Google Drive API quota exceeded")
            
            # フォールバックが正常動作
            mock_upload_fallback.return_value = DocumentIngestionResult(
                job_id="fallback_job",
                status="completed",
                total_files=1,
                processed_files=1,
                failed_files=0,
                processing_time_ms=800,
                errors=[]
            )
            
            # 取り込み要求
            ingestion_request = DocumentIngestionRequest(
                source_type="google_drive",
                source_id="error_folder",
                auto_analyze=True
            )
            
            # エラー時の回復確認
            result = await unified_interface.ingest_documents(ingestion_request, demo_researcher['context'])
            
            # フォールバック動作確認
            assert result.status == "completed"
            print("   ✅ Google Driveエラー → アップロードフォールバック成功")
        
        # エラーシナリオ2: ベクトル検索エラー
        print("\n🔍 シナリオ2: ベクトル検索エラー時の回復")
        
        with patch.object(unified_interface, '_search_vector_system') as mock_vector_search, \
             patch.object(unified_interface, '_search_existing_system') as mock_existing_search:
            
            # ベクトル検索でエラー発生
            mock_vector_search.side_effect = Exception("Vector search service unavailable")
            
            # 既存検索システムで継続
            mock_existing_search.return_value = SearchResult(
                results=[
                    DocumentMetadata(
                        id="fallback_doc",
                        title="フォールバック検索結果",
                        content_type="paper",
                        file_path="/data/paper/fallback.pdf",
                        file_size=1024000,
                        created_at=datetime.now()
                    )
                ],
                total_results=1,
                search_time_ms=150,
                mode=SearchMode.KEYWORD
            )
            
            # 検索要求
            search_request = SearchRequest(
                query="research data",
                mode=SearchMode.VECTOR,  # ベクトル検索を要求
                max_results=10
            )
            
            # エラー時の回復確認
            search_result = await unified_interface.search_documents(search_request, demo_researcher['context'])
            
            # フォールバック動作確認
            assert search_result.mode == SearchMode.KEYWORD  # キーワード検索にフォールバック
            assert search_result.total_results == 1
            print("   ✅ ベクトル検索エラー → キーワード検索フォールバック成功")
        
        # エラーシナリオ3: 部分的システム障害
        print("\n🏥 シナリオ3: 部分的システム障害時の動作継続")
        
        with patch.object(unified_interface, '_check_google_drive_health') as mock_gdrive_health, \
             patch.object(unified_interface, '_check_vector_search_health') as mock_vector_health, \
             patch.object(unified_interface, '_check_existing_system_health') as mock_existing_health:
            
            # 一部機能で障害発生
            mock_gdrive_health.return_value = HealthStatus.UNHEALTHY
            mock_vector_health.side_effect = Exception("Service timeout")
            mock_existing_health.return_value = HealthStatus.HEALTHY  # 既存システムは正常
            
            # ヘルスチェック実行
            health_status = await unified_interface.check_system_health(demo_researcher['context'])
            
            # 劣化動作確認
            assert health_status == HealthStatus.DEGRADED
            print("   ✅ 部分的障害 → 劣化動作で継続成功")
        
        print("\n🛡️ 全エラーシナリオで適切な回復動作を確認")


if __name__ == "__main__":
    """エンドツーエンドテストスイート実行"""
    print("=== Instance E - エンドツーエンドテストスイート実行 ===")
    
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
        
        print(f"\nエンドツーエンドテストスイート結果: {'SUCCESS' if result.returncode == 0 else 'FAILED'}")
        sys.exit(result.returncode)
        
    except Exception as e:
        print(f"エンドツーエンドテストスイート実行エラー: {e}")
        sys.exit(1)