"""
検索結果処理機能
検索結果のスコアリング、ソート、ファセット生成
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict


class ResultProcessor:
    """検索結果を処理するクラス"""
    
    def score_results(self, results: List[Dict[str, Any]], 
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
        keywords = parsed_query.get('keywords', '').lower().split() if parsed_query.get('keywords') else []
        phrases = parsed_query.get('phrases', [])
        exclude_keywords = parsed_query.get('exclude_keywords', [])
        
        for result in results:
            score = 0.0
            
            # 除外キーワードがある場合はスキップ
            if self._contains_exclude_keywords(result, exclude_keywords):
                continue
            
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
            for phrase in phrases:
                phrase_lower = phrase.lower()
                if phrase_lower in title:
                    score += 15.0
                elif phrase_lower in summary:
                    score += 8.0
            
            # 最近更新されたデータにボーナス
            score += self._calculate_recency_bonus(result)
            
            # データ品質ボーナス
            score += self._calculate_quality_bonus(result)
            
            result['_score'] = score
            scored_results.append(result)
        
        return scored_results
    
    def _contains_exclude_keywords(self, result: Dict[str, Any], 
                                  exclude_keywords: List[str]) -> bool:
        """
        除外キーワードが含まれているかチェック
        
        Args:
            result: 検索結果
            exclude_keywords: 除外キーワード
        
        Returns:
            除外キーワードが含まれている場合True
        """
        if not exclude_keywords:
            return False
        
        text_fields = [
            result.get('title', ''),
            result.get('summary', ''),
            result.get('research_field', '')
        ]
        
        full_text = ' '.join(text_fields).lower()
        
        return any(keyword.lower() in full_text for keyword in exclude_keywords)
    
    def _calculate_recency_bonus(self, result: Dict[str, Any]) -> float:
        """
        最新性ボーナスの計算
        
        Args:
            result: 検索結果
        
        Returns:
            最新性ボーナススコア
        """
        if not result.get('updated_at'):
            return 0.0
        
        try:
            updated = datetime.fromisoformat(result['updated_at'])
            days_old = (datetime.now() - updated).days
            
            if days_old < 7:
                return 2.0
            elif days_old < 30:
                return 1.0
            elif days_old < 90:
                return 0.5
            else:
                return 0.0
        except:
            return 0.0
    
    def _calculate_quality_bonus(self, result: Dict[str, Any]) -> float:
        """
        品質ボーナスの計算
        
        Args:
            result: 検索結果
        
        Returns:
            品質ボーナススコア
        """
        bonus = 0.0
        
        # タイトルの長さボーナス
        title = result.get('title', '')
        if 10 <= len(title) <= 100:
            bonus += 1.0
        
        # 概要の存在ボーナス
        summary = result.get('summary', '')
        if summary and len(summary) > 20:
            bonus += 1.0
        
        # 研究分野の存在ボーナス
        if result.get('research_field') and result['research_field'] != '未分類':
            bonus += 0.5
        
        # メタデータの豊富さボーナス
        metadata = result.get('metadata', {})
        if isinstance(metadata, dict) and len(metadata) > 3:
            bonus += 0.5
        
        return bonus
    
    def sort_results(self, results: List[Dict[str, Any]], 
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
        elif sort_by == 'data_type':
            return sorted(results, key=lambda x: x.get('data_type', ''))
        elif sort_by == 'research_field':
            return sorted(results, key=lambda x: x.get('research_field', ''))
        else:
            return results
    
    def generate_facets(self, results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        ファセット情報を生成
        
        Args:
            results: 検索結果
        
        Returns:
            ファセット情報
        """
        facets = {
            'data_type': defaultdict(int),
            'research_field': defaultdict(int),
            'file_extension': defaultdict(int),
            'year': defaultdict(int)
        }
        
        # データタイプの集計
        for result in results:
            data_type = result.get('data_type', 'unknown')
            facets['data_type'][data_type] += 1
        
        # 研究分野の集計
        for result in results:
            field = result.get('research_field', '未分類')
            if field:
                facets['research_field'][field] += 1
        
        # ファイル拡張子の集計
        for result in results:
            metadata = result.get('metadata', {})
            if isinstance(metadata, dict):
                ext = metadata.get('file_extension', '')
                if ext:
                    facets['file_extension'][ext] += 1
        
        # 年別の集計
        for result in results:
            created_date = result.get('created_date', '')
            if created_date:
                try:
                    year = created_date[:4]
                    if year.isdigit():
                        facets['year'][year] += 1
                except:
                    pass
        
        # リスト形式に変換
        return {
            'data_type': [
                {'value': k, 'count': v} 
                for k, v in sorted(facets['data_type'].items(), key=lambda x: x[1], reverse=True)
            ],
            'research_field': [
                {'value': k, 'count': v} 
                for k, v in sorted(facets['research_field'].items(), key=lambda x: x[1], reverse=True)
            ][:10],  # 上位10件のみ
            'file_extension': [
                {'value': k, 'count': v} 
                for k, v in sorted(facets['file_extension'].items(), key=lambda x: x[1], reverse=True)
            ][:5],   # 上位5件のみ
            'year': [
                {'value': k, 'count': v} 
                for k, v in sorted(facets['year'].items(), reverse=True)
            ][:5]    # 最新5年分
        }
    
    def generate_suggestions(self, query: Optional[str], 
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
            # 汎用的なサジェスト
            suggestions = [
                "機械学習",
                "自然言語処理", 
                "データセット",
                "deep learning",
                "computer vision"
            ]
        else:
            # 検索結果から関連キーワードを抽出
            field_counts = defaultdict(int)
            
            for result in results[:20]:  # 上位20件から抽出
                field = result.get('research_field')
                if field and field != '未分類':
                    field_counts[field] += 1
            
            # 頻出する研究分野をサジェスト
            sorted_fields = sorted(field_counts.items(), key=lambda x: x[1], reverse=True)
            for field, count in sorted_fields[:3]:
                if field.lower() not in query.lower():
                    suggestions.append(f"{query} {field}")
        
        return suggestions[:5]  # 最大5件
    
    def apply_pagination(self, results: List[Dict[str, Any]], 
                        offset: int, limit: int) -> Dict[str, Any]:
        """
        ページネーションを適用
        
        Args:
            results: 検索結果
            offset: オフセット
            limit: 取得件数
        
        Returns:
            ページネーション適用後の結果
        """
        total_count = len(results)
        paginated_results = results[offset:offset + limit]
        
        return {
            'results': paginated_results,
            'total_count': total_count,
            'returned_count': len(paginated_results),
            'offset': offset,
            'limit': limit,
            'has_more': offset + limit < total_count
        }
    
    def highlight_keywords(self, text: str, keywords: List[str]) -> str:
        """
        テキスト内のキーワードをハイライト
        
        Args:
            text: 対象テキスト
            keywords: ハイライトするキーワード
        
        Returns:
            ハイライト済みテキスト
        """
        if not text or not keywords:
            return text
        
        highlighted = text
        for keyword in keywords:
            if keyword:
                # 簡易的なハイライト（HTMLタグで囲む）
                pattern = re.compile(re.escape(keyword), re.IGNORECASE)
                highlighted = pattern.sub(f'<mark>{keyword}</mark>', highlighted)
        
        return highlighted