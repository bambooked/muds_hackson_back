"""
類似度計算機能
データ間の類似度計算とトレンド分析
"""
import re
from typing import List, Dict, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict

from ..database_handler import DatabaseHandler


class SimilarityCalculator:
    """類似度計算を行うクラス"""
    
    def __init__(self, db_handler: DatabaseHandler):
        """
        類似度計算器の初期化
        
        Args:
            db_handler: データベースハンドラ
        """
        self.db_handler = db_handler
    
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
        base_features = self._extract_features(base_data)
        
        # 候補データの取得
        candidates = self._get_candidate_data(base_data, base_features)
        
        # 類似度スコアを計算
        scored_candidates = []
        for candidate in candidates:
            if candidate['data_id'] != data_id:  # 自身を除外
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
    
    def _extract_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        データから特徴を抽出
        
        Args:
            data: データ辞書
        
        Returns:
            抽出された特徴
        """
        features = {
            'type': data.get('data_type'),
            'field': data.get('research_field'),
            'keywords': self._extract_keywords(data),
            'title_words': self._extract_title_words(data),
            'metadata_features': self._extract_metadata_features(data)
        }
        
        return features
    
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
            # 英語の単語を抽出
            english_words = re.findall(r'[a-zA-Z]{3,}', title.lower())
            keywords.extend(english_words)
            
            # 日本語の単語を抽出（簡易版）
            japanese_words = re.findall(r'[\u4e00-\u9faf\u3040-\u309f\u30a0-\u30ff]{2,}', title)
            keywords.extend(japanese_words)
        
        # 概要からも抽出
        summary = data.get('summary', '')
        if summary:
            english_words = re.findall(r'[a-zA-Z]{4,}', summary.lower())
            keywords.extend(english_words[:5])  # 最大5個
        
        return list(set(keywords))  # 重複を削除
    
    def _extract_title_words(self, data: Dict[str, Any]) -> List[str]:
        """
        タイトルから単語を抽出
        
        Args:
            data: データ辞書
        
        Returns:
            タイトルの単語リスト
        """
        title = data.get('title', '')
        if not title:
            return []
        
        # 単語分割（簡易版）
        words = []
        
        # 英語の単語
        english_words = re.findall(r'[a-zA-Z]+', title.lower())
        words.extend([w for w in english_words if len(w) > 2])
        
        # 日本語の単語（カタカナ、ひらがな、漢字）
        japanese_words = re.findall(r'[\u4e00-\u9faf\u3040-\u309f\u30a0-\u30ff]+', title)
        words.extend([w for w in japanese_words if len(w) > 1])
        
        return words
    
    def _extract_metadata_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        メタデータから特徴を抽出
        
        Args:
            data: データ辞書
        
        Returns:
            メタデータ特徴
        """
        metadata = data.get('metadata', {})
        if not isinstance(metadata, dict):
            return {}
        
        features = {}
        
        # ファイル関連の特徴
        if 'file_extension' in metadata:
            features['file_extension'] = metadata['file_extension']
        
        if 'file_size' in metadata:
            features['file_size_category'] = self._categorize_file_size(metadata['file_size'])
        
        # データセット特有の特徴
        if 'sample_count' in metadata:
            features['sample_count_category'] = self._categorize_sample_count(metadata['sample_count'])
        
        # その他の特徴
        if 'json_keys' in metadata:
            features['has_structured_data'] = True
        
        return features
    
    def _categorize_file_size(self, file_size: int) -> str:
        """
        ファイルサイズをカテゴリ化
        
        Args:
            file_size: ファイルサイズ（バイト）
        
        Returns:
            サイズカテゴリ
        """
        if file_size < 1024 * 1024:  # 1MB未満
            return 'small'
        elif file_size < 10 * 1024 * 1024:  # 10MB未満
            return 'medium'
        else:
            return 'large'
    
    def _categorize_sample_count(self, sample_count: int) -> str:
        """
        サンプル数をカテゴリ化
        
        Args:
            sample_count: サンプル数
        
        Returns:
            サンプル数カテゴリ
        """
        if sample_count < 100:
            return 'small'
        elif sample_count < 10000:
            return 'medium'
        else:
            return 'large'
    
    def _get_candidate_data(self, base_data: Dict[str, Any], 
                           base_features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        類似度計算の候補データを取得
        
        Args:
            base_data: 基準データ
            base_features: 基準データの特徴
        
        Returns:
            候補データのリスト
        """
        candidates = []
        
        # 同じタイプのデータを検索
        if base_features['type']:
            type_results = self.db_handler.search_data(
                data_type=base_features['type'],
                limit=50
            )
            candidates.extend(type_results)
        
        # 同じ研究分野のデータを検索
        if base_features['field']:
            field_results = self.db_handler.search_data(
                research_field=base_features['field'],
                limit=50
            )
            candidates.extend(field_results)
        
        # キーワードベースの検索
        if base_features['keywords']:
            for keyword in base_features['keywords'][:3]:  # 最初の3個のキーワード
                keyword_results = self.db_handler.search_data(
                    keyword=keyword,
                    limit=20
                )
                candidates.extend(keyword_results)
        
        # 重複を除去
        seen = set()
        unique_candidates = []
        for candidate in candidates:
            if candidate['data_id'] not in seen:
                seen.add(candidate['data_id'])
                unique_candidates.append(candidate)
        
        return unique_candidates
    
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
        
        # データタイプの一致（重要度高）
        if base_features['type'] == candidate.get('data_type'):
            score += 0.3
        
        # 研究分野の一致（重要度高）
        if base_features['field'] == candidate.get('research_field'):
            score += 0.3
        
        # キーワードの重複
        candidate_keywords = self._extract_keywords(candidate)
        if base_features['keywords'] and candidate_keywords:
            common_keywords = set(base_features['keywords']) & set(candidate_keywords)
            if len(base_features['keywords']) > 0:
                keyword_score = len(common_keywords) / len(base_features['keywords'])
                score += 0.25 * keyword_score
        
        # タイトルの単語の重複
        candidate_title_words = self._extract_title_words(candidate)
        if base_features.get('title_words') and candidate_title_words:
            common_title_words = set(base_features['title_words']) & set(candidate_title_words)
            if len(base_features['title_words']) > 0:
                title_score = len(common_title_words) / len(base_features['title_words'])
                score += 0.15 * title_score
        
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
        recent_data = self.db_handler.search_data(limit=200)
        
        # 日付でフィルタリング
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_data = []
        
        for data in recent_data:
            updated_at = data.get('updated_at')
            if updated_at:
                try:
                    update_time = datetime.fromisoformat(updated_at)
                    if update_time > cutoff_date:
                        filtered_data.append(data)
                except:
                    pass
        
        # 研究分野の集計
        field_counts = defaultdict(int)
        field_latest = defaultdict(str)
        
        for data in filtered_data:
            field = data.get('research_field', '未分類')
            if field and field != '未分類':
                field_counts[field] += 1
                # 最新の更新日時を記録
                updated_at = data.get('updated_at', '')
                if updated_at > field_latest[field]:
                    field_latest[field] = updated_at
        
        # トレンドスコアの計算
        trending = []
        for field, count in field_counts.items():
            if count >= 2:  # 最低2件以上
                # トレンドスコア = 件数 × 最新性ボーナス
                latest_update = field_latest[field]
                recency_bonus = self._calculate_recency_score(latest_update, days)
                trend_score = count * (1 + recency_bonus)
                
                trending.append({
                    'topic': field,
                    'count': count,
                    'latest_update': latest_update,
                    'trend_score': trend_score,
                    'days_analyzed': days
                })
        
        # スコアでソート
        trending.sort(key=lambda x: x['trend_score'], reverse=True)
        
        return trending[:10]  # 上位10件
    
    def _calculate_recency_score(self, updated_at: str, days_window: int) -> float:
        """
        最新性スコアを計算
        
        Args:
            updated_at: 更新日時
            days_window: 分析対象日数
        
        Returns:
            最新性スコア（0-1）
        """
        try:
            update_time = datetime.fromisoformat(updated_at)
            hours_ago = (datetime.now() - update_time).total_seconds() / 3600
            window_hours = days_window * 24
            
            # 最新ほど高いスコア
            return max(0, 1 - (hours_ago / window_hours))
        except:
            return 0.0