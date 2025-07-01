"""
統合ファイルプロセッサクラス
分割された機能を統合して従来のインターフェースを提供
"""
from typing import Dict, Any, Optional, List

from ..config import Config
from .content_extractors import ContentExtractors
from .gemini_analyzer import GeminiAnalyzer


class FileProcessor:
    """ファイルを処理して情報を抽出するクラス（リファクタリング版）"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        ファイルプロセッサの初期化
        
        Args:
            config: 設定オブジェクト
        """
        self.config = config or Config()
        
        # 分割された機能クラスのインスタンス化
        self.content_extractors = ContentExtractors()
        self.gemini_analyzer = GeminiAnalyzer(self.config)
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        """
        ファイルを処理して情報を抽出
        
        Args:
            file_path: ファイルパス
        
        Returns:
            処理結果の辞書
        """
        result = {
            'title': None,
            'summary': '',
            'research_field': '',
            'additional_metadata': {}
        }
        
        # ファイルタイプに応じた基本処理
        if file_path.endswith('.json'):
            result.update(self.content_extractors.process_json_file(file_path))
        elif file_path.endswith(('.txt', '.md')):
            result.update(self.content_extractors.process_text_file(file_path))
        elif file_path.endswith('.pdf'):
            result.update(self.content_extractors.process_pdf_file(file_path))
        elif file_path.endswith('.csv'):
            result.update(self.content_extractors.process_csv_file(file_path))
        
        # Gemini APIによる高度な解析（利用可能な場合）
        if self.gemini_analyzer.is_available() and self.config.use_gemini_for_analysis:
            gemini_result = self._analyze_with_gemini(file_path, result)
            result.update(gemini_result)
        
        return result
    
    def _analyze_with_gemini(self, file_path: str, current_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gemini APIを使用してファイルを解析
        
        Args:
            file_path: ファイルパス
            current_result: 現在の処理結果
        
        Returns:
            Gemini解析結果
        """
        try:
            # ファイル内容のプレビューを取得
            content_preview = self.content_extractors.extract_content_preview(file_path)
            
            # Gemini分析の実行
            gemini_result = self.gemini_analyzer.analyze_file_content(file_path, content_preview)
            
            if gemini_result:
                # 既存の結果がない場合のみGeminiの結果を使用
                result = {}
                
                if not current_result.get('title') and gemini_result.get('title'):
                    result['title'] = gemini_result['title']
                
                if not current_result.get('summary') and gemini_result.get('summary'):
                    result['summary'] = gemini_result['summary']
                
                if (not current_result.get('research_field') or 
                    current_result.get('research_field') == '未分類') and \
                   gemini_result.get('research_field'):
                    result['research_field'] = gemini_result['research_field']
                
                # 追加メタデータの統合
                if gemini_result.get('keywords') or gemini_result.get('data_quality'):
                    additional_metadata = current_result.get('additional_metadata', {})
                    
                    if gemini_result.get('keywords'):
                        additional_metadata['keywords'] = gemini_result['keywords']
                    
                    if gemini_result.get('data_quality'):
                        additional_metadata['data_quality'] = gemini_result['data_quality']
                    
                    if gemini_result.get('complexity'):
                        additional_metadata['complexity'] = gemini_result['complexity']
                    
                    result['additional_metadata'] = additional_metadata
                
                return result
            
        except Exception as e:
            print(f"Gemini解析エラー: {e}")
        
        return {}
    
    def batch_process_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        複数ファイルをバッチ処理
        
        Args:
            file_paths: ファイルパスのリスト
        
        Returns:
            処理結果のリスト
        """
        results = []
        
        for file_path in file_paths:
            try:
                result = self.process_file(file_path)
                result['file_path'] = file_path
                result['process_status'] = 'success'
                results.append(result)
            except Exception as e:
                results.append({
                    'file_path': file_path,
                    'process_status': 'error',
                    'error': str(e)
                })
        
        return results
    
    def get_content_preview(self, file_path: str, max_length: int = 200) -> str:
        """
        ファイルの内容プレビューを取得
        
        Args:
            file_path: ファイルパス
            max_length: 最大文字数
        
        Returns:
            内容のプレビュー
        """
        return self.content_extractors.extract_content_preview(file_path, max_length)
    
    def generate_research_summary(self, data_list: list) -> Dict[str, Any]:
        """
        複数のデータから研究サマリーを生成
        
        Args:
            data_list: データのリスト
        
        Returns:
            研究サマリー
        """
        return self.gemini_analyzer.generate_research_summary(data_list)
    
    def suggest_related_research(self, query: str, existing_data: list) -> Dict[str, Any]:
        """
        関連研究の提案を生成
        
        Args:
            query: ユーザーのクエリ
            existing_data: 既存データ
        
        Returns:
            関連研究の提案
        """
        return self.gemini_analyzer.suggest_related_research(query, existing_data)
    
    # === 後方互換性のためのメソッド ===
    
    def _process_json_file(self, file_path: str) -> Dict[str, Any]:
        """後方互換性のためのJSONファイル処理メソッド"""
        return self.content_extractors.process_json_file(file_path)
    
    def _process_text_file(self, file_path: str) -> Dict[str, Any]:
        """後方互換性のためのテキストファイル処理メソッド"""
        return self.content_extractors.process_text_file(file_path)
    
    def _process_pdf_file(self, file_path: str) -> Dict[str, Any]:
        """後方互換性のためのPDFファイル処理メソッド"""
        return self.content_extractors.process_pdf_file(file_path)
    
    def _infer_research_field_from_text(self, text: str) -> str:
        """後方互換性のための研究分野推定メソッド"""
        return self.content_extractors._infer_research_field_from_text(text)