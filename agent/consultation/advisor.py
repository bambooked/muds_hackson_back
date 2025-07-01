"""
研究相談AIアドバイザー
ユーザーの研究相談に対応し、適切なデータやアドバイスを提供
"""
import re
from typing import Dict, Any, List, Optional, Tuple
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
from ..search.search_engine import SearchEngine
from ..database_handler import DatabaseHandler
from ..config import Config


class ResearchAdvisor:
    """研究相談を行うAIアドバイザー"""
    
    def __init__(self, db_handler: Optional[DatabaseHandler] = None,
                config: Optional[Config] = None):
        """
        アドバイザーの初期化
        
        Args:
            db_handler: データベースハンドラ
            config: 設定オブジェクト
        """
        self.db_handler = db_handler or DatabaseHandler()
        self.search_engine = SearchEngine(self.db_handler)
        self.config = config or Config()
        self._init_gemini()
    
    def _init_gemini(self):
        """Gemini APIの初期化"""
        if GEMINI_AVAILABLE and self.config.gemini_api_key:
            genai.configure(api_key=self.config.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None
    
    def consult(self, user_query: str, 
               consultation_type: str = 'general') -> Dict[str, Any]:
        """
        研究相談に応答
        
        Args:
            user_query: ユーザーの質問
            consultation_type: 相談タイプ（general, dataset, idea）
        
        Returns:
            相談結果
        """
        # 相談内容の解析
        analysis = self._analyze_query(user_query, consultation_type)
        
        # 関連データの検索
        related_data = self._search_related_data(analysis)
        
        # アドバイスの生成
        advice = self._generate_advice(user_query, analysis, related_data)
        
        # 推薦データの選定
        recommendations = self._select_recommendations(related_data, analysis)
        
        return {
            'query': user_query,
            'consultation_type': consultation_type,
            'analysis': analysis,
            'advice': advice,
            'recommendations': recommendations,
            'related_data_count': len(related_data)
        }
    
    def _analyze_query(self, query: str, 
                      consultation_type: str) -> Dict[str, Any]:
        """
        ユーザーの質問を解析
        
        Args:
            query: ユーザーの質問
            consultation_type: 相談タイプ
        
        Returns:
            解析結果
        """
        analysis = {
            'keywords': [],
            'research_field': None,
            'data_type_preference': None,
            'intent': consultation_type
        }
        
        # キーワード抽出（簡易版）
        # 日本語と英語の重要そうな単語を抽出
        keywords = re.findall(r'[a-zA-Z]{3,}|[\u4e00-\u9faf\u3040-\u309f\u30a0-\u30ff]{2,}', query)
        analysis['keywords'] = keywords
        
        # データタイプの推定
        if 'データセット' in query or 'dataset' in query.lower():
            analysis['data_type_preference'] = 'dataset'
        elif '論文' in query or 'paper' in query.lower():
            analysis['data_type_preference'] = 'paper'
        elif 'ポスター' in query or 'poster' in query.lower():
            analysis['data_type_preference'] = 'poster'
        
        # 研究分野の推定
        field_keywords = {
            '機械学習': ['機械学習', '深層学習', 'ML', 'ディープラーニング'],
            '自然言語処理': ['自然言語', 'NLP', 'テキスト', '言語処理'],
            'コンピュータビジョン': ['画像', 'ビジョン', 'CV', '画像認識'],
            'データサイエンス': ['データ分析', 'データサイエンス', '統計'],
            '医療AI': ['医療', '診断', 'ヘルスケア', '病気']
        }
        
        for field, keywords_list in field_keywords.items():
            for keyword in keywords_list:
                if keyword.lower() in query.lower():
                    analysis['research_field'] = field
                    break
        
        # Gemini APIによる高度な解析（利用可能な場合）
        if self.model and self.config.use_gemini_for_analysis:
            try:
                gemini_analysis = self._analyze_with_gemini(query, consultation_type)
                analysis.update(gemini_analysis)
            except:
                pass
        
        return analysis
    
    def _analyze_with_gemini(self, query: str, 
                           consultation_type: str) -> Dict[str, Any]:
        """
        Gemini APIを使用した高度な解析
        
        Args:
            query: ユーザーの質問
            consultation_type: 相談タイプ
        
        Returns:
            Gemini解析結果
        """
        prompt = f"""
        以下の研究相談を分析してください：
        
        相談タイプ: {consultation_type}
        質問: {query}
        
        以下の情報を抽出してください：
        1. 主要なキーワード（最大5個）
        2. 推定される研究分野
        3. 求められているデータの種類
        4. ユーザーの研究段階（初期調査、実装、評価など）
        
        JSON形式で回答してください。
        """
        
        try:
            response = self.model.generate_content(prompt)
            # レスポンスからJSON部分を抽出（簡易実装）
            # 実際にはより堅牢な解析が必要
            return {}
        except:
            return {}
    
    def _search_related_data(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        解析結果に基づいて関連データを検索
        
        Args:
            analysis: 解析結果
        
        Returns:
            関連データのリスト
        """
        # 検索クエリの構築
        search_query = ' '.join(analysis['keywords'][:3])
        
        # フィルターの設定
        filters = {}
        if analysis['data_type_preference']:
            filters['data_type'] = analysis['data_type_preference']
        if analysis['research_field']:
            filters['research_field'] = analysis['research_field']
        
        # 検索実行
        search_result = self.search_engine.search(
            query=search_query,
            filters=filters,
            limit=20
        )
        
        return search_result['results']
    
    def _generate_advice(self, user_query: str, 
                        analysis: Dict[str, Any],
                        related_data: List[Dict[str, Any]]) -> str:
        """
        アドバイスを生成
        
        Args:
            user_query: ユーザーの質問
            analysis: 解析結果
            related_data: 関連データ
        
        Returns:
            アドバイス文
        """
        # 基本的なアドバイステンプレート
        advice_parts = []
        
        # 相談タイプに応じた導入
        if analysis['intent'] == 'dataset':
            advice_parts.append("データセットをお探しですね。")
        elif analysis['intent'] == 'idea':
            advice_parts.append("研究アイデアをお探しですね。")
        else:
            advice_parts.append("研究に関するご相談ですね。")
        
        # 検索結果に基づくアドバイス
        if related_data:
            advice_parts.append(f"\n\n関連する{len(related_data)}件のデータが見つかりました。")
            
            # データタイプ別の集計
            type_counts = {}
            for data in related_data:
                data_type = data.get('data_type', 'unknown')
                type_counts[data_type] = type_counts.get(data_type, 0) + 1
            
            if type_counts:
                type_summary = "、".join([f"{t}: {c}件" for t, c in type_counts.items()])
                advice_parts.append(f"内訳は{type_summary}です。")
        else:
            advice_parts.append("\n\n申し訳ございません。関連するデータが見つかりませんでした。")
            advice_parts.append("検索条件を変更してお試しください。")
        
        # 研究分野に応じた追加アドバイス
        if analysis['research_field']:
            advice_parts.append(f"\n\n{analysis['research_field']}分野での研究をお考えのようですね。")
            
            # 分野別の一般的なアドバイス
            field_advice = {
                '機械学習': "最新のモデルアーキテクチャやベンチマークデータセットを確認することをお勧めします。",
                '自然言語処理': "タスクに適したコーパスやプレトレーニング済みモデルの活用を検討してください。",
                'コンピュータビジョン': "画像の品質やアノテーションの精度が重要になります。",
                'データサイエンス': "データの前処理と特徴量エンジニアリングに十分な時間をかけることが重要です。",
                '医療AI': "倫理的配慮とプライバシー保護に特に注意が必要です。"
            }
            
            if analysis['research_field'] in field_advice:
                advice_parts.append(field_advice[analysis['research_field']])
        
        # 次のステップの提案
        advice_parts.append("\n\n次のステップとして以下をご提案します：")
        advice_parts.append("1. 推薦されたデータの詳細を確認する")
        advice_parts.append("2. 類似研究の論文を調査する")
        advice_parts.append("3. 必要に応じて追加のデータを収集する")
        
        return '\n'.join(advice_parts)
    
    def _select_recommendations(self, related_data: List[Dict[str, Any]], 
                              analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        推薦データを選定
        
        Args:
            related_data: 関連データ
            analysis: 解析結果
        
        Returns:
            推薦データのリスト（最大5件）
        """
        # スコアリング
        scored_data = []
        
        for data in related_data:
            score = 0
            
            # データタイプの一致
            if analysis['data_type_preference'] and \
               data.get('data_type') == analysis['data_type_preference']:
                score += 10
            
            # 研究分野の一致
            if analysis['research_field'] and \
               data.get('research_field') == analysis['research_field']:
                score += 8
            
            # キーワードの一致
            title = (data.get('title') or '').lower()
            summary = (data.get('summary') or '').lower()
            
            for keyword in analysis['keywords']:
                if keyword.lower() in title:
                    score += 5
                elif keyword.lower() in summary:
                    score += 2
            
            # 検索スコアがある場合は考慮
            if '_score' in data:
                score += data['_score'] * 0.5
            
            data['_recommendation_score'] = score
            scored_data.append(data)
        
        # スコアでソートして上位を選択
        scored_data.sort(key=lambda x: x['_recommendation_score'], reverse=True)
        
        # 推薦理由を追加
        recommendations = []
        for data in scored_data[:5]:
            recommendation = {
                'data_id': data['data_id'],
                'title': data.get('title', ''),
                'data_type': data.get('data_type', ''),
                'research_field': data.get('research_field', ''),
                'summary': data.get('summary', '')[:200] + '...' if len(data.get('summary', '')) > 200 else data.get('summary', ''),
                'score': data['_recommendation_score'],
                'reason': self._generate_recommendation_reason(data, analysis)
            }
            recommendations.append(recommendation)
        
        return recommendations
    
    def _generate_recommendation_reason(self, data: Dict[str, Any], 
                                      analysis: Dict[str, Any]) -> str:
        """
        推薦理由を生成
        
        Args:
            data: データ情報
            analysis: 解析結果
        
        Returns:
            推薦理由
        """
        reasons = []
        
        if analysis['data_type_preference'] and \
           data.get('data_type') == analysis['data_type_preference']:
            reasons.append(f"ご希望の{analysis['data_type_preference']}タイプです")
        
        if analysis['research_field'] and \
           data.get('research_field') == analysis['research_field']:
            reasons.append(f"{analysis['research_field']}分野のデータです")
        
        # キーワードマッチ
        matched_keywords = []
        title = (data.get('title') or '').lower()
        summary = (data.get('summary') or '').lower()
        
        for keyword in analysis['keywords'][:3]:
            if keyword.lower() in title or keyword.lower() in summary:
                matched_keywords.append(keyword)
        
        if matched_keywords:
            reasons.append(f"キーワード「{'、'.join(matched_keywords)}」を含んでいます")
        
        if not reasons:
            reasons.append("関連性の高いデータです")
        
        return '。'.join(reasons)
    
    def get_consultation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        相談履歴を取得（検索履歴を活用）
        
        Args:
            limit: 取得件数
        
        Returns:
            相談履歴
        """
        # 検索履歴を相談履歴として活用
        search_history = self.db_handler.get_search_history(limit)
        
        consultation_history = []
        for history in search_history:
            consultation_history.append({
                'query': history['query'],
                'timestamp': history['timestamp'],
                'type': 'search'  # 実際の実装では相談タイプも記録する
            })
        
        return consultation_history