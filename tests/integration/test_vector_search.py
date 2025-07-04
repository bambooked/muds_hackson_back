#!/usr/bin/env python3
"""
Vector Search Integration Test

Instance B統合テスト：
- ChromaDB初期化確認
- 既存文書のベクトル化テスト
- 検索機能テスト
- 既存システムとの互換性確認
"""

import asyncio
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from agent.source.interfaces.vector_service import VectorSearchService, get_vector_search_service
from agent.source.interfaces.vector_search_impl import ChromaVectorSearchPort, load_vector_search_config_from_env
from agent.source.interfaces.vector_indexer import VectorIndexer


async def test_vector_search_initialization():
    """ベクトル検索初期化テスト"""
    print("=== Vector Search Initialization Test ===")
    
    try:
        # 設定確認
        print("1. Checking configuration...")
        config = load_vector_search_config_from_env()
        print(f"   Provider: {config.provider}")
        print(f"   Collection: {config.collection_name}")
        print(f"   Embedding Model: {config.embedding_model}")
        print(f"   Persist Directory: {config.persist_directory}")
        
        # ChromaDB初期化
        print("\n2. Initializing ChromaDB...")
        vector_port = ChromaVectorSearchPort()
        init_success = await vector_port.initialize_index(config, force_recreate=True)
        
        if init_success:
            print("   ✅ ChromaDB initialized successfully")
        else:
            print("   ❌ ChromaDB initialization failed")
            return False
        
        # ヘルスチェック
        print("\n3. Health check...")
        health = await vector_port.health_check()
        print(f"   Status: {health.get('status')}")
        print(f"   Response time: {health.get('response_time_ms')}ms")
        
        if health.get('status') == 'healthy':
            print("   ✅ Health check passed")
            return True
        else:
            print("   ❌ Health check failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Initialization failed: {e}")
        return False


async def test_document_indexing():
    """文書インデックステスト"""
    print("\n=== Document Indexing Test ===")
    
    try:
        # VectorIndexer初期化
        indexer = VectorIndexer()
        
        # 初期化
        print("1. Initializing vector indexer...")
        init_success = await indexer.initialize_vector_search(force_recreate=False)
        
        if not init_success:
            print("   ❌ Vector indexer initialization failed")
            return False
        
        print("   ✅ Vector indexer initialized")
        
        # インデックス統計（開始前）
        print("\n2. Getting initial index statistics...")
        initial_stats = await indexer.get_indexing_status()
        print(f"   Database documents: {initial_stats['database_counts']['total']}")
        print(f"   Indexed documents: {initial_stats['indexing_coverage']['indexed_documents']}")
        print(f"   Coverage: {initial_stats['indexing_coverage']['coverage_percentage']:.1f}%")
        
        # 少数の文書をインデックス（テスト用）
        print("\n3. Indexing sample documents...")
        results = await indexer.index_all_existing_documents(
            batch_size=2,  # 小さなバッチサイズでテスト
            categories=['dataset']  # データセットのみでテスト
        )
        
        print(f"   Total: {results['total_documents']}")
        print(f"   Successful: {results['successful']}")
        print(f"   Failed: {results['failed']}")
        print(f"   Duration: {results['duration_seconds']:.2f}s")
        
        if results['errors']:
            print(f"   Errors: {len(results['errors'])}")
            for error in results['errors'][:3]:  # 最初の3つのエラー表示
                print(f"     - {error}")
        
        if results['successful'] > 0:
            print("   ✅ Document indexing test passed")
            return True
        else:
            print("   ❌ No documents were indexed successfully")
            return False
            
    except Exception as e:
        print(f"   ❌ Document indexing failed: {e}")
        return False


async def test_vector_search():
    """ベクトル検索テスト"""
    print("\n=== Vector Search Test ===")
    
    try:
        # VectorSearchService初期化
        service = get_vector_search_service()
        init_success = await service.initialize()
        
        if not init_success:
            print("   ❌ Vector search service initialization failed")
            return False
        
        print("   ✅ Vector search service initialized")
        
        # テストクエリ実行
        test_queries = [
            "機械学習",
            "データ分析",
            "sustainability",
            "環境"
        ]
        
        print("\n2. Running test queries...")
        for query in test_queries:
            print(f"\n   Query: '{query}'")
            
            # ベクトル検索のみ
            vector_results = await service.enhanced_search(
                query=query,
                search_mode="vector",
                top_k=3
            )
            
            print(f"   Vector results: {len(vector_results)}")
            for i, result in enumerate(vector_results[:2], 1):
                score = result.get('relevance_score', 0)
                filename = result.get('file_name', 'Unknown')
                print(f"     {i}. {filename} (score: {score:.3f})")
        
        print("\n   ✅ Vector search test completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Vector search failed: {e}")
        return False


async def test_service_integration():
    """サービス統合テスト"""
    print("\n=== Service Integration Test ===")
    
    try:
        # サービス状況確認
        service = get_vector_search_service()
        status = await service.get_service_status()
        
        print("1. Service status:")
        print(f"   Enabled: {status.get('enabled')}")
        print(f"   Initialized: {status.get('initialized')}")
        print(f"   Health: {status.get('health')}")
        print(f"   Vector search available: {status.get('vector_search_available')}")
        
        if status.get('indexing_status'):
            coverage = status['indexing_status']['indexing_coverage']
            print(f"   Indexing coverage: {coverage['coverage_percentage']:.1f}%")
            print(f"   Indexed/Total: {coverage['indexed_documents']}/{coverage['total_documents']}")
        
        # ハイブリッド検索テスト
        print("\n2. Hybrid search test...")
        
        def mock_existing_search(query, category=None):
            """モック既存検索関数"""
            return [
                {
                    'id': 1,
                    'category': 'dataset',
                    'file_name': 'test_dataset.csv',
                    'title': 'Test Dataset',
                    'summary': 'Test dataset for mock search'
                }
            ]
        
        hybrid_results = await service.enhanced_search(
            query="テストデータ",
            search_mode="hybrid",
            existing_search_function=mock_existing_search
        )
        
        print(f"   Hybrid results: {len(hybrid_results)}")
        for result in hybrid_results[:2]:
            print(f"     - {result.get('file_name')} ({result.get('search_type', 'unknown')})")
        
        print("\n   ✅ Service integration test completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Service integration failed: {e}")
        return False


async def test_fallback_behavior():
    """フォールバック機能テスト"""
    print("\n=== Fallback Behavior Test ===")
    
    try:
        # ベクトル検索を無効化してテスト
        original_enabled = os.getenv('VECTOR_SEARCH_ENABLED')
        os.environ['VECTOR_SEARCH_ENABLED'] = 'False'
        
        # 新しいサービスインスタンス作成
        service = VectorSearchService()
        
        def mock_existing_search(query, category=None):
            return [
                {
                    'id': 2,
                    'category': 'paper',
                    'file_name': 'fallback_test.pdf',
                    'title': 'Fallback Test Paper'
                }
            ]
        
        # 検索実行（フォールバックされるはず）
        results = await service.enhanced_search(
            query="フォールバックテスト",
            search_mode="hybrid",
            existing_search_function=mock_existing_search
        )
        
        print(f"   Fallback results: {len(results)}")
        
        # 元の設定に戻す
        if original_enabled:
            os.environ['VECTOR_SEARCH_ENABLED'] = original_enabled
        else:
            os.environ.pop('VECTOR_SEARCH_ENABLED', None)
        
        if len(results) > 0:
            print("   ✅ Fallback behavior test passed")
            return True
        else:
            print("   ❌ Fallback behavior test failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Fallback test failed: {e}")
        return False


async def main():
    """統合テストメイン実行"""
    print("🔬 Vector Search Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Vector Search Initialization", test_vector_search_initialization),
        ("Document Indexing", test_document_indexing),
        ("Vector Search", test_vector_search),
        ("Service Integration", test_service_integration),
        ("Fallback Behavior", test_fallback_behavior),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Vector search integration successful.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))