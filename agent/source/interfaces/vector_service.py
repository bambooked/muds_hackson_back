"""
ベクトル検索統合サービス

Instance B: 既存システムとベクトル検索の統合レイヤー
- UserInterfaceとの橋渡し
- 既存検索とベクトル検索のハイブリッド実行
- フォールバック機能実装
- 設定による機能ON/OFF制御
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from .vector_search_impl import ChromaVectorSearchPort, load_vector_search_config_from_env
from .vector_indexer import VectorIndexer
from .search_ports import SearchMode, RankingStrategy, SearchPortRegistry
from .data_models import SearchResult, DocumentMetadata, UserContext
from .hybrid_search_impl import EnhancedHybridSearchPort
from .semantic_search_impl import IntelligentSemanticSearchPort

logger = logging.getLogger(__name__)


class VectorSearchService:
    """
    ベクトル検索統合サービス
    
    既存システム保護：
    - ベクトル検索無効時は既存検索のみ使用
    - エラー時の自動フォールバック
    - 既存インターフェースと完全互換
    """
    
    def __init__(self):
        self.is_enabled = self._is_vector_search_enabled()
        self.vector_search_port = None
        self.vector_indexer = None
        self.hybrid_search_port = None
        self.semantic_search_port = None
        self.search_registry = SearchPortRegistry()
        self._initialization_attempted = False
    
    def _is_vector_search_enabled(self) -> bool:
        """環境変数からベクトル検索有効化確認"""
        return os.getenv('VECTOR_SEARCH_ENABLED', 'False').lower() in ['true', '1', 'yes', 'on']
    
    async def initialize(self, force_recreate: bool = False) -> bool:
        """ベクトル検索サービス初期化"""
        if not self.is_enabled:
            logger.info("Vector search disabled by configuration")
            return False
        
        if self._initialization_attempted and self.vector_search_port and self.vector_search_port.is_initialized:
            return True
        
        try:
            logger.info("Initializing vector search service...")
            
            # ベクトル検索ポート初期化
            self.vector_search_port = ChromaVectorSearchPort()
            config = load_vector_search_config_from_env()
            
            success = await self.vector_search_port.initialize_index(config, force_recreate)
            
            if success:
                # インデクサー初期化
                self.vector_indexer = VectorIndexer(self.vector_search_port)
                
                # 拡張検索ポート初期化
                self.hybrid_search_port = EnhancedHybridSearchPort(self.vector_search_port)
                self.semantic_search_port = IntelligentSemanticSearchPort(self.vector_search_port)
                
                # 検索レジストリに登録
                self.search_registry.register_vector_search_port(self.vector_search_port)
                self.search_registry.register_hybrid_search_port(self.hybrid_search_port)
                self.search_registry.register_semantic_search_port(self.semantic_search_port)
                
                logger.info("Vector search service with enhanced features initialized successfully")
                self._initialization_attempted = True
                return True
            else:
                logger.warning("Vector search initialization failed")
                self._initialization_attempted = True
                return False
                
        except Exception as e:
            logger.error(f"Vector search service initialization error: {e}")
            self._initialization_attempted = True
            return False
    
    async def enhanced_search(
        self,
        query: str,
        search_mode: str = "hybrid",
        category_filter: Optional[str] = None,
        top_k: int = 10,
        existing_search_function=None
    ) -> List[Dict[str, Any]]:
        """
        強化検索（ベクトル検索＋既存検索のハイブリッド）
        
        Args:
            query: 検索クエリ
            search_mode: "vector", "keyword", "hybrid"
            category_filter: カテゴリフィルタ ('dataset', 'paper', 'poster')
            top_k: 取得件数
            existing_search_function: 既存検索関数（フォールバック用）
        
        Returns:
            List[Dict]: 検索結果（既存形式互換）
        """
        try:
            # 初期化確認
            if not await self.initialize():
                logger.info("Vector search not available, falling back to existing search")
                return await self._fallback_search(query, category_filter, existing_search_function)
            
            results = []
            
            # 検索モード別実行
            if search_mode == "vector" or search_mode == "hybrid":
                # ベクトル検索実行
                vector_results = await self._vector_search(query, category_filter, top_k)
                results.extend(vector_results)
            
            if search_mode == "keyword" or search_mode == "hybrid":
                # 既存検索実行
                keyword_results = await self._keyword_search(query, category_filter, existing_search_function)
                results.extend(keyword_results)
            
            # 結果統合・重複排除
            if search_mode == "hybrid":
                results = self._merge_search_results(results, top_k)
            else:
                results = results[:top_k]
            
            logger.info(f"Enhanced search completed: {len(results)} results for query '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"Enhanced search failed: {e}")
            # エラー時フォールバック
            return await self._fallback_search(query, category_filter, existing_search_function)
    
    async def _vector_search(
        self, 
        query: str, 
        category_filter: Optional[str], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """ベクトル検索実行"""
        try:
            if not self.vector_search_port or not self.vector_search_port.is_initialized:
                return []
            
            # フィルタ設定
            filter_metadata = None
            if category_filter:
                filter_metadata = {"category": category_filter}
            
            # ベクトル検索実行
            search_results = await self.vector_search_port.search_similar(
                query=query,
                top_k=top_k,
                filter_metadata=filter_metadata
            )
            
            # 既存形式に変換
            converted_results = []
            for result in search_results:
                converted = result.to_existing_format()
                converted['search_type'] = 'vector'
                converted['relevance_score'] = result.score
                converted['explanation'] = result.explanation
                converted_results.append(converted)
            
            return converted_results
            
        except Exception as e:
            logger.error(f"Vector search execution failed: {e}")
            return []
    
    async def _keyword_search(
        self, 
        query: str, 
        category_filter: Optional[str], 
        existing_search_function
    ) -> List[Dict[str, Any]]:
        """既存キーワード検索実行"""
        try:
            if not existing_search_function:
                return []
            
            # 既存検索実行（同期関数を非同期で実行）
            loop = asyncio.get_event_loop()
            keyword_results = await loop.run_in_executor(
                None, 
                existing_search_function, 
                query, 
                category_filter
            )
            
            # 既存形式に統一
            converted_results = []
            for result in keyword_results:
                if isinstance(result, dict):
                    result['search_type'] = 'keyword'
                    result['relevance_score'] = 1.0  # キーワード検索は一律1.0
                    converted_results.append(result)
            
            return converted_results
            
        except Exception as e:
            logger.error(f"Keyword search execution failed: {e}")
            return []
    
    def _merge_search_results(self, results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """検索結果統合・重複排除"""
        try:
            # ID+カテゴリで重複チェック
            seen = set()
            merged = []
            
            # スコア順でソート
            results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            for result in results:
                # 重複チェック用キー作成
                key = (result.get('id'), result.get('category'))
                
                if key not in seen:
                    seen.add(key)
                    merged.append(result)
                    
                    if len(merged) >= top_k:
                        break
                else:
                    # 重複の場合、より高いスコアのものを保持
                    for i, existing in enumerate(merged):
                        if (existing.get('id'), existing.get('category')) == key:
                            if result.get('relevance_score', 0) > existing.get('relevance_score', 0):
                                merged[i] = result
                            break
            
            return merged
            
        except Exception as e:
            logger.error(f"Search result merging failed: {e}")
            return results[:top_k]
    
    async def _fallback_search(
        self, 
        query: str, 
        category_filter: Optional[str], 
        existing_search_function
    ) -> List[Dict[str, Any]]:
        """既存検索へのフォールバック"""
        try:
            if existing_search_function:
                return await self._keyword_search(query, category_filter, existing_search_function)
            else:
                logger.warning("No fallback search function available")
                return []
                
        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
            return []
    
    async def index_all_documents(self, force_recreate: bool = False) -> Dict[str, Any]:
        """全文書のベクトル化実行"""
        try:
            if not await self.initialize(force_recreate):
                return {"error": "Vector search initialization failed"}
            
            if not self.vector_indexer:
                return {"error": "Vector indexer not available"}
            
            logger.info("Starting vector indexing for all documents...")
            results = await self.vector_indexer.index_all_existing_documents()
            
            logger.info(f"Vector indexing completed: {results['successful']}/{results['total_documents']} successful")
            return results
            
        except Exception as e:
            logger.error(f"Document indexing failed: {e}")
            return {"error": str(e)}
    
    async def get_service_status(self) -> Dict[str, Any]:
        """サービス状況取得"""
        try:
            status = {
                "enabled": self.is_enabled,
                "initialized": False,
                "vector_search_available": False,
                "indexing_status": None,
                "health": "unknown"
            }
            
            if self.is_enabled and await self.initialize():
                status["initialized"] = True
                
                if self.vector_search_port:
                    health = await self.vector_search_port.health_check()
                    status["health"] = health.get("status", "unknown")
                    status["vector_search_available"] = health.get("status") == "healthy"
                
                if self.vector_indexer:
                    indexing_status = await self.vector_indexer.get_indexing_status()
                    status["indexing_status"] = indexing_status
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get service status: {e}")
            return {"error": str(e)}
    
    def create_enhanced_search_function(self, existing_search_function):
        """既存検索関数の拡張版作成"""
        async def enhanced_search_wrapper(query: str, category: Optional[str] = None, search_mode: str = "hybrid"):
            return await self.enhanced_search(
                query=query,
                search_mode=search_mode,
                category_filter=category,
                existing_search_function=existing_search_function
            )
        
        return enhanced_search_wrapper


# Global service instance
_vector_search_service = None


def get_vector_search_service() -> VectorSearchService:
    """グローバルベクトル検索サービス取得"""
    global _vector_search_service
    if _vector_search_service is None:
        _vector_search_service = VectorSearchService()
    return _vector_search_service


# Utility functions for integration with existing code

async def initialize_vector_search(force_recreate: bool = False) -> bool:
    """ベクトル検索初期化（外部呼び出し用）"""
    service = get_vector_search_service()
    return await service.initialize(force_recreate)


async def search_documents_enhanced(
    query: str,
    search_mode: str = "hybrid",
    category: Optional[str] = None,
    existing_search_function=None
) -> List[Dict[str, Any]]:
    """強化文書検索（外部呼び出し用）"""
    service = get_vector_search_service()
    return await service.enhanced_search(
        query=query,
        search_mode=search_mode,
        category_filter=category,
        existing_search_function=existing_search_function
    )


async def index_all_documents_vector(force_recreate: bool = False) -> Dict[str, Any]:
    """全文書ベクトル化（外部呼び出し用）"""
    service = get_vector_search_service()
    return await service.index_all_documents(force_recreate)


# Command line interface
if __name__ == "__main__":
    import sys
    
    async def main():
        service = get_vector_search_service()
        
        if len(sys.argv) > 1:
            command = sys.argv[1]
            
            if command == "status":
                status = await service.get_service_status()
                print("Vector Search Service Status:")
                print(f"  Enabled: {status.get('enabled')}")
                print(f"  Initialized: {status.get('initialized')}")
                print(f"  Health: {status.get('health')}")
                if status.get('indexing_status'):
                    coverage = status['indexing_status']['indexing_coverage']
                    print(f"  Coverage: {coverage['coverage_percentage']:.1f}% ({coverage['indexed_documents']}/{coverage['total_documents']})")
            
            elif command == "index":
                force = "--force" in sys.argv
                results = await service.index_all_documents(force)
                print(f"Indexing completed: {results.get('successful', 0)}/{results.get('total_documents', 0)} successful")
                if results.get('errors'):
                    print(f"Errors: {len(results['errors'])}")
            
            elif command == "search":
                if len(sys.argv) < 3:
                    print("Usage: python vector_service.py search <query>")
                    return
                query = sys.argv[2]
                results = await service.enhanced_search(query)
                print(f"Search results for '{query}': {len(results)} found")
                for i, result in enumerate(results[:5], 1):
                    print(f"  {i}. {result.get('file_name', 'Unknown')} (score: {result.get('relevance_score', 0):.3f})")
        else:
            print("Available commands: status, index, search <query>")
    
    asyncio.run(main())