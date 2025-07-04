"""
検索機能インターフェース定義

このモジュールは、従来のキーワード検索に加えて、ベクトル検索・セマンティック検索機能を抽象化します。
既存検索システムとの完全互換性を保ちながら、新しい検索手法を段階的に導入可能。

Claude Code実装ガイダンス：
- 既存システムの検索機能は変更しない
- 新しい検索手法は並行実行して結果を統合
- ベクトルDB選択は設定で切り替え可能
- パフォーマンス重視の非同期実装

実装優先順位：
1. VectorSearchPort (ベクトル検索基盤)
2. HybridSearchPort (既存検索との統合)
3. SemanticSearchPort (高度なセマンティック検索)
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple, Union
from enum import Enum
import asyncio

from .data_models import (
    DocumentMetadata,
    SearchResult,
    UserContext,
    VectorSearchConfig,
    SearchError
)


class SearchMode(Enum):
    """検索モード"""
    KEYWORD_ONLY = "keyword"          # 既存キーワード検索のみ
    VECTOR_ONLY = "vector"            # ベクトル検索のみ
    HYBRID = "hybrid"                 # ハイブリッド検索
    SEMANTIC = "semantic"             # セマンティック検索


class RankingStrategy(Enum):
    """ランキング戦略"""
    SCORE_WEIGHTED = "score_weighted"     # スコア重み付け
    RRF = "reciprocal_rank_fusion"       # Reciprocal Rank Fusion
    RERANK = "rerank"                    # Re-ranking
    SIMPLE_MERGE = "simple_merge"        # 単純マージ


class VectorSearchPort(ABC):
    """
    ベクトル検索インターフェース
    
    役割：
    - 文書のベクトル化・インデックス作成
    - セマンティック検索実行
    - ベクトルDBとの通信抽象化
    
    Claude Code実装ガイダンス：
    - ChromaDB推奨（組み込み容易、永続化対応）
    - 埋め込みモデルは設定で切り替え可能
    - 既存文書の自動ベクトル化機能
    - インクリメンタル更新対応
    
    推奨実装パッケージ：
    - chromadb (推奨)
    - qdrant-client (高性能が必要な場合)
    - sentence-transformers (埋め込みモデル)
    """
    
    @abstractmethod
    async def initialize_index(
        self, 
        config: VectorSearchConfig,
        force_recreate: bool = False
    ) -> bool:
        """
        ベクトルインデックス初期化
        
        Args:
            config: ベクトル検索設定
            force_recreate: 既存インデックス強制再作成
            
        Returns:
            bool: 初期化成功可否
            
        Claude Code実装例（ChromaDB）：
        ```python
        import chromadb
        from sentence_transformers import SentenceTransformer
        
        async def initialize_index(self, config, force_recreate=False):
            try:
                self.client = chromadb.PersistentClient(path=config.persist_directory)
                self.embedding_model = SentenceTransformer(config.embedding_model)
                
                if force_recreate:
                    try:
                        self.client.delete_collection(config.collection_name)
                    except:
                        pass
                
                self.collection = self.client.get_or_create_collection(
                    name=config.collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                return True
            except Exception as e:
                raise SearchError(f"Vector index initialization failed: {e}")
        ```
        """
        pass
    
    @abstractmethod
    async def index_document(
        self,
        document: DocumentMetadata,
        content: str,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        文書をベクトル化してインデックス
        
        Args:
            document: 文書メタデータ
            content: 文書内容
            user_context: ユーザーコンテキスト
            
        Returns:
            bool: インデックス成功可否
            
        Claude Code実装時の注意：
        - 既存解析済み文書の自動ベクトル化
        - チャンク分割（長文対応）
        - メタデータ保存
        - 重複チェック（document.vector_id）
        
        実装フロー：
        1. 文書内容の前処理（クリーニング）
        2. チャンク分割（必要に応じて）
        3. 埋め込みベクトル生成
        4. メタデータと共にインデックス保存
        5. document.vector_idを更新
        """
        pass
    
    @abstractmethod
    async def search_similar(
        self,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.7,
        filter_metadata: Optional[Dict[str, Any]] = None,
        user_context: Optional[UserContext] = None
    ) -> List[SearchResult]:
        """
        類似文書検索
        
        Args:
            query: 検索クエリ
            top_k: 取得件数上限
            similarity_threshold: 類似度閾値
            filter_metadata: メタデータフィルタ
            user_context: ユーザーコンテキスト
            
        Returns:
            List[SearchResult]: 検索結果（類似度順）
            
        Claude Code実装例：
        ```python
        async def search_similar(self, query, top_k=10, similarity_threshold=0.7, filter_metadata=None, user_context=None):
            try:
                # クエリベクトル化
                query_embedding = self.embedding_model.encode([query])
                
                # ベクトル検索実行
                results = self.collection.query(
                    query_embeddings=query_embedding,
                    n_results=top_k,
                    where=filter_metadata
                )
                
                # SearchResultに変換
                search_results = []
                for i, (doc_id, distance) in enumerate(zip(results['ids'][0], results['distances'][0])):
                    similarity = 1.0 - distance  # コサイン距離を類似度に変換
                    if similarity >= similarity_threshold:
                        document = await self._get_document_by_vector_id(doc_id)
                        if document:
                            search_results.append(SearchResult(
                                document=document,
                                score=similarity,
                                relevance_type='semantic',
                                explanation=f"Vector similarity: {similarity:.3f}"
                            ))
                
                return sorted(search_results, key=lambda x: x.score, reverse=True)
                
            except Exception as e:
                raise SearchError(f"Vector search failed: {e}")
        ```
        """
        pass
    
    @abstractmethod
    async def batch_index_documents(
        self,
        documents: List[Tuple[DocumentMetadata, str]],
        batch_size: int = 10,
        user_context: Optional[UserContext] = None
    ) -> Dict[str, Any]:
        """
        文書群の一括インデックス
        
        Args:
            documents: [(document, content), ...] のリスト
            batch_size: バッチサイズ
            user_context: ユーザーコンテキスト
            
        Returns:
            Dict: {'successful': 25, 'failed': 3, 'errors': [...]}
        """
        pass
    
    @abstractmethod
    async def delete_document(
        self,
        vector_id: str,
        user_context: Optional[UserContext] = None
    ) -> bool:
        """
        ベクトルインデックスから文書削除"""
        pass
    
    @abstractmethod
    async def get_index_stats(self) -> Dict[str, Any]:
        """
        インデックス統計情報取得
        
        Returns:
            Dict: {'total_documents': 1000, 'index_size_mb': 50, 'last_updated': '...'}
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        ベクトル検索システムヘルスチェック
        
        Returns:
            Dict: {'status': 'healthy', 'response_time_ms': 50, 'errors': []}
        """
        pass


class SemanticSearchPort(ABC):
    """
    高度なセマンティック検索インターフェース
    
    役割：
    - 意図理解検索
    - クエリ拡張
    - コンテキスト考慮検索
    
    Claude Code実装ガイダンス：
    - VectorSearchPortを基盤として実装
    - クエリ前処理・後処理を追加
    - LLMとの連携によるクエリ理解
    """
    
    @abstractmethod
    async def search_with_intent(
        self,
        query: str,
        intent_context: Optional[str] = None,
        top_k: int = 10,
        user_context: Optional[UserContext] = None
    ) -> List[SearchResult]:
        """
        意図理解に基づく検索
        
        Args:
            query: 自然言語クエリ
            intent_context: 検索意図のコンテキスト
            top_k: 取得件数
            user_context: ユーザーコンテキスト
            
        Claude Code実装時の注意：
        - クエリの意図理解（Google Gemini API活用）
        - 検索クエリの自動拡張
        - コンテキストに基づく結果フィルタリング
        """
        pass
    
    @abstractmethod
    async def explain_search_results(
        self,
        query: str,
        results: List[SearchResult],
        user_context: Optional[UserContext] = None
    ) -> List[SearchResult]:
        """
        検索結果の説明生成
        
        Args:
            query: 元クエリ
            results: 検索結果
            user_context: ユーザーコンテキスト
            
        Returns:
            List[SearchResult]: 説明付き検索結果
        """
        pass
    
    @abstractmethod
    async def suggest_related_queries(
        self,
        query: str,
        user_context: Optional[UserContext] = None
    ) -> List[str]:
        """
        関連クエリ提案
        
        Returns:
            List[str]: 関連クエリ候補
        """
        pass


class HybridSearchPort(ABC):
    """
    ハイブリッド検索インターフェース
    
    役割：
    - キーワード検索とベクトル検索の統合
    - 結果ランキングの最適化
    - 既存システムとの完全互換性維持
    
    Claude Code実装ガイダンス：
    - 既存UserInterface.search_documents()と連携
    - 並行検索実行でパフォーマンス最適化
    - 複数ランキング戦略をサポート
    """
    
    @abstractmethod
    async def hybrid_search(
        self,
        query: str,
        search_mode: SearchMode = SearchMode.HYBRID,
        ranking_strategy: RankingStrategy = RankingStrategy.SCORE_WEIGHTED,
        top_k: int = 10,
        category_filter: Optional[str] = None,
        user_context: Optional[UserContext] = None
    ) -> List[SearchResult]:
        """
        ハイブリッド検索実行
        
        Args:
            query: 検索クエリ
            search_mode: 検索モード
            ranking_strategy: ランキング戦略
            top_k: 取得件数
            category_filter: カテゴリフィルタ ('dataset', 'paper', 'poster')
            user_context: ユーザーコンテキスト
            
        Returns:
            List[SearchResult]: 統合検索結果
            
        Claude Code実装例：
        ```python
        async def hybrid_search(self, query, search_mode=SearchMode.HYBRID, ranking_strategy=RankingStrategy.SCORE_WEIGHTED, top_k=10, category_filter=None, user_context=None):
            results = []
            
            # 既存キーワード検索
            if search_mode in [SearchMode.KEYWORD_ONLY, SearchMode.HYBRID]:
                keyword_results = await self._existing_keyword_search(query, category_filter)
                results.extend(keyword_results)
            
            # ベクトル検索
            if search_mode in [SearchMode.VECTOR_ONLY, SearchMode.HYBRID]:
                vector_results = await self.vector_search_port.search_similar(
                    query, top_k, filter_metadata={'category': category_filter} if category_filter else None
                )
                results.extend(vector_results)
            
            # 結果統合・ランキング
            merged_results = await self._merge_and_rank(results, ranking_strategy)
            
            return merged_results[:top_k]
        ```
        """
        pass
    
    @abstractmethod
    async def search_with_filters(
        self,
        query: str,
        filters: Dict[str, Any],
        user_context: Optional[UserContext] = None
    ) -> List[SearchResult]:
        """
        フィルタ付き検索
        
        Args:
            query: 検索クエリ
            filters: {'category': 'paper', 'date_range': {...}, 'file_size': {...}}
            user_context: ユーザーコンテキスト
        """
        pass
    
    @abstractmethod
    async def get_search_suggestions(
        self,
        partial_query: str,
        user_context: Optional[UserContext] = None
    ) -> List[str]:
        """
        検索候補取得（オートコンプリート）
        
        Claude Code実装時の注意：
        - 既存文書のタイトル・キーワードから候補生成
        - ユーザーの検索履歴考慮
        - 人気検索クエリの活用
        """
        pass
    
    @abstractmethod
    async def analyze_search_performance(
        self,
        query: str,
        results: List[SearchResult],
        user_feedback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        検索性能分析
        
        Returns:
            Dict: {'precision': 0.8, 'recall': 0.6, 'response_time_ms': 150}
        """
        pass


# ========================================
# Implementation Helper Classes
# ========================================

class SearchPortRegistry:
    """
    検索ポートの統合管理クラス
    
    Claude Code実装ガイダンス：
    - 各検索ポートの実装を統合管理
    - 設定に基づく検索手法の有効/無効切り替え
    - フォールバック機能（ベクトル検索失敗時はキーワード検索）
    """
    
    def __init__(self):
        self.vector_search_port: Optional[VectorSearchPort] = None
        self.semantic_search_port: Optional[SemanticSearchPort] = None
        self.hybrid_search_port: Optional[HybridSearchPort] = None
        self._existing_search_function = None
    
    def register_vector_search_port(self, port: VectorSearchPort):
        """ベクトル検索ポート登録"""
        self.vector_search_port = port
    
    def register_semantic_search_port(self, port: SemanticSearchPort):
        """セマンティック検索ポート登録"""
        self.semantic_search_port = port
    
    def register_hybrid_search_port(self, port: HybridSearchPort):
        """ハイブリッド検索ポート登録"""
        self.hybrid_search_port = port
    
    def set_existing_search_function(self, search_func):
        """既存検索関数設定（UserInterface.search_documents）"""
        self._existing_search_function = search_func
    
    async def search(
        self,
        query: str,
        search_mode: SearchMode = SearchMode.HYBRID,
        **kwargs
    ) -> List[SearchResult]:
        """
        統合検索インターフェース
        
        Claude Code実装時の注意：
        - 利用可能な検索手法を自動判定
        - フォールバック機能実装
        - エラー時は既存検索で継続
        """
        try:
            if search_mode == SearchMode.HYBRID and self.hybrid_search_port:
                return await self.hybrid_search_port.hybrid_search(query, **kwargs)
            elif search_mode == SearchMode.VECTOR_ONLY and self.vector_search_port:
                return await self.vector_search_port.search_similar(query, **kwargs)
            elif search_mode == SearchMode.SEMANTIC and self.semantic_search_port:
                return await self.semantic_search_port.search_with_intent(query, **kwargs)
            else:
                # フォールバック：既存検索
                return await self._fallback_to_existing_search(query, **kwargs)
        except Exception as e:
            # エラー時フォールバック
            return await self._fallback_to_existing_search(query, **kwargs)
    
    async def _fallback_to_existing_search(self, query: str, **kwargs) -> List[SearchResult]:
        """既存検索システムへのフォールバック"""
        if self._existing_search_function:
            # 既存システムでの検索実行
            existing_results = self._existing_search_function(query)
            # SearchResult形式に変換
            return [self._convert_to_search_result(result) for result in existing_results]
        return []
    
    def _convert_to_search_result(self, existing_result: Dict[str, Any]) -> SearchResult:
        """既存検索結果をSearchResultに変換"""
        from .data_models import create_search_result_from_existing
        return create_search_result_from_existing(existing_result)


# ========================================
# Utility Functions for Claude Code
# ========================================

async def integrate_with_existing_search(
    user_interface_instance,
    vector_search_port: Optional[VectorSearchPort] = None
) -> SearchPortRegistry:
    """
    既存検索システムとの統合ヘルパー
    
    Claude Code実装時の使用例：
    ```python
    from ..ui.interface import UserInterface
    
    ui = UserInterface()
    registry = await integrate_with_existing_search(ui, vector_search_port)
    
    # 統合検索の実行
    results = await registry.search("機械学習", SearchMode.HYBRID)
    ```
    """
    registry = SearchPortRegistry()
    
    # 既存検索関数を登録
    registry.set_existing_search_function(user_interface_instance.search_documents)
    
    # ベクトル検索ポートがあれば登録
    if vector_search_port:
        registry.register_vector_search_port(vector_search_port)
    
    return registry


def create_metadata_filter(
    category: Optional[str] = None,
    date_range: Optional[Tuple[str, str]] = None,
    file_size_range: Optional[Tuple[int, int]] = None,
    user_context: Optional[UserContext] = None
) -> Dict[str, Any]:
    """
    メタデータフィルタ作成ヘルパー
    
    Claude Code実装ガイダンス：
    - ベクトル検索でのフィルタリング用
    - ユーザー権限も考慮したフィルタ生成
    """
    filters = {}
    
    if category:
        filters['category'] = category
    
    if date_range:
        filters['created_at'] = {'$gte': date_range[0], '$lte': date_range[1]}
    
    if file_size_range:
        filters['file_size'] = {'$gte': file_size_range[0], '$lte': file_size_range[1]}
    
    if user_context:
        # ユーザー権限に基づくフィルタ追加
        if not user_context.is_faculty():
            # 学生の場合はパブリック文書のみ
            filters['access_level'] = 'public'
    
    return filters