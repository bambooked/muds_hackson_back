"""
統合検索エンジンクラス
分割された機能を統合して従来のインターフェースを提供
"""
from typing import List, Dict, Any, Optional

from ..database_handler import DatabaseHandler
from .query_parser import QueryParser
from .result_processor import ResultProcessor
from .similarity_calculator import SimilarityCalculator


class SearchEngine:
    """研究データの検索エンジン（リファクタリング版）"""
    
    def __init__(self, db_handler: Optional[DatabaseHandler] = None):
        """
        検索エンジンの初期化
        
        Args:
            db_handler: データベースハンドラ
        """
        self.db_handler = db_handler or DatabaseHandler()
        
        # 分割された機能クラスのインスタンス化
        self.query_parser = QueryParser()
        self.result_processor = ResultProcessor()
        self.similarity_calculator = SimilarityCalculator(self.db_handler)
    
    def search(self, query: str = None,
              filters: Optional[Dict[str, Any]] = None,
              sort_by: str = 'relevance',
              limit: int = 50,
              offset: int = 0) -> Dict[str, Any]:
        """
        高度な検索機能
        
        Args:
            query: 検索クエリ
            filters: フィルター条件
            sort_by: ソート基準（relevance, date, title）
            limit: 取得件数
            offset: オフセット
        
        Returns:
            検索結果と関連情報
        """
        # クエリの正規化と解析
        if query:
            normalized_query = self.query_parser.normalize_query(query)
            parsed_query = self.query_parser.parse_query(normalized_query)
            search_intent = self.query_parser.extract_search_intent(query)
        else:
            parsed_query = {'keywords': '', 'phrases': [], 'operators': []}
            search_intent = {'type': 'general'}
        
        # フィルターの統合
        filters = filters or {}
        
        # 検索意図からフィルターを自動設定
        if search_intent.get('data_type_preference') and not filters.get('data_type'):
            filters['data_type'] = search_intent['data_type_preference']
        
        if search_intent.get('research_field_hint') and not filters.get('research_field'):
            filters['research_field'] = search_intent['research_field_hint']
        
        # 基本検索の実行
        if query:
            # research_dataテーブルから検索
            research_results = self.db_handler.search_data(
                keyword=parsed_query.get('keywords'),
                data_type=filters.get('data_type'),
                research_field=filters.get('research_field'),
                limit=limit * 2  # スコアリングのため多めに取得
            )
            
            # データセットテーブルからも検索
            dataset_results = self._search_datasets(
                keyword=parsed_query.get('keywords'),
                data_type=filters.get('data_type'),
                research_field=filters.get('research_field'),
                limit=limit
            )
            
            # 結果を統合
            all_results = research_results + dataset_results
            
            # 検索結果のスコアリング
            scored_results = self.result_processor.score_results(all_results, parsed_query)
        else:
            # フィルターのみの検索
            research_results = self.db_handler.search_data(
                data_type=filters.get('data_type'),
                research_field=filters.get('research_field'),
                limit=limit * 2
            )
            
            dataset_results = self._search_datasets(
                data_type=filters.get('data_type'),
                research_field=filters.get('research_field'),
                limit=limit
            )
            
            scored_results = research_results + dataset_results
            
            # スコアを0で初期化
            for result in scored_results:
                result['_score'] = 0.0
        
        # ソート
        sorted_results = self.result_processor.sort_results(scored_results, sort_by)
        
        # ページネーション
        pagination_result = self.result_processor.apply_pagination(
            sorted_results, offset, limit
        )
        
        # ファセット情報の生成
        facets = self.result_processor.generate_facets(scored_results)
        
        # サジェスチョンの生成
        suggestions = self.result_processor.generate_suggestions(query, scored_results)
        
        # クエリ改善案の生成
        query_improvements = []
        if query:
            query_improvements = self.query_parser.suggest_query_improvements(
                query, len(scored_results)
            )
        
        return {
            'results': pagination_result['results'],
            'total_count': pagination_result['total_count'],
            'returned_count': pagination_result['returned_count'],
            'query': query,
            'parsed_query': parsed_query,
            'search_intent': search_intent,
            'filters': filters,
            'facets': facets,
            'suggestions': suggestions,
            'query_improvements': query_improvements,
            'offset': offset,
            'limit': limit,
            'has_more': pagination_result['has_more']
        }
    
    def get_similar_data(self, data_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        類似データを取得
        
        Args:
            data_id: 基準となるデータID
            limit: 取得件数
        
        Returns:
            類似データのリスト
        """
        return self.similarity_calculator.get_similar_data(data_id, limit)
    
    def get_trending_topics(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        トレンディングトピックを取得
        
        Args:
            days: 過去何日間のデータを対象とするか
        
        Returns:
            トレンディングトピックのリスト
        """
        return self.similarity_calculator.get_trending_topics(days)
    
    # === 後方互換性のためのメソッド ===
    
    def _parse_query(self, query: str) -> Dict[str, Any]:
        """後方互換性のためのクエリ解析メソッド"""
        return self.query_parser.parse_query(query)
    
    def _score_results(self, results: List[Dict[str, Any]], 
                      parsed_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """後方互換性のためのスコアリングメソッド"""
        return self.result_processor.score_results(results, parsed_query)
    
    def _sort_results(self, results: List[Dict[str, Any]], 
                     sort_by: str) -> List[Dict[str, Any]]:
        """後方互換性のためのソートメソッド"""
        return self.result_processor.sort_results(results, sort_by)
    
    def _generate_facets(self, results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, int]]]:
        """後方互換性のためのファセット生成メソッド"""
        return self.result_processor.generate_facets(results)
    
    def _generate_suggestions(self, query: Optional[str], 
                            results: List[Dict[str, Any]]) -> List[str]:
        """後方互換性のためのサジェスト生成メソッド"""
        return self.result_processor.generate_suggestions(query, results)
    
    def _extract_keywords(self, data: Dict[str, Any]) -> List[str]:
        """後方互換性のためのキーワード抽出メソッド"""
        return self.similarity_calculator._extract_keywords(data)
    
    def _search_datasets(self, keyword: str = None,
                        data_type: str = None,
                        research_field: str = None,
                        limit: int = 50) -> List[Dict[str, Any]]:
        """
        データセットテーブルから検索
        
        Args:
            keyword: 検索キーワード
            data_type: データタイプ
            research_field: 研究分野
            limit: 取得件数
        
        Returns:
            検索結果のリスト
        """
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            # SQLクエリの構築
            conditions = []
            params = []
            
            if keyword:
                conditions.append("(name LIKE ? OR description LIKE ? OR tags LIKE ?)")
                keyword_pattern = f"%{keyword}%"
                params.extend([keyword_pattern, keyword_pattern, keyword_pattern])
            
            if data_type:
                conditions.append("data_type = ?")
                params.append(data_type)
            
            if research_field:
                conditions.append("research_field = ?")
                params.append(research_field)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"""
                SELECT 
                    dataset_id as data_id,
                    name as title,
                    description,
                    research_field,
                    data_type,
                    file_count,
                    directory_path as file_path,
                    tags,
                    quality_score,
                    created_at
                FROM datasets
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ?
            """
            
            params.append(limit)
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                # カラム名でアクセス
                row_dict = {
                    'data_id': row[0],
                    'title': row[1],
                    'description': row[2] or '',
                    'research_field': row[3] or '未分類',
                    'data_type': row[4] or 'dataset',
                    'file_count': row[5] or 0,
                    'file_path': row[6] or '',
                    'tags': row[7] or '[]',
                    'quality_score': row[8] or 0.5,
                    'created_at': row[9],
                    'summary': row[2] or '',  # descriptionをsummaryとしても使用
                    'source_type': 'dataset'  # データセットからの結果であることを示す
                }
                results.append(row_dict)
            
            return results
    
    def _calculate_similarity(self, base_features: Dict[str, Any], 
                            candidate: Dict[str, Any]) -> float:
        """後方互換性のための類似度計算メソッド"""
        return self.similarity_calculator._calculate_similarity(base_features, candidate)