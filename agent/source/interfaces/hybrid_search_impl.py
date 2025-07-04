"""
HybridSearchPort実装

Instance B拡張: キーワード検索とベクトル検索の統合
- 既存キーワード検索とベクトル検索の並行実行
- 複数ランキング戦略によるスコア統合
- 高度なフィルタリング機能
- 検索候補・性能分析機能
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .search_ports import HybridSearchPort, SearchMode, RankingStrategy
from .data_models import SearchResult, DocumentMetadata, UserContext, SearchError
from .vector_search_impl import ChromaVectorSearchPort

logger = logging.getLogger(__name__)


class EnhancedHybridSearchPort(HybridSearchPort):
    """
    ハイブリッド検索の拡張実装
    
    機能：
    - キーワード検索 + ベクトル検索の統合
    - 複数ランキング戦略（RRF, Score-weighted, Re-ranking）
    - 高度なフィルタリング
    - 検索候補・性能分析
    """
    
    def __init__(self, vector_search_port: Optional[ChromaVectorSearchPort] = None):
        self.vector_search_port = vector_search_port
        self._existing_search_function = None
        self._search_history = []  # 検索履歴（候補生成用）
        self._popular_queries = {}  # 人気クエリ統計
    
    def set_existing_search_function(self, search_func):
        """既存検索関数設定"""
        self._existing_search_function = search_func
    
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
            category_filter: カテゴリフィルタ
            user_context: ユーザーコンテキスト
        
        Returns:
            List[SearchResult]: 統合検索結果
        """
        try:
            start_time = datetime.now()
            results = []
            
            # 検索履歴記録
            self._record_search_query(query)
            
            # 検索モード別実行
            if search_mode in [SearchMode.KEYWORD_ONLY, SearchMode.HYBRID]:
                # キーワード検索実行
                keyword_results = await self._execute_keyword_search(query, category_filter)
                results.extend(keyword_results)
            
            if search_mode in [SearchMode.VECTOR_ONLY, SearchMode.HYBRID] and self.vector_search_port:
                # ベクトル検索実行
                vector_results = await self._execute_vector_search(
                    query, top_k, category_filter, user_context
                )
                results.extend(vector_results)
            
            # 結果統合・ランキング
            merged_results = await self._merge_and_rank(
                results, ranking_strategy, query, top_k
            )
            
            # 実行時間記録
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(f"Hybrid search completed: {len(merged_results)} results for '{query}' in {execution_time:.1f}ms")
            
            return merged_results
            
        except Exception as e:
            logger.error(f"Hybrid search failed for query '{query}': {e}")
            # フォールバック: キーワード検索のみ
            return await self._execute_keyword_search(query, category_filter)
    
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
            filters: フィルタ設定
            user_context: ユーザーコンテキスト
        
        Returns:
            List[SearchResult]: フィルタ済み検索結果
        """
        try:
            # フィルタ解析
            category = filters.get('category')
            date_range = filters.get('date_range')
            file_size_range = filters.get('file_size_range')
            authors_filter = filters.get('authors')
            keywords_filter = filters.get('keywords')
            
            # ベース検索実行
            results = await self.hybrid_search(
                query=query,
                search_mode=SearchMode.HYBRID,
                category_filter=category,
                user_context=user_context
            )
            
            # 追加フィルタ適用
            filtered_results = []
            for result in results:
                # 日付範囲フィルタ
                if date_range and result.document.created_at:
                    created_at = result.document.created_at
                    start_date = datetime.fromisoformat(date_range.get('start', '1900-01-01'))
                    end_date = datetime.fromisoformat(date_range.get('end', '2100-12-31'))
                    if not (start_date <= created_at <= end_date):
                        continue
                
                # ファイルサイズフィルタ
                if file_size_range:
                    file_size = result.document.file_size
                    min_size = file_size_range.get('min', 0)
                    max_size = file_size_range.get('max', float('inf'))
                    if not (min_size <= file_size <= max_size):
                        continue
                
                # 著者フィルタ
                if authors_filter and result.document.authors:
                    if authors_filter.lower() not in result.document.authors.lower():
                        continue
                
                # キーワードフィルタ
                if keywords_filter and result.document.keywords:
                    keywords = result.document.keywords.lower()
                    if not any(kw.lower() in keywords for kw in keywords_filter):
                        continue
                
                # ユーザー権限フィルタ
                if user_context and not self._check_user_access(result.document, user_context):
                    continue
                
                filtered_results.append(result)
            
            logger.info(f"Filtered search: {len(filtered_results)}/{len(results)} results after filtering")
            return filtered_results
            
        except Exception as e:
            logger.error(f"Filtered search failed: {e}")
            raise SearchError(f"Filtered search failed: {e}")
    
    async def get_search_suggestions(
        self,
        partial_query: str,
        user_context: Optional[UserContext] = None
    ) -> List[str]:
        """
        検索候補取得（オートコンプリート）
        
        Args:
            partial_query: 部分クエリ
            user_context: ユーザーコンテキスト
        
        Returns:
            List[str]: 検索候補リスト
        """
        try:
            suggestions = []
            partial_lower = partial_query.lower()
            
            # 1. 検索履歴からの候補
            history_suggestions = [
                query for query in self._search_history
                if partial_lower in query.lower() and query not in suggestions
            ]
            suggestions.extend(history_suggestions[:3])
            
            # 2. 人気クエリからの候補
            popular_suggestions = [
                query for query, count in sorted(self._popular_queries.items(), key=lambda x: x[1], reverse=True)
                if partial_lower in query.lower() and query not in suggestions
            ]
            suggestions.extend(popular_suggestions[:3])
            
            # 3. 文書タイトル・キーワードからの候補
            if self.vector_search_port and len(partial_query) >= 2:
                # ベクトル検索で関連文書を取得
                similar_docs = await self.vector_search_port.search_similar(
                    query=partial_query,
                    top_k=5,
                    similarity_threshold=0.3
                )
                
                for result in similar_docs:
                    doc = result.document
                    # タイトルから候補生成
                    if doc.title and len(doc.title) > len(partial_query):
                        if partial_lower in doc.title.lower() and doc.title not in suggestions:
                            suggestions.append(doc.title)
                    
                    # キーワードから候補生成
                    if doc.keywords:
                        keywords = doc.keywords.split(',')
                        for keyword in keywords:
                            keyword = keyword.strip()
                            if len(keyword) > len(partial_query) and partial_lower in keyword.lower():
                                if keyword not in suggestions:
                                    suggestions.append(keyword)
            
            # 4. デフォルト候補（カテゴリ・一般用語）
            default_suggestions = [
                "データ分析", "機械学習", "research", "sustainability", "analysis",
                "dataset", "paper", "poster", "環境", "研究"
            ]
            for suggestion in default_suggestions:
                if partial_lower in suggestion.lower() and suggestion not in suggestions:
                    suggestions.append(suggestion)
            
            # 重複排除・長さ制限
            unique_suggestions = list(dict.fromkeys(suggestions))[:10]
            
            logger.debug(f"Generated {len(unique_suggestions)} suggestions for '{partial_query}'")
            return unique_suggestions
            
        except Exception as e:
            logger.error(f"Search suggestions failed: {e}")
            return []
    
    async def analyze_search_performance(
        self,
        query: str,
        results: List[SearchResult],
        user_feedback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        検索性能分析
        
        Args:
            query: 検索クエリ
            results: 検索結果
            user_feedback: ユーザーフィードバック
        
        Returns:
            Dict: 性能分析結果
        """
        try:
            analysis = {
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "total_results": len(results),
                "performance_metrics": {},
                "quality_metrics": {},
                "recommendations": []
            }
            
            # パフォーマンス指標
            if results:
                scores = [r.score for r in results]
                analysis["performance_metrics"] = {
                    "avg_score": sum(scores) / len(scores),
                    "max_score": max(scores),
                    "min_score": min(scores),
                    "score_variance": self._calculate_variance(scores)
                }
                
                # カテゴリ分布
                categories = {}
                for result in results:
                    cat = result.document.category
                    categories[cat] = categories.get(cat, 0) + 1
                analysis["category_distribution"] = categories
                
                # 検索タイプ分布
                search_types = {}
                for result in results:
                    search_type = result.relevance_type
                    search_types[search_type] = search_types.get(search_type, 0) + 1
                analysis["search_type_distribution"] = search_types
            
            # 品質指標（ユーザーフィードバックがある場合）
            if user_feedback:
                clicked_results = user_feedback.get('clicked_results', [])
                relevant_results = user_feedback.get('relevant_results', [])
                
                if clicked_results:
                    # CTR (Click Through Rate)
                    ctr = len(clicked_results) / len(results) if results else 0
                    analysis["quality_metrics"]["ctr"] = ctr
                
                if relevant_results:
                    # Precision@K
                    precision_at_5 = len([r for r in relevant_results[:5]]) / min(5, len(results))
                    precision_at_10 = len([r for r in relevant_results[:10]]) / min(10, len(results))
                    analysis["quality_metrics"]["precision_at_5"] = precision_at_5
                    analysis["quality_metrics"]["precision_at_10"] = precision_at_10
            
            # 推奨事項生成
            recommendations = []
            
            if len(results) == 0:
                recommendations.append("No results found. Try broader keywords or different search terms.")
            elif len(results) < 3:
                recommendations.append("Few results found. Consider using related keywords or synonyms.")
            
            if analysis["performance_metrics"].get("avg_score", 1.0) < 0.3:
                recommendations.append("Low relevance scores. Consider refining search query.")
            
            if len(set(r.document.category for r in results)) == 1:
                recommendations.append("Results from single category. Try broader search for diverse results.")
            
            analysis["recommendations"] = recommendations
            
            logger.info(f"Search performance analysis completed for query '{query}'")
            return analysis
            
        except Exception as e:
            logger.error(f"Search performance analysis failed: {e}")
            return {"error": str(e)}
    
    # Private helper methods
    
    async def _execute_keyword_search(self, query: str, category_filter: Optional[str]) -> List[SearchResult]:
        """既存キーワード検索実行"""
        try:
            if not self._existing_search_function:
                return []
            
            # 既存検索実行（同期関数を非同期で実行）
            loop = asyncio.get_event_loop()
            keyword_results = await loop.run_in_executor(
                None, 
                self._existing_search_function, 
                query
            )
            
            # SearchResult形式に変換
            converted_results = []
            for result in keyword_results:
                if isinstance(result, dict):
                    # 既存形式からDocumentMetadata作成
                    from .data_models import create_document_metadata_from_existing
                    document = create_document_metadata_from_existing(result)
                    
                    search_result = SearchResult(
                        document=document,
                        score=1.0,  # キーワード検索は一律1.0
                        relevance_type='keyword',
                        explanation="Keyword match"
                    )
                    converted_results.append(search_result)
            
            # カテゴリフィルタ適用
            if category_filter:
                converted_results = [
                    r for r in converted_results 
                    if r.document.category == category_filter
                ]
            
            return converted_results
            
        except Exception as e:
            logger.error(f"Keyword search execution failed: {e}")
            return []
    
    async def _execute_vector_search(
        self, 
        query: str, 
        top_k: int, 
        category_filter: Optional[str],
        user_context: Optional[UserContext]
    ) -> List[SearchResult]:
        """ベクトル検索実行"""
        try:
            if not self.vector_search_port or not self.vector_search_port.is_initialized:
                return []
            
            # フィルタ設定
            filter_metadata = None
            if category_filter:
                filter_metadata = {"category": category_filter}
            
            # ベクトル検索実行
            vector_results = await self.vector_search_port.search_similar(
                query=query,
                top_k=top_k,
                filter_metadata=filter_metadata,
                user_context=user_context
            )
            
            return vector_results
            
        except Exception as e:
            logger.error(f"Vector search execution failed: {e}")
            return []
    
    async def _merge_and_rank(
        self, 
        results: List[SearchResult], 
        ranking_strategy: RankingStrategy,
        query: str,
        top_k: int
    ) -> List[SearchResult]:
        """検索結果統合・ランキング"""
        try:
            if ranking_strategy == RankingStrategy.SIMPLE_MERGE:
                return self._simple_merge(results, top_k)
            elif ranking_strategy == RankingStrategy.SCORE_WEIGHTED:
                return self._score_weighted_merge(results, top_k)
            elif ranking_strategy == RankingStrategy.RRF:
                return await self._reciprocal_rank_fusion(results, top_k)
            elif ranking_strategy == RankingStrategy.RERANK:
                return await self._rerank_results(results, query, top_k)
            else:
                return self._simple_merge(results, top_k)
                
        except Exception as e:
            logger.error(f"Result merging failed: {e}")
            return results[:top_k]
    
    def _simple_merge(self, results: List[SearchResult], top_k: int) -> List[SearchResult]:
        """単純マージ（重複排除+スコア順）"""
        # ID+カテゴリで重複チェック
        seen = set()
        merged = []
        
        # スコア順でソート
        results.sort(key=lambda x: x.score, reverse=True)
        
        for result in results:
            key = (result.document.id, result.document.category)
            if key not in seen:
                seen.add(key)
                merged.append(result)
                if len(merged) >= top_k:
                    break
        
        return merged
    
    def _score_weighted_merge(self, results: List[SearchResult], top_k: int) -> List[SearchResult]:
        """スコア重み付けマージ"""
        # 検索タイプ別重み
        weights = {
            'keyword': 0.4,
            'semantic': 0.6,
            'vector': 0.6
        }
        
        # 重み付けスコア計算
        for result in results:
            weight = weights.get(result.relevance_type, 0.5)
            result.score = result.score * weight
        
        return self._simple_merge(results, top_k)
    
    async def _reciprocal_rank_fusion(self, results: List[SearchResult], top_k: int) -> List[SearchResult]:
        """Reciprocal Rank Fusion (RRF)"""
        try:
            # 検索タイプ別ランキング作成
            rankings = {}
            for result in results:
                search_type = result.relevance_type
                if search_type not in rankings:
                    rankings[search_type] = []
                rankings[search_type].append(result)
            
            # 各ランキングでスコア順ソート
            for search_type in rankings:
                rankings[search_type].sort(key=lambda x: x.score, reverse=True)
            
            # RRFスコア計算
            rrf_scores = {}
            k = 60  # RRF定数
            
            for search_type, ranked_results in rankings.items():
                for rank, result in enumerate(ranked_results, 1):
                    doc_key = (result.document.id, result.document.category)
                    rrf_score = 1.0 / (k + rank)
                    
                    if doc_key not in rrf_scores:
                        rrf_scores[doc_key] = {'score': 0.0, 'result': result}
                    rrf_scores[doc_key]['score'] += rrf_score
            
            # RRFスコア順でソート
            final_results = []
            for doc_key, data in sorted(rrf_scores.items(), key=lambda x: x[1]['score'], reverse=True):
                result = data['result']
                result.score = data['score']
                result.explanation = f"RRF score: {data['score']:.3f}"
                final_results.append(result)
            
            return final_results[:top_k]
            
        except Exception as e:
            logger.error(f"RRF merge failed: {e}")
            return self._simple_merge(results, top_k)
    
    async def _rerank_results(self, results: List[SearchResult], query: str, top_k: int) -> List[SearchResult]:
        """高度なリランキング"""
        try:
            # シンプルなリランキング実装
            # (実際の実装では、より高度なリランキングモデルを使用)
            
            reranked = []
            query_lower = query.lower()
            
            for result in results:
                doc = result.document
                rerank_score = result.score
                
                # タイトル一致ボーナス
                if doc.title and query_lower in doc.title.lower():
                    rerank_score += 0.2
                
                # 著者一致ボーナス
                if doc.authors and query_lower in doc.authors.lower():
                    rerank_score += 0.1
                
                # キーワード一致ボーナス
                if doc.keywords and query_lower in doc.keywords.lower():
                    rerank_score += 0.15
                
                # 要約一致ボーナス
                if doc.summary and query_lower in doc.summary.lower():
                    rerank_score += 0.1
                
                result.score = min(rerank_score, 1.0)  # 1.0を上限
                result.explanation = f"Reranked score: {result.score:.3f}"
                reranked.append(result)
            
            # リランクスコア順でソート
            reranked.sort(key=lambda x: x.score, reverse=True)
            return reranked[:top_k]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return results[:top_k]
    
    def _record_search_query(self, query: str):
        """検索クエリ履歴記録"""
        # 検索履歴記録（最新20件）
        if query not in self._search_history:
            self._search_history.append(query)
            if len(self._search_history) > 20:
                self._search_history.pop(0)
        
        # 人気クエリ統計更新
        self._popular_queries[query] = self._popular_queries.get(query, 0) + 1
    
    def _check_user_access(self, document: DocumentMetadata, user_context: UserContext) -> bool:
        """ユーザーアクセス権限チェック"""
        try:
            # 基本的なアクセス制御実装
            if not user_context:
                return True  # ユーザーコンテキストなしは全てアクセス可能
            
            # 管理者は全てアクセス可能
            if 'admin' in user_context.roles:
                return True
            
            # 教員は全てアクセス可能
            if user_context.is_faculty():
                return True
            
            # 学生の場合、パブリック文書のみ
            if 'student' in user_context.roles:
                access_level = document.access_permissions.get('access_level', 'public')
                return access_level == 'public'
            
            return True  # デフォルトはアクセス可能
            
        except Exception as e:
            logger.error(f"User access check failed: {e}")
            return True  # エラー時はアクセス可能
    
    def _calculate_variance(self, scores: List[float]) -> float:
        """分散計算"""
        if len(scores) <= 1:
            return 0.0
        
        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / len(scores)
        return variance


# Factory function
def create_hybrid_search_port(vector_search_port: Optional[ChromaVectorSearchPort] = None) -> EnhancedHybridSearchPort:
    """HybridSearchPortインスタンス作成"""
    return EnhancedHybridSearchPort(vector_search_port)