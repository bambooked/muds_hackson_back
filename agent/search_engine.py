"""
検索エンジンモジュール
高度な検索機能とフィルタリングを提供
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json

from .database_handler import DatabaseHandler


class SearchEngine:
    """研究データの検索エンジン"""
    
    def __init__(self, db_handler: Optional[DatabaseHandler] = None):
        """
        検索エンジンの初期化
        
        Args:
            db_handler: データベースハンドラ
        """
        self.db_handler = db_handler or DatabaseHandler()
    
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
        # フィルターの初期化
        filters = filters or {}
        
        # 基本検索の実行
        if query:
            # クエリの解析
            parsed_query = self._parse_query(query)
            
            # キーワード検索
            results = self.db_handler.search_data(
                keyword=parsed_query['keywords'],
                data_type=filters.get('data_type'),
                research_field=filters.get('research_field'),
                limit=limit * 2  # スコアリングのため多めに取得
            )
            
            # 検索結果のスコアリングとランキング
            scored_results = self._score_results(results, parsed_query)
            
            # ソート
            sorted_results = self._sort_results(scored_results, sort_by)
            
            # ページネーション
            final_results = sorted_results[offset:offset + limit]
        else:
            # フィルターのみの検索
            results = self.db_handler.search_data(
                data_type=filters.get('data_type'),
                research_field=filters.get('research_field'),
                limit=limit
            )
            final_results = results
        
        # ファセット情報の生成
        facets = self._generate_facets(results)
        
        # サジェスチョンの生成
        suggestions = self._generate_suggestions(query, results)
        
        return {
            'results': final_results,
            'total_count': len(results),
            'returned_count': len(final_results),
            'query': query,
            'filters': filters,
            'facets': facets,
            'suggestions': suggestions,
            'offset': offset,
            'limit': limit
        }
    
    def _parse_query(self, query: str) -> Dict[str, Any]:
        """
        検索クエリを解析
        
        Args:
            query: 検索クエリ
        
        Returns:
            解析結果
        """
        parsed = {
            'original': query,
            'keywords': query,
            'operators': [],
            'phrases': []
        }
        
        # フレーズ検索の抽出（"..."で囲まれた部分）
        phrase_pattern = r'"([^"]+)"'
        phrases = re.findall(phrase_pattern, query)
        parsed['phrases'] = phrases
        
        # フレーズを除いたキーワード
        keywords = re.sub(phrase_pattern, '', query).strip()
        parsed['keywords'] = keywords
        
        # 検索演算子の検出（AND, OR, NOT）
        if ' AND ' in query.upper():
            parsed['operators'].append('AND')
        if ' OR ' in query.upper():
            parsed['operators'].append('OR')
        if ' NOT ' in query.upper():
            parsed['operators'].append('NOT')
        
        return parsed
    
    def _score_results(self, results: List[Dict[str, Any]], 
                      parsed_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        検索結果にスコアを付与
        
        Args:
            results: 検索結果
            parsed_query: 解析済みクエリ
        
        Returns:
            スコア付き結果
        """
        scored_results = []
        keywords = parsed_query['keywords'].lower().split()
        
        for result in results:
            score = 0.0
            
            # タイトルマッチのスコア
            title = (result.get('title') or '').lower()
            for keyword in keywords:
                if keyword in title:
                    score += 10.0  # タイトルマッチは高スコア
            
            # 概要マッチのスコア
            summary = (result.get('summary') or '').lower()
            for keyword in keywords:
                if keyword in summary:
                    score += 5.0
            
            # 研究分野マッチのスコア
            field = (result.get('research_field') or '').lower()
            for keyword in keywords:
                if keyword in field:
                    score += 3.0
            
            # フレーズマッチのボーナス
            for phrase in parsed_query['phrases']:
                if phrase.lower() in title:
                    score += 15.0
                elif phrase.lower() in summary:
                    score += 8.0
            
            # 最近更新されたデータにボーナス
            if result.get('updated_at'):
                try:
                    updated = datetime.fromisoformat(result['updated_at'])
                    days_old = (datetime.now() - updated).days
                    if days_old < 7:
                        score += 2.0
                    elif days_old < 30:
                        score += 1.0
                except:
                    pass
            
            result['_score'] = score
            scored_results.append(result)
        
        return scored_results
    
    def _sort_results(self, results: List[Dict[str, Any]], 
                     sort_by: str) -> List[Dict[str, Any]]:
        """
        検索結果をソート
        
        Args:
            results: 検索結果
            sort_by: ソート基準
        
        Returns:
            ソート済み結果
        """
        if sort_by == 'relevance':
            return sorted(results, key=lambda x: x.get('_score', 0), reverse=True)
        elif sort_by == 'date':
            return sorted(results, key=lambda x: x.get('updated_at', ''), reverse=True)
        elif sort_by == 'title':
            return sorted(results, key=lambda x: x.get('title', ''))
        else:
            return results
    
    def _generate_facets(self, results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, int]]]:
        """
        ファセット情報を生成
        
        Args:
            results: 検索結果
        
        Returns:
            ファセット情報
        """
        facets = {
            'data_type': {},
            'research_field': {}
        }
        
        # データタイプの集計
        for result in results:
            data_type = result.get('data_type', 'unknown')
            facets['data_type'][data_type] = facets['data_type'].get(data_type, 0) + 1
        
        # 研究分野の集計
        for result in results:
            field = result.get('research_field', '未分類')
            if field:
                facets['research_field'][field] = facets['research_field'].get(field, 0) + 1
        
        # リスト形式に変換
        return {
            'data_type': [
                {'value': k, 'count': v} 
                for k, v in sorted(facets['data_type'].items(), key=lambda x: x[1], reverse=True)
            ],
            'research_field': [
                {'value': k, 'count': v} 
                for k, v in sorted(facets['research_field'].items(), key=lambda x: x[1], reverse=True)
            ][:10]  # 上位10件のみ
        }
    
    def _generate_suggestions(self, query: Optional[str], 
                            results: List[Dict[str, Any]]) -> List[str]:
        """
        検索サジェスチョンを生成
        
        Args:
            query: 検索クエリ
            results: 検索結果
        
        Returns:
            サジェスチョンリスト
        """
        suggestions = []
        
        if not query or len(results) == 0:
            # 最近の検索履歴からサジェスト
            history = self.db_handler.get_search_history(limit=5)
            suggestions = [h['query'] for h in history]
        else:
            # 検索結果から関連キーワードを抽出
            field_counts = {}
            
            for result in results[:20]:  # 上位20件から抽出
                field = result.get('research_field')
                if field and field != '未分類':
                    field_counts[field] = field_counts.get(field, 0) + 1
            
            # 頻出する研究分野をサジェスト
            sorted_fields = sorted(field_counts.items(), key=lambda x: x[1], reverse=True)
            for field, count in sorted_fields[:3]:
                if field.lower() not in query.lower():
                    suggestions.append(f"{query} {field}")
        
        return suggestions[:5]  # 最大5件
    
    def get_similar_data(self, data_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        類似データを取得
        
        Args:
            data_id: 基準となるデータID
            limit: 取得件数
        
        Returns:
            類似データのリスト
        """
        # 基準データの取得
        base_data = self.db_handler.get_data_by_id(data_id)
        if not base_data:
            return []
        
        # 類似度計算のための特徴抽出
        base_features = {
            'type': base_data.get('data_type'),
            'field': base_data.get('research_field'),
            'keywords': self._extract_keywords(base_data)
        }
        
        # 同じタイプまたは分野のデータを検索
        candidates = []
        
        # 同じデータタイプを検索
        if base_features['type']:
            type_results = self.db_handler.search_data(
                data_type=base_features['type'],
                limit=50
            )
            candidates.extend(type_results)
        
        # 同じ研究分野を検索
        if base_features['field']:
            field_results = self.db_handler.search_data(
                research_field=base_features['field'],
                limit=50
            )
            candidates.extend(field_results)
        
        # 重複を除去し、自身を除外
        seen = set()
        unique_candidates = []
        for candidate in candidates:
            if candidate['data_id'] != data_id and candidate['data_id'] not in seen:
                seen.add(candidate['data_id'])
                unique_candidates.append(candidate)
        
        # 類似度スコアを計算
        scored_candidates = []
        for candidate in unique_candidates:
            score = self._calculate_similarity(base_features, candidate)
            candidate['_similarity_score'] = score
            scored_candidates.append(candidate)
        
        # スコアでソートして上位を返す
        sorted_candidates = sorted(
            scored_candidates, 
            key=lambda x: x['_similarity_score'], 
            reverse=True
        )
        
        return sorted_candidates[:limit]
    
    def _extract_keywords(self, data: Dict[str, Any]) -> List[str]:
        """
        データからキーワードを抽出
        
        Args:
            data: データ辞書
        
        Returns:
            キーワードリスト
        """
        keywords = []
        
        # メタデータからキーワードを抽出
        metadata = data.get('metadata', {})
        if isinstance(metadata, dict) and 'keywords' in metadata:
            keywords.extend(metadata['keywords'])
        
        # タイトルから単語を抽出
        title = data.get('title', '')
        if title:
            # 簡易的な単語分割
            words = re.findall(r'\w+', title.lower())
            keywords.extend([w for w in words if len(w) > 2])
        
        return keywords
    
    def _calculate_similarity(self, base_features: Dict[str, Any], 
                            candidate: Dict[str, Any]) -> float:
        """
        二つのデータの類似度を計算
        
        Args:
            base_features: 基準データの特徴
            candidate: 比較対象データ
        
        Returns:
            類似度スコア（0-1）
        """
        score = 0.0
        
        # データタイプの一致
        if base_features['type'] == candidate.get('data_type'):
            score += 0.3
        
        # 研究分野の一致
        if base_features['field'] == candidate.get('research_field'):
            score += 0.4
        
        # キーワードの重複
        candidate_keywords = self._extract_keywords(candidate)
        if base_features['keywords'] and candidate_keywords:
            common_keywords = set(base_features['keywords']) & set(candidate_keywords)
            if len(base_features['keywords']) > 0:
                keyword_score = len(common_keywords) / len(base_features['keywords'])
                score += 0.3 * keyword_score
        
        return min(score, 1.0)
    
    def get_trending_topics(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        トレンディングトピックを取得
        
        Args:
            days: 過去何日間のデータを対象とするか
        
        Returns:
            トレンディングトピックのリスト
        """
        # 最近のデータを取得
        recent_data = self.db_handler.search_data(limit=100)
        
        # 日付でフィルタリング
        cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
        recent_data = [
            d for d in recent_data
            if d.get('updated_at') and 
            datetime.fromisoformat(d['updated_at']).timestamp() > cutoff_date
        ]
        
        # 研究分野の集計
        field_counts = {}
        for data in recent_data:
            field = data.get('research_field', '未分類')
            if field:
                field_counts[field] = field_counts.get(field, 0) + 1
        
        # トレンドスコアの計算（件数と新しさを考慮）
        trending = []
        for field, count in field_counts.items():
            # 該当分野の最新データを取得
            field_data = [d for d in recent_data if d.get('research_field') == field]
            if field_data:
                latest = max(
                    field_data, 
                    key=lambda x: x.get('updated_at', '')
                )
                
                trending.append({
                    'topic': field,
                    'count': count,
                    'latest_update': latest.get('updated_at'),
                    'trend_score': count * 1.5  # シンプルなスコア計算
                })
        
        # スコアでソート
        trending.sort(key=lambda x: x['trend_score'], reverse=True)
        
        return trending[:10]  # 上位10件