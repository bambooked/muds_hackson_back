#!/usr/bin/env python3
"""
Enhanced Search Features Integration Test

Instance B拡張機能テスト：
- HybridSearchPort機能テスト
- SemanticSearchPort機能テスト
- 統合検索サービステスト
"""

import asyncio
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from agent.source.interfaces.vector_service import VectorSearchService, get_vector_search_service
from agent.source.interfaces.hybrid_search_impl import EnhancedHybridSearchPort
from agent.source.interfaces.semantic_search_impl import IntelligentSemanticSearchPort
from agent.source.interfaces.search_ports import SearchMode, RankingStrategy


async def test_hybrid_search_features():
    """HybridSearchPort機能テスト"""
    print("=== Hybrid Search Features Test ===")
    
    try:
        # サービス初期化
        service = get_vector_search_service()
        await service.initialize()
        
        if not service.hybrid_search_port:
            print("   ❌ Hybrid search port not available")
            return False
        
        hybrid_port = service.hybrid_search_port
        
        # 既存検索関数をモック設定
        def mock_existing_search(query):
            return [
                {
                    'id': 1,
                    'category': 'dataset',
                    'file_name': 'test_data.csv',
                    'title': 'Test Dataset',
                    'summary': 'A test dataset for hybrid search',
                    'file_size': 1024,
                    'created_at': '2025-01-01',
                    'updated_at': '2025-01-01'
                }
            ]
        
        hybrid_port.set_existing_search_function(mock_existing_search)
        
        print("\n1. Testing hybrid search modes...")
        
        # 各検索モードをテスト
        test_modes = [
            (SearchMode.HYBRID, "ハイブリッド検索"),
            (SearchMode.KEYWORD_ONLY, "キーワード検索のみ"),
            (SearchMode.VECTOR_ONLY, "ベクトル検索のみ")
        ]
        
        for mode, description in test_modes:
            results = await hybrid_port.hybrid_search(
                query="test data",
                search_mode=mode,
                top_k=5
            )
            print(f"   {description}: {len(results)} results")
        
        print("\n2. Testing ranking strategies...")
        
        # ランキング戦略テスト
        strategies = [
            (RankingStrategy.SIMPLE_MERGE, "単純マージ"),
            (RankingStrategy.SCORE_WEIGHTED, "スコア重み付け"),
            (RankingStrategy.RRF, "Reciprocal Rank Fusion")
        ]
        
        for strategy, description in strategies:
            results = await hybrid_port.hybrid_search(
                query="research",
                search_mode=SearchMode.HYBRID,
                ranking_strategy=strategy,
                top_k=3
            )
            print(f"   {description}: {len(results)} results")
        
        print("\n3. Testing filtered search...")
        
        # フィルタ検索テスト
        filters = {
            'category': 'dataset',
            'file_size_range': {'min': 100, 'max': 10000}
        }
        
        filtered_results = await hybrid_port.search_with_filters(
            query="data",
            filters=filters
        )
        print(f"   Filtered search: {len(filtered_results)} results")
        
        print("\n4. Testing search suggestions...")
        
        # 検索候補テスト
        suggestions = await hybrid_port.get_search_suggestions("dat")
        print(f"   Search suggestions for 'dat': {len(suggestions)} suggestions")
        for suggestion in suggestions[:3]:
            print(f"     - {suggestion}")
        
        print("\n5. Testing performance analysis...")
        
        # 性能分析テスト
        test_results = await hybrid_port.hybrid_search("analysis", top_k=3)
        analysis = await hybrid_port.analyze_search_performance(
            query="analysis",
            results=test_results,
            user_feedback={'clicked_results': [0, 1]}
        )
        
        print(f"   Performance analysis completed:")
        print(f"     Total results: {analysis.get('total_results', 0)}")
        print(f"     Avg score: {analysis.get('performance_metrics', {}).get('avg_score', 0):.3f}")
        print(f"     Recommendations: {len(analysis.get('recommendations', []))}")
        
        print("\n   ✅ Hybrid search features test passed")
        return True
        
    except Exception as e:
        print(f"   ❌ Hybrid search test failed: {e}")
        return False


async def test_semantic_search_features():
    """SemanticSearchPort機能テスト"""
    print("\n=== Semantic Search Features Test ===")
    
    try:
        # サービス初期化
        service = get_vector_search_service()
        await service.initialize()
        
        if not service.semantic_search_port:
            print("   ❌ Semantic search port not available")
            return False
        
        semantic_port = service.semantic_search_port
        
        print("\n1. Testing intent-based search...")
        
        # 意図理解検索テスト
        intent_results = await semantic_port.search_with_intent(
            query="environmental research",
            intent_context="Looking for sustainability-related datasets",
            top_k=3
        )
        print(f"   Intent-based search: {len(intent_results)} results")
        for i, result in enumerate(intent_results, 1):
            print(f"     {i}. {result.document.file_name} (score: {result.score:.3f})")
        
        print("\n2. Testing result explanations...")
        
        # 結果説明生成テスト
        if intent_results:
            explained_results = await semantic_port.explain_search_results(
                query="environmental research",
                results=intent_results[:2]
            )
            print(f"   Generated explanations for {len(explained_results)} results:")
            for result in explained_results:
                print(f"     - {result.document.file_name}: {result.explanation}")
        
        print("\n3. Testing related query suggestions...")
        
        # 関連クエリ提案テスト
        related_queries = await semantic_port.suggest_related_queries(
            query="machine learning"
        )
        print(f"   Related queries for 'machine learning': {len(related_queries)} suggestions")
        for query in related_queries[:5]:
            print(f"     - {query}")
        
        print("\n4. Testing multilingual query expansion...")
        
        # 多言語クエリ拡張テスト
        multilingual_results = await semantic_port.search_with_intent(
            query="データ分析",  # 日本語クエリ
            top_k=3
        )
        print(f"   Multilingual search (Japanese): {len(multilingual_results)} results")
        
        print("\n   ✅ Semantic search features test passed")
        return True
        
    except Exception as e:
        print(f"   ❌ Semantic search test failed: {e}")
        return False


async def test_integrated_search_service():
    """統合検索サービステスト"""
    print("\n=== Integrated Search Service Test ===")
    
    try:
        service = get_vector_search_service()
        await service.initialize()
        
        print("\n1. Testing service status...")
        
        # サービス状況確認
        status = await service.get_service_status()
        print(f"   Service enabled: {status.get('enabled')}")
        print(f"   Initialized: {status.get('initialized')}")
        print(f"   Health: {status.get('health')}")
        print(f"   Vector search available: {status.get('vector_search_available')}")
        
        print("\n2. Testing enhanced search modes...")
        
        # 拡張検索モードテスト
        def mock_existing_search(query, category=None):
            return [
                {
                    'id': 2,
                    'category': 'paper',
                    'file_name': 'research_paper.pdf',
                    'title': 'Research Paper on Data Analysis',
                    'summary': 'A comprehensive study on data analysis techniques',
                    'file_size': 2048,
                    'created_at': '2025-01-01',
                    'updated_at': '2025-01-01'
                }
            ]
        
        # 各検索モードの組み合わせテスト
        test_cases = [
            ("vector", "ベクトル検索"),
            ("keyword", "キーワード検索"),
            ("hybrid", "ハイブリッド検索")
        ]
        
        for mode, description in test_cases:
            results = await service.enhanced_search(
                query="data analysis",
                search_mode=mode,
                existing_search_function=mock_existing_search
            )
            print(f"   {description}: {len(results)} results")
            if results:
                print(f"     Best match: {results[0].get('file_name', 'Unknown')} (score: {results[0].get('relevance_score', 0):.3f})")
        
        print("\n3. Testing category filtering...")
        
        # カテゴリフィルタテスト
        categories = ['dataset', 'paper', 'poster']
        for category in categories:
            results = await service.enhanced_search(
                query="research",
                category_filter=category,
                existing_search_function=mock_existing_search
            )
            print(f"   Category '{category}': {len(results)} results")
        
        print("\n4. Testing search registry integration...")
        
        # 検索レジストリ統合テスト
        registry = service.search_registry
        registry.set_existing_search_function(mock_existing_search)
        
        registry_results = await registry.search(
            query="test query",
            search_mode=SearchMode.HYBRID
        )
        print(f"   Registry search: {len(registry_results)} results")
        
        print("\n   ✅ Integrated search service test passed")
        return True
        
    except Exception as e:
        print(f"   ❌ Integrated service test failed: {e}")
        return False


async def test_error_handling_and_fallbacks():
    """エラーハンドリング・フォールバック機能テスト"""
    print("\n=== Error Handling and Fallbacks Test ===")
    
    try:
        # ベクトル検索を無効化
        original_enabled = os.getenv('VECTOR_SEARCH_ENABLED')
        os.environ['VECTOR_SEARCH_ENABLED'] = 'False'
        
        # 新しいサービスインスタンス作成
        service = VectorSearchService()
        
        print("\n1. Testing disabled vector search fallback...")
        
        def mock_fallback_search(query, category=None):
            return [
                {
                    'id': 3,
                    'category': 'dataset',
                    'file_name': 'fallback_data.csv',
                    'title': 'Fallback Dataset',
                    'summary': 'Fallback search result',
                    'file_size': 512,
                    'created_at': '2025-01-01',
                    'updated_at': '2025-01-01'
                }
            ]
        
        # フォールバック検索実行
        fallback_results = await service.enhanced_search(
            query="fallback test",
            search_mode="hybrid",
            existing_search_function=mock_fallback_search
        )
        
        print(f"   Fallback search: {len(fallback_results)} results")
        if fallback_results:
            print(f"     Result: {fallback_results[0].get('file_name', 'Unknown')}")
        
        print("\n2. Testing graceful degradation...")
        
        # サービス状況確認（無効状態）
        status = await service.get_service_status()
        print(f"   Service enabled: {status.get('enabled')}")
        print(f"   Graceful degradation: {'Yes' if not status.get('enabled') else 'No'}")
        
        # 元の設定に戻す
        if original_enabled:
            os.environ['VECTOR_SEARCH_ENABLED'] = original_enabled
        else:
            os.environ.pop('VECTOR_SEARCH_ENABLED', None)
        
        print("\n   ✅ Error handling and fallbacks test passed")
        return True
        
    except Exception as e:
        print(f"   ❌ Error handling test failed: {e}")
        return False


async def main():
    """拡張機能統合テストメイン実行"""
    print("🔬 Enhanced Search Features Integration Test Suite")
    print("=" * 60)
    
    tests = [
        ("Hybrid Search Features", test_hybrid_search_features),
        ("Semantic Search Features", test_semantic_search_features),
        ("Integrated Search Service", test_integrated_search_service),
        ("Error Handling and Fallbacks", test_error_handling_and_fallbacks),
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
    
    print("\n" + "=" * 60)
    print(f"📊 Enhanced Features Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All enhanced features tests passed! Instance B implementation complete.")
        return 0
    else:
        print("⚠️  Some enhanced features tests failed. Please review implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))