"""
LLMベースの研究相談アドバイザー
全ての応答をLLMが生成し、データベース検索も組み込む
"""
import json
import re
from typing import Dict, Any, List, Optional

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

from ..search.search_engine import SearchEngine
from ..database_handler import DatabaseHandler
from ..data_management.dataset_manager import DatasetManager
from ..config import Config


class LLMAdvisor:
    """LLMベースの研究相談アドバイザー"""
    
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
        self.dataset_manager = DatasetManager(self.db_handler, config)
        self.config = config or Config()
        self._init_gemini()
    
    def _init_gemini(self):
        """Gemini APIの初期化"""
        if GEMINI_AVAILABLE and self.config.gemini_api_key:
            genai.configure(api_key=self.config.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-1.5-pro')
            self.available = True
        else:
            self.model = None
            self.available = False
    
    def consult(self, user_query: str, 
                consultation_type: str = 'general') -> Dict[str, Any]:
        """
        研究相談に応答（シンプル版）
        
        Args:
            user_query: ユーザーの質問
            consultation_type: 相談タイプ
        
        Returns:
            相談結果
        """
        if not self.available:
            response = self._fallback_response(user_query, consultation_type)
        else:
            try:
                # データベース情報の収集
                database_context = self._gather_database_context(user_query)
                
                # LLMによる包括的な相談対応
                response = self._generate_comprehensive_response(
                    user_query, consultation_type, database_context
                )
                
            except Exception as e:
                print(f"LLM相談エラー: {e}")
                response = self._fallback_response(user_query, consultation_type)
        
        return response
    
    def _gather_database_context(self, user_query: str) -> Dict[str, Any]:
        """
        データベースから関連情報を収集
        
        Args:
            user_query: ユーザーの質問
        
        Returns:
            データベースコンテキスト
        """
        context = {
            'file_data': [],
            'datasets': [],
            'statistics': {},
            'available_fields': [],
            'available_tags': []
        }
        
        try:
            # ファイルデータの検索
            file_search_results = self.search_engine.search(user_query, limit=10)
            context['file_data'] = file_search_results.get('results', [])
            
            # データセットの検索
            dataset_results = self.dataset_manager.search_datasets(user_query, limit=5)
            context['datasets'] = dataset_results
            
            # システム統計の取得
            from ..data_management.data_manager import DataManager
            data_manager = DataManager(self.db_handler)
            context['statistics'] = data_manager.get_statistics()
            
            # 利用可能なタグの取得
            context['available_tags'] = self.dataset_manager.get_all_tags()[:20]
            
            # 研究分野の一覧
            if context['statistics'].get('field_counts'):
                context['available_fields'] = list(context['statistics']['field_counts'].keys())[:10]
            
        except Exception as e:
            print(f"データベースコンテキスト収集エラー: {e}")
        
        return context
    
    def _generate_comprehensive_response(self, user_query: str, 
                                       consultation_type: str,
                                       database_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLMによる包括的な応答生成
        
        Args:
            user_query: ユーザーの質問
            consultation_type: 相談タイプ
            database_context: データベースコンテキスト
            conversation_context: 会話コンテキスト
        
        Returns:
            生成された応答
        """
        # プロンプトの構築
        prompt = self._build_consultation_prompt(user_query, consultation_type, database_context)
        
        # Gemini APIの呼び出し
        response = self.model.generate_content(prompt)
        
        # レスポンスの解析
        return self._parse_llm_response(response.text, user_query, consultation_type)
    
    def _build_consultation_prompt(self, user_query: str, 
                                 consultation_type: str,
                                 database_context: Dict[str, Any]) -> str:
        """
        相談用のプロンプトを構築
        
        Args:
            user_query: ユーザーの質問
            consultation_type: 相談タイプ
            database_context: データベースコンテキスト
            conversation_context: 会話コンテキスト
        
        Returns:
            プロンプト文字列
        """
        # データベース情報の要約
        db_summary = self._summarize_database_context(database_context)
        
        consultation_type_map = {
            'general': '一般的な研究相談',
            'dataset': 'データセット相談',
            'idea': '研究アイデア相談'
        }
        
        consultation_desc = consultation_type_map.get(consultation_type, '一般的な研究相談')
        
        prompt = f"""
あなたは研究データ基盤システムの専門AIアドバイザーです。
ユーザーの研究相談に対して、データベース内の情報を活用して包括的で有用な回答を提供してください。
## ユーザーの質問
相談タイプ: {consultation_desc}
質問内容: {user_query}

## 利用可能なデータベース情報
{db_summary}

## 回答形式
以下のJSON形式で回答してください：

{{
  "advice": "ユーザーへの詳細で実用的なアドバイス（300-500文字）",
  "response_type": "helpful/no_data_found/need_more_info/general_guidance",
  "search_suggestions": ["検索で試すべきキーワード1", "検索で試すべきキーワード2", "検索で試すべきキーワード3"],
  "recommended_data": [
    {{
      "title": "推薦データ/データセット名",
      "type": "dataset/paper/poster",
      "data_id": "実際のIDまたはnull",
      "reason": "推薦理由",
      "relevance_score": 0.8
    }}
  ],
  "alternative_approaches": ["代替アプローチ1", "代替アプローチ2"],
  "research_direction": "研究方向性のアドバイス",
  "next_steps": ["次に取るべき具体的なステップ1", "次に取るべき具体的なステップ2"],
  "related_fields": ["関連する研究分野1", "関連する研究分野2"],
  "useful_tags": ["検索に有用なタグ1", "検索に有用なタグ2"]
}}

## 重要な指針
1. **会話の継続性**: 過去の会話内容を参照し、一貫した対話を維持する
2. **データが見つからない場合でも**、建設的で有用なアドバイスを提供する
3. **具体的な検索キーワード**や**代替アプローチ**を提案する
4. **利用可能なデータ**から最も関連性の高いものを推薦する
5. **研究の方向性**や**次のステップ**を明確に示す
6. **親しみやすく専門的**な口調で回答する
7. **データベースにないデータ**についても、一般的な研究アドバイスを提供する
8. **フォローアップ質問**を促し、継続的な相談を支援する

データベースに直接的な関連データがない場合は、research_direction や alternative_approaches を充実させ、
ユーザーが研究を進められるよう建設的なガイダンスを提供してください。
過去の会話で言及された内容があれば、それに言及して継続性を保ってください。
"""
        
        return prompt
    
    def _summarize_database_context(self, context: Dict[str, Any]) -> str:
        """
        データベースコンテキストを要約
        
        Args:
            context: データベースコンテキスト
        
        Returns:
            要約されたコンテキスト文字列
        """
        summary_parts = []
        
        # システム統計
        stats = context.get('statistics', {})
        if stats:
            summary_parts.append(f"総データ数: {stats.get('total_count', 0)}件")
            
            if stats.get('type_counts'):
                type_info = ", ".join([f"{k}: {v}件" for k, v in stats['type_counts'].items()])
                summary_parts.append(f"データタイプ別: {type_info}")
            
            if stats.get('field_counts'):
                field_info = ", ".join(list(stats['field_counts'].keys())[:5])
                summary_parts.append(f"主要研究分野: {field_info}")
        
        # 検索結果
        file_data = context.get('file_data', [])
        if file_data:
            summary_parts.append(f"関連ファイルデータ: {len(file_data)}件見つかりました")
            
            # 上位3件の詳細
            top_files = []
            for i, data in enumerate(file_data[:3], 1):
                title = data.get('title', '無題')
                data_type = data.get('data_type', '不明')
                field = data.get('research_field', '未分類')
                summary = data.get('summary', '')[:50] + '...' if data.get('summary') else '概要なし'
                top_files.append(f"{i}. {title} ({data_type}, {field}) - {summary}")
            
            if top_files:
                summary_parts.append("主要な関連ファイル:")
                summary_parts.extend(top_files)
        
        # データセット
        datasets = context.get('datasets', [])
        if datasets:
            summary_parts.append(f"関連データセット: {len(datasets)}件見つかりました")
            
            # 上位2件の詳細
            top_datasets = []
            for i, dataset in enumerate(datasets[:2], 1):
                name = dataset.get('name', '無名')
                field = dataset.get('research_field', '不明')
                desc = dataset.get('description', '')[:50] + '...' if dataset.get('description') else '説明なし'
                file_count = dataset.get('file_count', 0)
                top_datasets.append(f"{i}. {name} ({field}, {file_count}ファイル) - {desc}")
            
            if top_datasets:
                summary_parts.append("主要なデータセット:")
                summary_parts.extend(top_datasets)
        
        # 利用可能なタグ
        tags = context.get('available_tags', [])
        if tags:
            summary_parts.append(f"利用可能なタグ: {', '.join(tags[:10])}")
        
        # データが見つからない場合
        if not file_data and not datasets:
            summary_parts.append("直接的に関連するデータは見つかりませんでしたが、以下の情報を参考にアドバイスを提供します。")
        
        return "\n".join(summary_parts)
    
    def _parse_llm_response(self, response_text: str, 
                           user_query: str,
                           consultation_type: str) -> Dict[str, Any]:
        """
        LLMレスポンスを解析
        
        Args:
            response_text: LLMからのレスポンス
            user_query: 元のユーザークエリ
            consultation_type: 相談タイプ
        
        Returns:
            解析された応答
        """
        try:
            # JSONの抽出と解析
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                llm_response = json.loads(json_match.group())
                
                # 推薦データの実際のIDを検証・補完
                if llm_response.get('recommended_data'):
                    llm_response['recommended_data'] = self._validate_recommendations(
                        llm_response['recommended_data']
                    )
                
                # 標準形式に変換
                return {
                    'query': user_query,
                    'consultation_type': consultation_type,
                    'advice': llm_response.get('advice', 'アドバイスの生成に失敗しました'),
                    'response_type': llm_response.get('response_type', 'general_guidance'),
                    'recommendations': llm_response.get('recommended_data', []),
                    'search_suggestions': llm_response.get('search_suggestions', []),
                    'alternative_approaches': llm_response.get('alternative_approaches', []),
                    'research_direction': llm_response.get('research_direction', ''),
                    'next_steps': llm_response.get('next_steps', []),
                    'related_fields': llm_response.get('related_fields', []),
                    'useful_tags': llm_response.get('useful_tags', []),
                    'llm_generated': True
                }
            else:
                # JSONが見つからない場合はテキストから情報を抽出
                return self._extract_from_text(response_text, user_query, consultation_type)
                
        except Exception as e:
            print(f"LLMレスポンス解析エラー: {e}")
            return self._fallback_response(user_query, consultation_type)
    
    def _validate_recommendations(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        推薦データのIDを実際のデータベースと照合・補完
        
        Args:
            recommendations: LLMが生成した推薦リスト
        
        Returns:
            検証・補完された推薦リスト
        """
        validated = []
        
        for rec in recommendations:
            title = rec.get('title', '')
            data_type = rec.get('type', '')
            
            # タイトルでデータベース検索
            if title:
                # ファイルデータから検索
                search_results = self.search_engine.search(title, limit=3)
                for result in search_results.get('results', []):
                    if self._is_similar_title(title, result.get('title', '')):
                        rec['data_id'] = result.get('data_id')
                        rec['actual_title'] = result.get('title')
                        rec['file_path'] = result.get('file_path')
                        break
                
                # データセットから検索
                if not rec.get('data_id'):
                    dataset_results = self.dataset_manager.search_datasets(title, limit=3)
                    for dataset in dataset_results:
                        if self._is_similar_title(title, dataset.get('name', '')):
                            rec['dataset_id'] = dataset.get('dataset_id')
                            rec['actual_title'] = dataset.get('name')
                            rec['type'] = 'dataset'
                            break
            
            validated.append(rec)
        
        return validated
    
    def _is_similar_title(self, title1: str, title2: str) -> bool:
        """
        タイトルの類似性を判定
        
        Args:
            title1: タイトル1
            title2: タイトル2
        
        Returns:
            類似している場合True
        """
        # 簡易類似性判定
        title1_clean = re.sub(r'[^\w\s]', '', title1.lower())
        title2_clean = re.sub(r'[^\w\s]', '', title2.lower())
        
        # 部分一致または包含関係をチェック
        return (title1_clean in title2_clean or 
                title2_clean in title1_clean or
                len(set(title1_clean.split()) & set(title2_clean.split())) >= 2)
    
    def _extract_from_text(self, text: str, user_query: str, consultation_type: str) -> Dict[str, Any]:
        """
        テキストから情報を抽出（JSONが見つからない場合）
        
        Args:
            text: レスポンステキスト
            user_query: ユーザークエリ
            consultation_type: 相談タイプ
        
        Returns:
            抽出された情報
        """
        return {
            'query': user_query,
            'consultation_type': consultation_type,
            'advice': text[:500] + '...' if len(text) > 500 else text,
            'response_type': 'general_guidance',
            'recommendations': [],
            'search_suggestions': [],
            'alternative_approaches': [],
            'research_direction': '',
            'next_steps': [],
            'related_fields': [],
            'useful_tags': [],
            'llm_generated': True,
            'raw_response': text
        }
    
    def _fallback_response(self, user_query: str, consultation_type: str) -> Dict[str, Any]:
        """
        LLMが利用できない場合のフォールバック応答（データベース検索機能付き）
        
        Args:
            user_query: ユーザークエリ
            consultation_type: 相談タイプ
            session: チャットセッション
        
        Returns:
            フォールバック応答
        """
        # データベースから関連データを検索
        database_context = self._gather_database_context(user_query)
        
        # 基本的なアドバイス
        advice_parts = []
        advice_parts.append('LLM機能は利用できませんが、データベース検索結果に基づいてご提案します。')
        
        # 検索結果に基づくアドバイス生成
        file_data = database_context.get('file_data', [])
        datasets = database_context.get('datasets', [])
        statistics = database_context.get('statistics', {})
        
        # 検索結果がない場合は、キーワードベースで個別検索を試行
        if not file_data:
            # 複合キーワードを分解して検索
            keywords_to_try = []
            
            # ユーザークエリから有効なキーワードを抽出
            query_keywords = user_query.lower().replace('の', ' ').replace('、', ' ').replace('，', ' ').split()
            keywords_to_try.extend(query_keywords)
            
            # 一般的な研究キーワードも追加
            common_keywords = ['機械学習', 'データセット', 'covid', 'nlp', '深層学習', '自然言語処理', 
                             'reinforcement', 'transformer', 'bert', 'データ分析', '画像分類']
            
            for keyword in common_keywords:
                if keyword in user_query.lower():
                    keywords_to_try.append(keyword)
            
            # 各キーワードで検索を試行
            for keyword in keywords_to_try:
                if keyword and len(keyword) > 1:
                    search_result = self.search_engine.search(keyword, limit=5)
                    if search_result.get('results'):
                        file_data = search_result['results']
                        advice_parts.append(f'キーワード「{keyword}」で関連データを検索しました。')
                        break
        
        if file_data or datasets:
            advice_parts.append(f'\n関連するデータが見つかりました：')
            
            # ファイルデータの要約
            if file_data:
                advice_parts.append(f'- ファイルデータ: {len(file_data)}件')
                for i, data in enumerate(file_data[:3], 1):
                    title = data.get('title', '無題')
                    field = data.get('research_field', '未分類')
                    data_type = data.get('data_type', '不明')
                    advice_parts.append(f'  {i}. {title} ({field}, {data_type})')
            
            # データセットの要約
            if datasets:
                advice_parts.append(f'- データセット: {len(datasets)}件')
                for i, dataset in enumerate(datasets[:2], 1):
                    name = dataset.get('name', '無名')
                    field = dataset.get('research_field', '不明')
                    advice_parts.append(f'  {i}. {name} ({field})')
        else:
            advice_parts.append('\n直接的に関連するデータは見つかりませんでしたが、データベースには以下のようなデータがあります：')
            
            # 統計情報から利用可能なデータを紹介
            if statistics:
                total_count = statistics.get('total_count', 0)
                type_counts = statistics.get('type_counts', {})
                field_counts = statistics.get('field_counts', {})
                recent_updates = statistics.get('recent_updates', [])
                
                advice_parts.append(f'\n総データ数: {total_count}件')
                
                if type_counts:
                    type_info = ', '.join([f'{k}: {v}件' for k, v in type_counts.items()])
                    advice_parts.append(f'データタイプ: {type_info}')
                
                if field_counts:
                    top_fields = list(field_counts.keys())[:5]
                    advice_parts.append(f'主要研究分野: {", ".join(top_fields)}')
                
                if recent_updates:
                    advice_parts.append(f'\n最近追加されたデータ:')
                    for i, update in enumerate(recent_updates[:3], 1):
                        advice_parts.append(f'  {i}. {update.get("title", "無題")}')
                        
                        # 最近のデータを推薦リストに追加
                        if not file_data:
                            if 'recent_recommendations' not in locals():
                                recent_recommendations = []
                            recent_recommendations.append({
                                'title': update.get('title', '無題'),
                                'type': 'recent_data',
                                'data_id': update.get('data_id'),
                                'reason': '最近追加されたデータとして参考になります',
                                'relevance_score': 0.5
                            })
                            
                    # recent_recommendationsが定義されている場合は推薦データに追加
                    if 'recent_recommendations' in locals():
                        if not file_data:
                            file_data = []
                        # file_dataを使って推薦を生成するため、ダミーデータを追加
                        for rec in recent_recommendations:
                            file_data.append({
                                'title': rec['title'],
                                'data_id': rec['data_id'],
                                'data_type': rec['type'],
                                'research_field': '最近追加'
                            })
        
        # 推薦データの生成
        recommendations = []
        if file_data:
            for data in file_data[:5]:
                recommendations.append({
                    'title': data.get('title', '無題'),
                    'type': data.get('data_type', 'unknown'),
                    'data_id': data.get('data_id'),
                    'reason': f"{data.get('research_field', '未分類')}分野のデータとして関連性があります",
                    'relevance_score': 0.7
                })
        
        if datasets:
            for dataset in datasets[:3]:
                recommendations.append({
                    'title': dataset.get('name', '無名'),
                    'type': 'dataset',
                    'dataset_id': dataset.get('dataset_id'),
                    'reason': f"{dataset.get('research_field', '不明')}分野のデータセットとして有用です",
                    'relevance_score': 0.8
                })
        
        # 検索提案の生成
        search_suggestions = ['機械学習', '自然言語処理', 'データサイエンス']
        if file_data:
            # 実際のデータの研究分野を提案に追加
            fields = list(set([data.get('research_field', '') for data in file_data if data.get('research_field')]))
            search_suggestions.extend(fields[:3])
        
        # 代替アプローチの生成
        alternative_approaches = [
            'メインメニューの「1. データを探す」でキーワード検索を試してください',
            'メインメニューの「3. データを管理する」でデータ一覧を確認してください'
        ]
        
        if consultation_type == 'dataset':
            alternative_approaches.append('データセット専用の検索機能を利用してください')
        
        # 研究方向性の提案
        research_direction = ''
        if file_data:
            common_fields = {}
            for data in file_data:
                field = data.get('research_field', '不明')
                common_fields[field] = common_fields.get(field, 0) + 1
            
            if common_fields:
                top_field = max(common_fields, key=common_fields.get)
                research_direction = f'{top_field}分野のデータが豊富にあります。この分野での研究を検討してはいかがでしょうか。'
        
        if not research_direction:
            research_direction = 'より具体的なキーワードで検索を試してみてください。'
        
        # 次のステップ
        next_steps = [
            '推薦されたデータの詳細を確認してください',
            'より具体的なキーワードで再検索してください'
        ]
        
        if not file_data and not datasets:
            next_steps.append('データを登録してデータベースを充実させてください')
        
        
        return {
            'query': user_query,
            'consultation_type': consultation_type,
            'advice': '\n'.join(advice_parts),
            'response_type': 'helpful' if (file_data or datasets) else 'no_data_found',
            'recommendations': recommendations,
            'search_suggestions': list(set(search_suggestions))[:7],
            'alternative_approaches': alternative_approaches,
            'research_direction': research_direction,
            'next_steps': next_steps,
            'related_fields': list(set([data.get('research_field', '') for data in file_data if data.get('research_field')]))[:5],
            'useful_tags': [],
            'llm_generated': False
        }
