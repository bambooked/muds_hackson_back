"""
SemanticSearchPort実装

Instance B拡張: 高度なセマンティック検索機能
- 意図理解に基づく検索
- Google Gemini APIとの連携によるクエリ拡張
- 検索結果の説明生成
- 関連クエリ提案機能
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from .search_ports import SemanticSearchPort
from .data_models import SearchResult, DocumentMetadata, UserContext, SearchError
from .vector_search_impl import ChromaVectorSearchPort

logger = logging.getLogger(__name__)


class IntelligentSemanticSearchPort(SemanticSearchPort):
    """
    高度なセマンティック検索実装
    
    機能：
    - 意図理解に基づく検索クエリ拡張
    - Google Gemini APIとの連携
    - 検索結果の説明生成
    - 関連クエリ提案
    """
    
    def __init__(self, vector_search_port: Optional[ChromaVectorSearchPort] = None):
        self.vector_search_port = vector_search_port
        self._gemini_client = None
        self._intent_cache = {}  # 意図理解結果キャッシュ
        self._explanation_cache = {}  # 説明生成結果キャッシュ
        
        # Gemini APIクライアント初期化（遅延初期化）
        self._initialize_gemini_client()
    
    def _initialize_gemini_client(self):
        """Gemini APIクライアント初期化"""
        try:
            # 既存のGeminiClientを再利用
            from ..analyzer.gemini_client import GeminiClient
            self._gemini_client = GeminiClient()
            logger.info("Semantic search: Gemini client initialized")
        except Exception as e:
            logger.warning(f"Gemini client initialization failed: {e}")
            self._gemini_client = None
    
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
        
        Returns:
            List[SearchResult]: 意図理解検索結果
        """
        try:
            # 検索意図の理解・クエリ拡張
            expanded_queries = await self._understand_search_intent(query, intent_context)
            
            all_results = []
            
            # 拡張されたクエリで検索実行
            for expanded_query in expanded_queries:
                if self.vector_search_port and self.vector_search_port.is_initialized:
                    results = await self.vector_search_port.search_similar(
                        query=expanded_query,
                        top_k=top_k,
                        user_context=user_context
                    )
                    
                    # 意図理解による検索であることを明記
                    for result in results:
                        result.relevance_type = 'semantic'
                        result.explanation = f"Intent-based search for: '{expanded_query}'"
                    
                    all_results.extend(results)
            
            # 結果の重複排除・統合
            unified_results = self._unify_intent_results(all_results, query, top_k)
            
            logger.info(f"Intent-based search completed: {len(unified_results)} results for '{query}'")
            return unified_results
            
        except Exception as e:
            logger.error(f"Intent-based search failed for query '{query}': {e}")
            # フォールバック: 通常のベクトル検索
            if self.vector_search_port and self.vector_search_port.is_initialized:
                return await self.vector_search_port.search_similar(query, top_k, user_context=user_context)
            return []
    
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
        try:
            explained_results = []
            
            for result in results:
                # 説明生成
                explanation = await self._generate_result_explanation(query, result)
                
                # 説明を結果に追加
                enhanced_result = SearchResult(
                    document=result.document,
                    score=result.score,
                    relevance_type=result.relevance_type,
                    highlighted_content=result.highlighted_content,
                    explanation=explanation,
                    metadata=result.metadata
                )
                
                explained_results.append(enhanced_result)
            
            logger.info(f"Generated explanations for {len(explained_results)} search results")
            return explained_results
            
        except Exception as e:
            logger.error(f"Search result explanation failed: {e}")
            return results  # エラー時は元の結果を返す
    
    async def suggest_related_queries(
        self,
        query: str,
        user_context: Optional[UserContext] = None
    ) -> List[str]:
        """
        関連クエリ提案
        
        Args:
            query: 元クエリ
            user_context: ユーザーコンテキスト
        
        Returns:
            List[str]: 関連クエリ候補
        """
        try:
            related_queries = []
            
            # 1. Gemini APIによる関連クエリ生成
            if self._gemini_client:
                ai_suggestions = await self._generate_ai_related_queries(query)
                related_queries.extend(ai_suggestions)
            
            # 2. ベクトル検索による関連文書からの提案
            if self.vector_search_port and self.vector_search_port.is_initialized:
                similar_docs = await self.vector_search_port.search_similar(
                    query=query,
                    top_k=5,
                    similarity_threshold=0.4
                )
                
                # 関連文書のキーワード・タイトルから提案生成
                doc_suggestions = self._extract_queries_from_documents(similar_docs, query)
                related_queries.extend(doc_suggestions)
            
            # 3. クエリ拡張・同義語による提案
            expansion_suggestions = self._generate_query_expansions(query)
            related_queries.extend(expansion_suggestions)
            
            # 重複排除・フィルタリング
            unique_queries = []
            query_lower = query.lower()
            
            for suggestion in related_queries:
                if (suggestion.lower() != query_lower and 
                    suggestion not in unique_queries and 
                    len(suggestion) >= 2):
                    unique_queries.append(suggestion)
            
            # 最大10件まで
            final_suggestions = unique_queries[:10]
            
            logger.info(f"Generated {len(final_suggestions)} related queries for '{query}'")
            return final_suggestions
            
        except Exception as e:
            logger.error(f"Related query suggestion failed: {e}")
            return []
    
    # Private helper methods
    
    async def _understand_search_intent(self, query: str, intent_context: Optional[str] = None) -> List[str]:
        """検索意図理解・クエリ拡張"""
        try:
            # キャッシュチェック
            cache_key = f"{query}_{intent_context or ''}"
            if cache_key in self._intent_cache:
                return self._intent_cache[cache_key]
            
            expanded_queries = [query]  # 元クエリは必ず含める
            
            if self._gemini_client:
                # Gemini APIで意図理解・クエリ拡張
                intent_prompt = self._build_intent_understanding_prompt(query, intent_context)
                
                try:
                    response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        self._gemini_client.generate_response,
                        intent_prompt
                    )
                    
                    # レスポンスから拡張クエリを抽出
                    ai_expanded = self._parse_intent_response(response)
                    expanded_queries.extend(ai_expanded)
                    
                except Exception as e:
                    logger.warning(f"Gemini intent understanding failed: {e}")
            
            # 基本的なクエリ拡張（同義語・関連語）
            basic_expansions = self._basic_query_expansion(query)
            expanded_queries.extend(basic_expansions)
            
            # 重複排除
            unique_expanded = list(dict.fromkeys(expanded_queries))
            
            # キャッシュ保存（最大100件）
            if len(self._intent_cache) < 100:
                self._intent_cache[cache_key] = unique_expanded
            
            logger.debug(f"Intent understanding: '{query}' expanded to {len(unique_expanded)} queries")
            return unique_expanded[:5]  # 最大5個のクエリ
            
        except Exception as e:
            logger.error(f"Intent understanding failed: {e}")
            return [query]
    
    def _build_intent_understanding_prompt(self, query: str, intent_context: Optional[str] = None) -> str:
        """意図理解用プロンプト構築"""
        base_prompt = f"""
以下の検索クエリの意図を理解し、関連する検索キーワードを生成してください。

検索クエリ: "{query}"
"""
        
        if intent_context:
            base_prompt += f"検索コンテキスト: {intent_context}\n"
        
        base_prompt += """
研究データ管理システムでの検索なので、以下のカテゴリの文書が対象です：
- データセット（CSV、JSON、研究データ）
- 論文（PDF、学術論文）
- ポスター（PDF、研究発表資料）

関連するキーワードや同義語、より具体的な検索語句を3つまで提案してください。
一行ずつ、「- 」で始めて回答してください。

例：
- machine learning algorithms
- データ分析手法  
- statistical analysis
"""
        
        return base_prompt
    
    def _parse_intent_response(self, response: str) -> List[str]:
        """Gemini APIレスポンスから拡張クエリを抽出"""
        try:
            expanded_queries = []
            lines = response.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if line.startswith('- ') or line.startswith('• '):
                    query = line[2:].strip()
                    if query and len(query) >= 2:
                        expanded_queries.append(query)
            
            return expanded_queries[:3]  # 最大3件
            
        except Exception as e:
            logger.error(f"Intent response parsing failed: {e}")
            return []
    
    def _basic_query_expansion(self, query: str) -> List[str]:
        """基本的なクエリ拡張"""
        expansions = []
        query_lower = query.lower()
        
        # 英日翻訳マッピング
        translation_map = {
            'machine learning': '機械学習',
            'data analysis': 'データ分析',
            'research': '研究',
            'dataset': 'データセット',
            'paper': '論文',
            'poster': 'ポスター',
            'environment': '環境',
            'sustainability': '持続可能性',
            'analysis': '分析',
            '機械学習': 'machine learning',
            'データ分析': 'data analysis',
            '研究': 'research',
            '環境': 'environment',
            '分析': 'analysis'
        }
        
        # 翻訳による拡張
        for en, ja in translation_map.items():
            if en in query_lower:
                expansions.append(query.replace(en, ja))
            elif ja in query:
                expansions.append(query.replace(ja, en))
        
        # 同義語による拡張
        synonyms_map = {
            'machine learning': ['ML', 'artificial intelligence', 'AI'],
            'data analysis': ['data science', 'analytics', 'statistical analysis'],
            'research': ['study', 'investigation', 'academic research'],
            'environment': ['environmental', 'green', 'eco'],
            'sustainability': ['sustainable', 'green technology']
        }
        
        for base_term, synonyms in synonyms_map.items():
            if base_term in query_lower:
                for synonym in synonyms:
                    expansions.append(query.replace(base_term, synonym))
        
        return expansions[:3]  # 最大3件
    
    async def _generate_result_explanation(self, query: str, result: SearchResult) -> str:
        """検索結果の説明生成"""
        try:
            # キャッシュチェック
            cache_key = f"{query}_{result.document.id}_{result.document.category}"
            if cache_key in self._explanation_cache:
                return self._explanation_cache[cache_key]
            
            doc = result.document
            
            # 基本的な説明生成
            explanation_parts = []
            
            # スコアによる関連度説明
            if result.score >= 0.8:
                explanation_parts.append("高い関連性")
            elif result.score >= 0.5:
                explanation_parts.append("中程度の関連性")
            else:
                explanation_parts.append("低い関連性")
            
            # カテゴリ説明
            category_descriptions = {
                'dataset': 'データセット',
                'paper': '学術論文',
                'poster': '研究ポスター'
            }
            category_desc = category_descriptions.get(doc.category, doc.category)
            explanation_parts.append(f"{category_desc}文書")
            
            # 内容の関連性説明
            query_lower = query.lower()
            
            if doc.title and query_lower in doc.title.lower():
                explanation_parts.append("タイトルにクエリが含まれています")
            
            if doc.keywords and query_lower in doc.keywords.lower():
                explanation_parts.append("キーワードにクエリが含まれています")
            
            if doc.summary and query_lower in doc.summary.lower():
                explanation_parts.append("要約にクエリが含まれています")
            
            if doc.authors and query_lower in doc.authors.lower():
                explanation_parts.append("著者名にクエリが含まれています")
            
            # Gemini APIによる高度な説明生成（可能であれば）
            if self._gemini_client and len(explanation_parts) <= 2:
                ai_explanation = await self._generate_ai_explanation(query, result)
                if ai_explanation:
                    explanation_parts.append(ai_explanation)
            
            final_explanation = "、".join(explanation_parts) + f"（スコア: {result.score:.3f}）"
            
            # キャッシュ保存
            if len(self._explanation_cache) < 100:
                self._explanation_cache[cache_key] = final_explanation
            
            return final_explanation
            
        except Exception as e:
            logger.error(f"Result explanation generation failed: {e}")
            return f"関連度スコア: {result.score:.3f}"
    
    async def _generate_ai_explanation(self, query: str, result: SearchResult) -> Optional[str]:
        """AI による詳細説明生成"""
        try:
            doc = result.document
            
            explanation_prompt = f"""
検索クエリ「{query}」に対する文書の関連性を簡潔に説明してください。

文書情報：
- カテゴリ: {doc.category}
- タイトル: {doc.title or 'なし'}
- 著者: {doc.authors or 'なし'}
- 要約: {(doc.summary or '')[:200]}...
- キーワード: {doc.keywords or 'なし'}

なぜこの文書が検索クエリに関連するのか、1文で簡潔に説明してください。
"""
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self._gemini_client.generate_response,
                explanation_prompt
            )
            
            # レスポンスをクリーンアップ
            explanation = response.strip()
            if len(explanation) > 100:
                explanation = explanation[:100] + "..."
            
            return explanation
            
        except Exception as e:
            logger.warning(f"AI explanation generation failed: {e}")
            return None
    
    async def _generate_ai_related_queries(self, query: str) -> List[str]:
        """AI による関連クエリ生成"""
        try:
            if not self._gemini_client:
                return []
            
            related_prompt = f"""
検索クエリ「{query}」に関連する検索語句を提案してください。

研究データ管理システムでの検索なので、以下のカテゴリの文書が対象です：
- データセット（研究データ、統計データ）
- 論文（学術論文、研究論文）
- ポスター（研究発表、学会発表）

関連する検索語句を3つまで提案してください。
一行ずつ、「- 」で始めて回答してください。
"""
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                self._gemini_client.generate_response,
                related_prompt
            )
            
            return self._parse_intent_response(response)
            
        except Exception as e:
            logger.warning(f"AI related query generation failed: {e}")
            return []
    
    def _extract_queries_from_documents(self, documents: List[SearchResult], original_query: str) -> List[str]:
        """関連文書からクエリ候補を抽出"""
        try:
            suggestions = []
            original_lower = original_query.lower()
            
            for result in documents:
                doc = result.document
                
                # タイトルから重要な語句を抽出
                if doc.title:
                    title_words = doc.title.split()
                    for word in title_words:
                        if (len(word) >= 3 and 
                            word.lower() != original_lower and 
                            word not in suggestions):
                            suggestions.append(word)
                
                # キーワードから抽出
                if doc.keywords:
                    keywords = [kw.strip() for kw in doc.keywords.split(',')]
                    for keyword in keywords:
                        if (len(keyword) >= 3 and 
                            keyword.lower() != original_lower and 
                            keyword not in suggestions):
                            suggestions.append(keyword)
            
            return suggestions[:5]  # 最大5件
            
        except Exception as e:
            logger.error(f"Document query extraction failed: {e}")
            return []
    
    def _generate_query_expansions(self, query: str) -> List[str]:
        """クエリ拡張・同義語生成"""
        try:
            expansions = []
            query_lower = query.lower()
            
            # 複合語の分解
            if ' ' in query:
                words = query.split()
                if len(words) == 2:
                    # 2語の場合、個別の語も提案
                    expansions.extend(words)
            
            # 語尾変化
            if query_lower.endswith('ing'):
                base = query_lower[:-3]
                expansions.append(base)
                expansions.append(base + 'ed')
            
            if query_lower.endswith('ed'):
                base = query_lower[:-2]
                expansions.append(base)
                expansions.append(base + 'ing')
            
            # 複数形・単数形
            if query_lower.endswith('s') and len(query) > 3:
                expansions.append(query[:-1])  # 単数形
            else:
                expansions.append(query + 's')  # 複数形
            
            # 専門用語の略語展開
            abbreviations = {
                'AI': 'artificial intelligence',
                'ML': 'machine learning',
                'DL': 'deep learning',
                'NLP': 'natural language processing',
                'CV': 'computer vision'
            }
            
            for abbr, full in abbreviations.items():
                if abbr.lower() in query_lower:
                    expansions.append(query.replace(abbr, full))
                elif full in query_lower:
                    expansions.append(query.replace(full, abbr))
            
            return expansions[:3]  # 最大3件
            
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return []
    
    def _unify_intent_results(self, results: List[SearchResult], original_query: str, top_k: int) -> List[SearchResult]:
        """意図理解検索結果の統合"""
        try:
            # 重複排除（document.id + category でユニーク化）
            seen = set()
            unified = []
            
            # スコア順でソート
            results.sort(key=lambda x: x.score, reverse=True)
            
            for result in results:
                key = (result.document.id, result.document.category)
                if key not in seen:
                    seen.add(key)
                    
                    # 説明を更新（意図理解検索であることを明記）
                    result.explanation = f"Intent-based semantic search for '{original_query}' (score: {result.score:.3f})"
                    
                    unified.append(result)
                    
                    if len(unified) >= top_k:
                        break
            
            return unified
            
        except Exception as e:
            logger.error(f"Intent result unification failed: {e}")
            return results[:top_k]


# Factory function
def create_semantic_search_port(vector_search_port: Optional[ChromaVectorSearchPort] = None) -> IntelligentSemanticSearchPort:
    """SemanticSearchPortインスタンス作成"""
    return IntelligentSemanticSearchPort(vector_search_port)