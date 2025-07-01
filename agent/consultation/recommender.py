"""
データ推薦エンジン
ユーザーの研究ニーズに基づいてデータを推薦
"""
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None
from ..database_handler import DatabaseHandler
from ..search.search_engine import SearchEngine


class DataRecommender:
    """研究データを推薦するエンジン"""
    
    def __init__(self, db_handler: Optional[DatabaseHandler] = None):
        """
        推薦エンジンの初期化
        
        Args:
            db_handler: データベースハンドラ
        """
        self.db_handler = db_handler or DatabaseHandler()
        self.search_engine = SearchEngine(self.db_handler)
    
    def recommend_by_type(self, data_type: str, 
                         exclude_ids: Optional[List[str]] = None,
                         limit: int = 10) -> List[Dict[str, Any]]:
        """
        データタイプに基づく推薦
        
        Args:
            data_type: データタイプ（dataset, paper, poster）
            exclude_ids: 除外するデータID
            limit: 推薦数
        
        Returns:
            推薦データのリスト
        """
        exclude_ids = exclude_ids or []
        
        # 指定タイプのデータを検索
        results = self.db_handler.search_data(
            data_type=data_type,
            limit=limit * 2  # 除外分を考慮して多めに取得
        )
        
        # 除外IDをフィルタリング
        recommendations = []
        for data in results:
            if data['data_id'] not in exclude_ids:
                recommendations.append({
                    **data,
                    'recommendation_type': 'type_based',
                    'recommendation_reason': f'{data_type}タイプの人気データ'
                })
                
                if len(recommendations) >= limit:
                    break
        
        return recommendations
    
    def recommend_by_field(self, research_field: str,
                          exclude_ids: Optional[List[str]] = None,
                          limit: int = 10) -> List[Dict[str, Any]]:
        """
        研究分野に基づく推薦
        
        Args:
            research_field: 研究分野
            exclude_ids: 除外するデータID
            limit: 推薦数
        
        Returns:
            推薦データのリスト
        """
        exclude_ids = exclude_ids or []
        
        # 指定分野のデータを検索
        results = self.db_handler.search_data(
            research_field=research_field,
            limit=limit * 2
        )
        
        # 除外IDをフィルタリング
        recommendations = []
        for data in results:
            if data['data_id'] not in exclude_ids:
                recommendations.append({
                    **data,
                    'recommendation_type': 'field_based',
                    'recommendation_reason': f'{research_field}分野の関連データ'
                })
                
                if len(recommendations) >= limit:
                    break
        
        return recommendations
    
    def recommend_similar(self, data_id: str,
                         limit: int = 5) -> List[Dict[str, Any]]:
        """
        類似データの推薦
        
        Args:
            data_id: 基準となるデータID
            limit: 推薦数
        
        Returns:
            類似データのリスト
        """
        # 検索エンジンの類似検索を利用
        similar_data = self.search_engine.get_similar_data(data_id, limit)
        
        # 推薦情報を追加
        recommendations = []
        for data in similar_data:
            recommendations.append({
                **data,
                'recommendation_type': 'similarity_based',
                'recommendation_reason': '内容が類似しているデータ',
                'similarity_score': data.get('_similarity_score', 0)
            })
        
        return recommendations
    
    def recommend_trending(self, days: int = 7,
                          exclude_ids: Optional[List[str]] = None,
                          limit: int = 10) -> List[Dict[str, Any]]:
        """
        トレンドに基づく推薦
        
        Args:
            days: 過去何日間のトレンドを見るか
            exclude_ids: 除外するデータID
            limit: 推薦数
        
        Returns:
            トレンドデータのリスト
        """
        exclude_ids = exclude_ids or []
        
        # トレンディングトピックを取得
        trending_topics = self.search_engine.get_trending_topics(days)
        
        recommendations = []
        
        # 各トレンドトピックから最新データを取得
        for topic in trending_topics[:3]:  # 上位3トピック
            topic_data = self.db_handler.search_data(
                research_field=topic['topic'],
                limit=5
            )
            
            for data in topic_data:
                if data['data_id'] not in exclude_ids and len(recommendations) < limit:
                    recommendations.append({
                        **data,
                        'recommendation_type': 'trending',
                        'recommendation_reason': f'「{topic["topic"]}」分野で注目されているデータ',
                        'trend_score': topic['trend_score']
                    })
        
        return recommendations[:limit]
    
    def recommend_collaborative(self, user_history: List[str],
                              limit: int = 10) -> List[Dict[str, Any]]:
        """
        協調フィルタリング的な推薦（簡易版）
        
        Args:
            user_history: ユーザーが過去に閲覧したデータID
            limit: 推薦数
        
        Returns:
            推薦データのリスト
        """
        if not user_history:
            return []
        
        # ユーザーの興味を分析
        user_interests = self._analyze_user_interests(user_history)
        
        # 興味に基づいて推薦
        recommendations = []
        seen_ids = set(user_history)
        
        # 最も興味のある分野から推薦
        for field, score in user_interests['fields'].items():
            if len(recommendations) >= limit:
                break
                
            field_data = self.db_handler.search_data(
                research_field=field,
                limit=10
            )
            
            for data in field_data:
                if data['data_id'] not in seen_ids:
                    recommendations.append({
                        **data,
                        'recommendation_type': 'collaborative',
                        'recommendation_reason': f'過去の閲覧履歴から「{field}」分野に興味があると推定',
                        'interest_score': score
                    })
                    seen_ids.add(data['data_id'])
                    
                    if len(recommendations) >= limit:
                        break
        
        return recommendations
    
    def _analyze_user_interests(self, user_history: List[str]) -> Dict[str, Any]:
        """
        ユーザーの興味を分析
        
        Args:
            user_history: 閲覧履歴
        
        Returns:
            興味の分析結果
        """
        interests = {
            'fields': defaultdict(float),
            'types': defaultdict(float),
            'keywords': defaultdict(float)
        }
        
        # 履歴データを取得
        for data_id in user_history:
            data = self.db_handler.get_data_by_id(data_id)
            if data:
                # 研究分野
                if data.get('research_field'):
                    interests['fields'][data['research_field']] += 1.0
                
                # データタイプ
                if data.get('data_type'):
                    interests['types'][data['data_type']] += 1.0
                
                # キーワード（タイトルから簡易抽出）
                if data.get('title'):
                    words = data['title'].split()
                    for word in words:
                        if len(word) > 3:  # 短い単語は除外
                            interests['keywords'][word.lower()] += 0.5
        
        # 正規化
        for category in interests.values():
            if category:
                max_score = max(category.values())
                for key in category:
                    category[key] = category[key] / max_score
        
        return interests
    
    def get_personalized_recommendations(self, user_profile: Dict[str, Any],
                                       limit: int = 20) -> List[Dict[str, Any]]:
        """
        パーソナライズされた推薦を生成
        
        Args:
            user_profile: ユーザープロフィール
                - history: 閲覧履歴
                - preferences: 好みの設定
                - current_research: 現在の研究テーマ
            limit: 推薦数
        
        Returns:
            パーソナライズされた推薦リスト
        """
        all_recommendations = []
        seen_ids = set()
        
        # 履歴がある場合は協調フィルタリング
        if user_profile.get('history'):
            collab_recs = self.recommend_collaborative(
                user_profile['history'], 
                limit=limit // 2
            )
            all_recommendations.extend(collab_recs)
            seen_ids.update([r['data_id'] for r in collab_recs])
        
        # 好みの分野がある場合
        if user_profile.get('preferences', {}).get('research_field'):
            field_recs = self.recommend_by_field(
                user_profile['preferences']['research_field'],
                exclude_ids=list(seen_ids),
                limit=limit // 3
            )
            all_recommendations.extend(field_recs)
            seen_ids.update([r['data_id'] for r in field_recs])
        
        # 好みのデータタイプがある場合
        if user_profile.get('preferences', {}).get('data_type'):
            type_recs = self.recommend_by_type(
                user_profile['preferences']['data_type'],
                exclude_ids=list(seen_ids),
                limit=limit // 3
            )
            all_recommendations.extend(type_recs)
            seen_ids.update([r['data_id'] for r in type_recs])
        
        # トレンドデータを追加
        trend_recs = self.recommend_trending(
            days=7,
            exclude_ids=list(seen_ids),
            limit=limit // 4
        )
        all_recommendations.extend(trend_recs)
        
        # スコアリングして上位を選択
        scored_recommendations = self._score_recommendations(
            all_recommendations, 
            user_profile
        )
        
        return scored_recommendations[:limit]
    
    def _score_recommendations(self, recommendations: List[Dict[str, Any]],
                             user_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        推薦にスコアを付けてソート
        
        Args:
            recommendations: 推薦リスト
            user_profile: ユーザープロフィール
        
        Returns:
            スコア付き推薦リスト
        """
        for rec in recommendations:
            score = 0.0
            
            # 推薦タイプによる基本スコア
            type_scores = {
                'collaborative': 1.0,
                'similarity_based': 0.9,
                'field_based': 0.8,
                'type_based': 0.7,
                'trending': 0.6
            }
            score += type_scores.get(rec.get('recommendation_type', ''), 0.5)
            
            # 現在の研究テーマとの関連性
            if user_profile.get('current_research'):
                current_keywords = user_profile['current_research'].lower().split()
                title = rec.get('title', '').lower()
                summary = rec.get('summary', '').lower()
                
                for keyword in current_keywords:
                    if keyword in title:
                        score += 0.3
                    elif keyword in summary:
                        score += 0.1
            
            # 既存のスコアがある場合は考慮
            if 'interest_score' in rec:
                score += rec['interest_score'] * 0.5
            if 'similarity_score' in rec:
                score += rec['similarity_score'] * 0.5
            if 'trend_score' in rec:
                score += min(rec['trend_score'] / 10, 0.5)
            
            rec['final_score'] = score
        
        # スコアでソート
        recommendations.sort(key=lambda x: x['final_score'], reverse=True)
        
        return recommendations
    
    def explain_recommendation(self, recommendation: Dict[str, Any]) -> str:
        """
        推薦理由を説明する文章を生成
        
        Args:
            recommendation: 推薦データ
        
        Returns:
            説明文
        """
        base_reason = recommendation.get('recommendation_reason', '')
        
        explanations = [base_reason]
        
        # スコア情報を追加
        if recommendation.get('similarity_score', 0) > 0.7:
            explanations.append("内容の類似度が非常に高いです。")
        
        if recommendation.get('trend_score', 0) > 5:
            explanations.append("最近注目を集めているトピックです。")
        
        if recommendation.get('interest_score', 0) > 0.8:
            explanations.append("あなたの興味に強く合致しています。")
        
        # データの特徴を追加
        if recommendation.get('metadata', {}).get('sample_count', 0) > 1000:
            explanations.append("大規模なデータセットです。")
        
        return ' '.join(explanations)