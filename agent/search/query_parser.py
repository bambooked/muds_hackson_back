"""
クエリ解析機能
検索クエリの解析と前処理
"""
import re
from typing import Dict, Any, List


class QueryParser:
    """検索クエリを解析するクラス"""
    
    def parse_query(self, query: str) -> Dict[str, Any]:
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
            'phrases': [],
            'field_searches': {},
            'filters': {}
        }
        
        # フレーズ検索の抽出（"..."で囲まれた部分）
        phrase_pattern = r'"([^"]+)"'
        phrases = re.findall(phrase_pattern, query)
        parsed['phrases'] = phrases
        
        # フレーズを除いたキーワード
        keywords = re.sub(phrase_pattern, '', query).strip()
        
        # フィールド検索の抽出（field:value形式）
        field_pattern = r'(\w+):\s*([^\s]+)'
        field_matches = re.findall(field_pattern, keywords)
        for field, value in field_matches:
            parsed['field_searches'][field] = value
        
        # フィールド検索を除いたキーワード
        keywords = re.sub(field_pattern, '', keywords).strip()
        parsed['keywords'] = keywords
        
        # 検索演算子の検出（AND, OR, NOT）
        if ' AND ' in query.upper():
            parsed['operators'].append('AND')
        if ' OR ' in query.upper():
            parsed['operators'].append('OR')
        if ' NOT ' in query.upper():
            parsed['operators'].append('NOT')
        
        # 除外キーワードの検出（-keyword形式）
        exclude_pattern = r'-(\w+)'
        exclude_keywords = re.findall(exclude_pattern, keywords)
        if exclude_keywords:
            parsed['exclude_keywords'] = exclude_keywords
            # 除外キーワードを削除
            keywords = re.sub(exclude_pattern, '', keywords).strip()
            parsed['keywords'] = keywords
        
        return parsed
    
    def build_search_conditions(self, parsed_query: Dict[str, Any], 
                               filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        解析されたクエリから検索条件を構築
        
        Args:
            parsed_query: 解析済みクエリ
            filters: 追加フィルター
        
        Returns:
            検索条件
        """
        conditions = {
            'keywords': [],
            'phrases': parsed_query.get('phrases', []),
            'exclude_keywords': parsed_query.get('exclude_keywords', []),
            'field_searches': parsed_query.get('field_searches', {}),
            'filters': filters or {}
        }
        
        # キーワードの分割と正規化
        keywords = parsed_query.get('keywords', '')
        if keywords:
            # 複数のスペースを単一に変換し、分割
            keywords = re.sub(r'\s+', ' ', keywords)
            conditions['keywords'] = [kw.strip() for kw in keywords.split() if kw.strip()]
        
        return conditions
    
    def normalize_query(self, query: str) -> str:
        """
        クエリの正規化
        
        Args:
            query: 元のクエリ
        
        Returns:
            正規化されたクエリ
        """
        # 余分な空白を削除
        normalized = re.sub(r'\s+', ' ', query.strip())
        
        # 全角英数字を半角に変換
        normalized = self._zenkaku_to_hankaku(normalized)
        
        return normalized
    
    def _zenkaku_to_hankaku(self, text: str) -> str:
        """
        全角英数字を半角に変換
        
        Args:
            text: 変換対象のテキスト
        
        Returns:
            変換後のテキスト
        """
        # 簡易的な全角→半角変換
        zenkaku = "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
        hankaku = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        
        for z, h in zip(zenkaku, hankaku):
            text = text.replace(z, h)
        
        return text
    
    def extract_search_intent(self, query: str) -> Dict[str, Any]:
        """
        クエリから検索意図を抽出
        
        Args:
            query: 検索クエリ
        
        Returns:
            検索意図の情報
        """
        intent = {
            'type': 'general',
            'data_type_preference': None,
            'research_field_hint': None,
            'temporal_filter': None,
            'quality_preference': None
        }
        
        query_lower = query.lower()
        
        # データタイプの推定
        if any(word in query_lower for word in ['データセット', 'dataset', 'data']):
            intent['data_type_preference'] = 'dataset'
        elif any(word in query_lower for word in ['論文', 'paper', '研究']):
            intent['data_type_preference'] = 'paper'
        elif any(word in query_lower for word in ['ポスター', 'poster', '発表']):
            intent['data_type_preference'] = 'poster'
        
        # 研究分野のヒント
        field_keywords = {
            '機械学習': ['機械学習', 'machine learning', 'ml', 'ディープラーニング', 'deep learning'],
            '自然言語処理': ['自然言語処理', 'nlp', 'natural language', 'テキスト解析'],
            'コンピュータビジョン': ['画像認識', 'computer vision', 'cv', '画像処理'],
            'データサイエンス': ['データ分析', 'data science', '統計', 'analytics'],
            '医療AI': ['医療', '診断', 'medical', 'healthcare']
        }
        
        for field, keywords in field_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                intent['research_field_hint'] = field
                break
        
        # 時間的フィルター
        if any(word in query_lower for word in ['最新', '新しい', 'recent', 'latest']):
            intent['temporal_filter'] = 'recent'
        elif any(word in query_lower for word in ['古い', 'old', '過去']):
            intent['temporal_filter'] = 'old'
        
        # 品質の好み
        if any(word in query_lower for word in ['高品質', 'quality', '良い', 'best']):
            intent['quality_preference'] = 'high'
        
        return intent
    
    def suggest_query_improvements(self, query: str, results_count: int) -> List[str]:
        """
        クエリの改善案を提案
        
        Args:
            query: 元のクエリ
            results_count: 検索結果数
        
        Returns:
            改善案のリスト
        """
        suggestions = []
        
        if results_count == 0:
            # 結果が0件の場合
            if len(query.split()) > 3:
                suggestions.append("キーワードを減らしてみてください")
            
            if '"' in query:
                suggestions.append("フレーズ検索を解除してみてください")
            
            suggestions.append("類似語や関連語で検索してみてください")
            suggestions.append("英語のキーワードも試してみてください")
        
        elif results_count > 100:
            # 結果が多すぎる場合
            suggestions.append("より具体的なキーワードを追加してください")
            suggestions.append("データタイプでフィルタしてください")
            suggestions.append("研究分野を指定してください")
        
        return suggestions