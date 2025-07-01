"""
Gemini API分析機能
Google Gemini APIを使用した高度な分析処理
"""
import json
import re
from typing import Dict, Any, Optional

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

from ..config import Config


class GeminiAnalyzer:
    """Gemini APIを使用した分析を行うクラス"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Gemini分析器の初期化
        
        Args:
            config: 設定オブジェクト
        """
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
    
    def is_available(self) -> bool:
        """
        Gemini APIが利用可能かチェック
        
        Returns:
            利用可能な場合True
        """
        return self.available and self.model is not None
    
    def analyze_file_content(self, file_path: str, content_preview: str) -> Dict[str, Any]:
        """
        ファイル内容をGemini APIで分析
        
        Args:
            file_path: ファイルパス
            content_preview: ファイル内容のプレビュー
        
        Returns:
            分析結果
        """
        if not self.is_available():
            return {}
        
        try:
            # プロンプトの構築
            prompt = self._build_analysis_prompt(file_path, content_preview)
            
            # Gemini APIの呼び出し
            response = self.model.generate_content(prompt)
            
            # レスポンスの解析
            return self._parse_gemini_response(response.text)
            
        except Exception as e:
            print(f"Gemini分析エラー: {e}")
            print(f"ファイルパス: {file_path}")
            print(f"コンテンツプレビュー: {content_preview[:200]}...")
            return {}
    
    def _build_analysis_prompt(self, file_path: str, content_preview: str) -> str:
        """
        分析用のプロンプトを構築
        
        Args:
            file_path: ファイルパス
            content_preview: ファイル内容のプレビュー
        
        Returns:
            プロンプト文字列
        """
        file_extension = file_path.split('.')[-1].lower()
        
        prompt = f"""
以下のファイル内容を分析して、研究データの情報を抽出してください：

ファイル名: {file_path}
ファイル形式: {file_extension}
内容のプレビュー:
{content_preview[:2000]}

以下の情報をJSON形式で抽出してください：
1. title: 適切なタイトル（ファイル内容から推定）
2. summary: 100文字程度の要約
3. research_field: 研究分野（機械学習、自然言語処理、データサイエンス、コンピュータビジョン、医療AI、ロボティクス、バイオインフォマティクスなど）
4. keywords: 主要なキーワード（最大5個）
5. data_quality: データの品質評価（high, medium, low）
6. complexity: 内容の複雑さ（simple, moderate, complex）

JSON形式で回答してください。例：
{{
  "title": "機械学習データセット",
  "summary": "画像分類タスク用のラベル付きデータセット",
  "research_field": "機械学習",
  "keywords": ["画像分類", "深層学習", "CNN", "データセット"],
  "data_quality": "high",
  "complexity": "moderate"
}}
"""
        return prompt
    
    def _parse_gemini_response(self, response_text: str) -> Dict[str, Any]:
        """
        Geminiのレスポンスを解析
        
        Args:
            response_text: レスポンステキスト
        
        Returns:
            解析結果
        """
        try:
            # JSONブロックを複数の方法で抽出
            json_data = self._extract_json_from_text(response_text)
            
            if json_data:
                # データの正規化と検証
                result = {}
                
                if json_data.get('title'):
                    result['title'] = str(json_data['title'])[:200]
                
                if json_data.get('summary'):
                    result['summary'] = str(json_data['summary'])[:500]
                
                if json_data.get('research_field'):
                    result['research_field'] = str(json_data['research_field'])
                
                if json_data.get('keywords'):
                    keywords = json_data['keywords']
                    if isinstance(keywords, list):
                        result['keywords'] = keywords[:5]
                
                if json_data.get('data_quality'):
                    quality = str(json_data['data_quality']).lower()
                    if quality in ['high', 'medium', 'low']:
                        result['data_quality'] = quality
                
                if json_data.get('complexity'):
                    complexity = str(json_data['complexity']).lower()
                    if complexity in ['simple', 'moderate', 'complex']:
                        result['complexity'] = complexity
                
                return result
            
        except Exception as e:
            print(f"Geminiレスポンス解析エラー: {e}")
            print(f"レスポンステキスト: {response_text[:500]}...")
        
        return {}
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        テキストからJSONを抽出（複数の方法を試行）
        
        Args:
            text: 解析対象のテキスト
        
        Returns:
            解析されたJSONデータ、失敗時はNone
        """
        # 方法1: 標準的なJSON抽出
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # 方法2: コードブロック内のJSON抽出
        try:
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL | re.IGNORECASE)
            if code_block_match:
                json_str = code_block_match.group(1)
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # 方法3: JSONの修復を試行
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                # 一般的なJSONエラーを修復
                json_str = self._fix_json_format(json_str)
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # 方法4: 行ごとにJSONパースを試行
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if '{' in line:
                # 複数行のJSONを組み立て
                json_lines = []
                brace_count = 0
                for j in range(i, len(lines)):
                    json_lines.append(lines[j])
                    brace_count += lines[j].count('{') - lines[j].count('}')
                    if brace_count == 0 and '{' in lines[j]:
                        try:
                            json_str = '\n'.join(json_lines)
                            json_str = self._fix_json_format(json_str)
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            break
                        break
        
        return None
    
    def _fix_json_format(self, json_str: str) -> str:
        """
        一般的なJSON形式エラーを修復
        
        Args:
            json_str: 修復対象のJSON文字列
        
        Returns:
            修復されたJSON文字列
        """
        # 先頭・末尾の不要な文字を削除
        json_str = json_str.strip()
        
        # JavaScriptのコメントを削除
        json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # シングルクォートをダブルクォートに変換
        json_str = re.sub(r"'([^']*)':", r'"\1":', json_str)
        json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
        
        # 末尾のカンマを削除
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # キーにダブルクォートがない場合の修復
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        
        # 不正な改行文字を削除
        json_str = json_str.replace('\n', ' ').replace('\r', ' ')
        
        # 重複する空白を削除
        json_str = re.sub(r'\s+', ' ', json_str)
        
        return json_str
    
    def generate_research_summary(self, data_list: list) -> Dict[str, Any]:
        """
        複数のデータから研究サマリーを生成
        
        Args:
            data_list: データのリスト
        
        Returns:
            研究サマリー
        """
        if not self.is_available() or not data_list:
            return {}
        
        try:
            # データを要約用に変換
            data_summary = []
            for data in data_list[:10]:  # 最大10件
                summary_item = {
                    'title': data.get('title', ''),
                    'research_field': data.get('research_field', ''),
                    'data_type': data.get('data_type', '')
                }
                data_summary.append(summary_item)
            
            # プロンプトの構築
            prompt = f"""
以下の研究データリストを分析して、全体的な研究動向をまとめてください：

データリスト:
{json.dumps(data_summary, ensure_ascii=False, indent=2)}

以下の観点で分析してください：
1. 主要な研究分野とその傾向
2. よく使われているデータタイプ
3. 研究の特徴や共通点
4. 今後の研究方向性の示唆

JSON形式で回答してください：
{{
  "main_fields": ["分野1", "分野2"],
  "trends": "研究動向の説明",
  "data_types": {{"dataset": 5, "paper": 3}},
  "characteristics": "研究の特徴",
  "future_directions": "今後の方向性"
}}
"""
            
            # Gemini APIの呼び出し
            response = self.model.generate_content(prompt)
            
            # レスポンスの解析
            return self._parse_research_summary_response(response.text)
            
        except Exception as e:
            print(f"研究サマリー生成エラー: {e}")
            return {}
    
    def _parse_research_summary_response(self, response_text: str) -> Dict[str, Any]:
        """
        研究サマリーレスポンスを解析
        
        Args:
            response_text: レスポンステキスト
        
        Returns:
            解析結果
        """
        json_data = self._extract_json_from_text(response_text)
        return json_data if json_data else {}
    
    def suggest_related_research(self, query: str, existing_data: list) -> Dict[str, Any]:
        """
        関連研究の提案を生成
        
        Args:
            query: ユーザーのクエリ
            existing_data: 既存データ
        
        Returns:
            関連研究の提案
        """
        if not self.is_available():
            return {}
        
        try:
            # 既存データの要約
            data_context = []
            for data in existing_data[:5]:
                context_item = {
                    'title': data.get('title', ''),
                    'research_field': data.get('research_field', ''),
                    'summary': data.get('summary', '')[:100]
                }
                data_context.append(context_item)
            
            prompt = f"""
ユーザーの質問: {query}

関連する既存データ:
{json.dumps(data_context, ensure_ascii=False, indent=2)}

これらの情報を基に、ユーザーの研究に役立つ以下の提案をしてください：

1. 関連研究のキーワード
2. 調査すべき研究分野
3. 参考になりそうなデータタイプ
4. 研究アプローチの提案

JSON形式で回答してください：
{{
  "related_keywords": ["キーワード1", "キーワード2"],
  "research_fields": ["分野1", "分野2"],
  "recommended_data_types": ["dataset", "paper"],
  "research_approaches": "研究アプローチの提案"
}}
"""
            
            response = self.model.generate_content(prompt)
            return self._parse_suggestion_response(response.text)
            
        except Exception as e:
            print(f"関連研究提案エラー: {e}")
            return {}
    
    def _parse_suggestion_response(self, response_text: str) -> Dict[str, Any]:
        """
        提案レスポンスを解析
        
        Args:
            response_text: レスポンステキスト
        
        Returns:
            解析結果
        """
        json_data = self._extract_json_from_text(response_text)
        return json_data if json_data else {}