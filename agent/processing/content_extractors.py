"""
コンテンツ抽出機能
ファイルタイプ別のコンテンツ抽出処理
"""
import json
import re
from typing import Dict, Any
from pathlib import Path


class ContentExtractors:
    """ファイルタイプ別のコンテンツ抽出を行うクラス"""
    
    def process_json_file(self, file_path: str) -> Dict[str, Any]:
        """
        JSONファイルを処理
        
        Args:
            file_path: JSONファイルパス
        
        Returns:
            処理結果
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result = {}
            
            if isinstance(data, dict):
                # タイトルの抽出
                result['title'] = self._extract_json_title(data)
                
                # 概要の抽出
                result['summary'] = self._extract_json_summary(data)
                
                # 研究分野の抽出
                result['research_field'] = self._extract_json_field(data)
                
                # データセットの特徴抽出
                result['additional_metadata'] = self._extract_json_metadata(data)
                
            elif isinstance(data, list):
                result['additional_metadata'] = {
                    'sample_count': len(data),
                    'data_structure': 'array'
                }
                
                if data and isinstance(data[0], dict):
                    result['additional_metadata']['fields'] = list(data[0].keys())
                
                # リストの場合、ファイル名をタイトルとして使用
                result['title'] = Path(file_path).stem
            
            return result
            
        except Exception as e:
            return {
                'parse_error': str(e),
                'title': Path(file_path).stem
            }
    
    def _extract_json_title(self, data: dict) -> str:
        """JSONデータからタイトルを抽出"""
        title_candidates = ['title', 'name', 'dataset_name', '名前', 'タイトル']
        
        for key in title_candidates:
            if key in data:
                return str(data[key])
        
        return ''
    
    def _extract_json_summary(self, data: dict) -> str:
        """JSONデータから概要を抽出"""
        summary_candidates = ['description', 'summary', 'abstract', '説明', '概要']
        
        for key in summary_candidates:
            if key in data:
                summary = str(data[key])
                return summary[:500] if len(summary) > 500 else summary
        
        return ''
    
    def _extract_json_field(self, data: dict) -> str:
        """JSONデータから研究分野を抽出"""
        field_candidates = ['field', 'category', 'research_field', '分野', 'カテゴリー']
        
        for key in field_candidates:
            if key in data:
                return str(data[key])
        
        return ''
    
    def _extract_json_metadata(self, data: dict) -> Dict[str, Any]:
        """JSONデータから追加メタデータを抽出"""
        metadata = {}
        
        # データ構造の情報
        if 'data' in data and isinstance(data['data'], list):
            sample_count = len(data['data'])
            metadata.update({
                'sample_count': sample_count,
                'data_structure': 'list_of_records'
            })
            
            # サンプルデータから特徴を抽出
            if data['data'] and isinstance(data['data'][0], dict):
                metadata['fields'] = list(data['data'][0].keys())
        
        # その他の有用な情報
        metadata['json_keys'] = list(data.keys())[:10]  # 最初の10個のキー
        
        return metadata
    
    def process_text_file(self, file_path: str) -> Dict[str, Any]:
        """
        テキストファイルを処理
        
        Args:
            file_path: テキストファイルパス
        
        Returns:
            処理結果
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            result = {}
            
            # Markdownファイルの処理
            if file_path.endswith('.md'):
                result.update(self._process_markdown_content(lines))
            else:
                # プレーンテキストの処理
                result.update(self._process_plain_text_content(lines))
            
            # キーワード抽出による研究分野の推定
            result['research_field'] = self._infer_research_field_from_text(content)
            
            return result
            
        except Exception as e:
            return {
                'parse_error': str(e),
                'title': Path(file_path).stem
            }
    
    def _process_markdown_content(self, lines: list) -> Dict[str, Any]:
        """Markdownコンテンツの処理"""
        result = {}
        
        # タイトルの抽出（最初のH1）
        for line in lines:
            if line.startswith('# '):
                result['title'] = line[2:].strip()
                break
        
        # 概要の生成（最初の段落）
        paragraphs = []
        current_paragraph = []
        
        for line in lines:
            if line.strip() == '':
                if current_paragraph:
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
            elif not line.startswith('#'):
                current_paragraph.append(line.strip())
        
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        if paragraphs:
            result['summary'] = paragraphs[0][:500]
        
        return result
    
    def _process_plain_text_content(self, lines: list) -> Dict[str, Any]:
        """プレーンテキストコンテンツの処理"""
        result = {}
        
        # 最初の非空行をタイトルとする
        for line in lines:
            if line.strip():
                result['title'] = line.strip()[:100]
                break
        
        # 最初の数行を概要とする
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        if len(non_empty_lines) > 1:
            result['summary'] = ' '.join(non_empty_lines[1:4])[:500]
        
        return result
    
    def _infer_research_field_from_text(self, text: str) -> str:
        """
        テキストから研究分野を推定
        
        Args:
            text: テキスト内容
        
        Returns:
            推定された研究分野
        """
        # 研究分野のキーワードマッピング
        field_keywords = {
            '機械学習': ['機械学習', 'machine learning', 'ML', 'ディープラーニング', 'deep learning', 'ニューラルネットワーク'],
            '自然言語処理': ['自然言語処理', 'NLP', 'natural language', 'テキスト解析', '形態素解析', '構文解析'],
            'コンピュータビジョン': ['画像認識', 'computer vision', '画像処理', 'CV', '物体検出', 'セグメンテーション'],
            'データサイエンス': ['データ分析', 'data science', '統計', 'ビッグデータ', 'データマイニング'],
            'バイオインフォマティクス': ['バイオ', 'ゲノム', '遺伝子', 'タンパク質', 'DNA', 'RNA'],
            '医療AI': ['医療', '診断', '病気', '患者', 'ヘルスケア', '創薬'],
            'ロボティクス': ['ロボット', 'robotics', '制御', 'センサー', 'アクチュエータ'],
            '量子コンピューティング': ['量子', 'quantum', 'qubit', '量子ビット', '量子アルゴリズム']
        }
        
        text_lower = text.lower()
        field_scores = {}
        
        # 各分野のスコアを計算
        for field, keywords in field_keywords.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text_lower)
            if score > 0:
                field_scores[field] = score
        
        # 最もスコアの高い分野を返す
        if field_scores:
            return max(field_scores.items(), key=lambda x: x[1])[0]
        
        return '未分類'
    
    def process_pdf_file(self, file_path: str) -> Dict[str, Any]:
        """
        PDFファイルを処理
        
        Args:
            file_path: PDFファイルパス
        
        Returns:
            処理結果
        """
        result = {
            'title': Path(file_path).stem,
            'summary': '',
            'additional_metadata': {
                'file_type': 'pdf',
                'requires_ocr': False
            }
        }
        
        try:
            # PyPDF2を試行
            try:
                import PyPDF2
                text = self._extract_text_with_pypdf2(file_path)
                if text.strip():
                    result['summary'] = text[:500] + '...' if len(text) > 500 else text
                    result['additional_metadata']['text_extracted'] = True
                    return result
            except ImportError:
                pass
            
            # pdfplumberを試行
            try:
                import pdfplumber
                text = self._extract_text_with_pdfplumber(file_path)
                if text.strip():
                    result['summary'] = text[:500] + '...' if len(text) > 500 else text
                    result['additional_metadata']['text_extracted'] = True
                    return result
            except ImportError:
                pass
            
            # PDF処理ライブラリがない場合は基本情報のみ
            result['summary'] = 'PDFファイル（テキスト抽出ライブラリが必要）'
            result['additional_metadata']['requires_ocr'] = True
            
        except Exception as e:
            result['summary'] = f'PDFファイル（読み取りエラー: {str(e)}）'
            result['additional_metadata']['error'] = str(e)
        
        return result
    
    def _extract_text_with_pypdf2(self, file_path: str) -> str:
        """PyPDF2を使用してテキストを抽出"""
        import PyPDF2
        
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # 最初の数ページからテキストを抽出
            max_pages = min(3, len(pdf_reader.pages))
            for page_num in range(max_pages):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
        
        return text.strip()
    
    def _extract_text_with_pdfplumber(self, file_path: str) -> str:
        """pdfplumberを使用してテキストを抽出"""
        import pdfplumber
        
        text = ""
        with pdfplumber.open(file_path) as pdf:
            # 最初の数ページからテキストを抽出
            max_pages = min(3, len(pdf.pages))
            for page_num in range(max_pages):
                page = pdf.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        return text.strip()
    
    def process_csv_file(self, file_path: str) -> Dict[str, Any]:
        """
        CSVファイルを処理
        
        Args:
            file_path: CSVファイルパス
        
        Returns:
            処理結果
        """
        try:
            import csv
            
            with open(file_path, 'r', encoding='utf-8') as f:
                # ファイルの最初の数行を読んで構造を把握
                sample = f.read(1024)
                f.seek(0)
                
                # 区切り文字の推定
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                # CSVの読み込み
                reader = csv.reader(f, delimiter=delimiter)
                
                # ヘッダーの取得
                headers = next(reader, [])
                
                # データ行数のカウント
                row_count = sum(1 for row in reader)
            
            return {
                'title': Path(file_path).stem,
                'summary': f'CSVファイル（{len(headers)}列, {row_count}行）',
                'additional_metadata': {
                    'file_type': 'csv',
                    'columns': headers[:10],  # 最初の10列
                    'column_count': len(headers),
                    'row_count': row_count,
                    'delimiter': delimiter
                }
            }
            
        except Exception as e:
            return {
                'title': Path(file_path).stem,
                'summary': 'CSVファイル（解析エラー）',
                'parse_error': str(e),
                'additional_metadata': {
                    'file_type': 'csv'
                }
            }
    
    def extract_content_preview(self, file_path: str, max_length: int = 200) -> str:
        """
        ファイルの内容プレビューを抽出
        
        Args:
            file_path: ファイルパス
            max_length: 最大文字数
        
        Returns:
            内容のプレビュー
        """
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(max_length * 2)
                    return self._format_json_preview(content, max_length)
            
            elif file_path.endswith(('.txt', '.md')):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(max_length)
                    return content[:max_length]
            
            elif file_path.endswith('.csv'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= 3:  # 最初の3行のみ
                            break
                        lines.append(line.strip())
                    return '\n'.join(lines)
            
            else:
                return f"プレビュー不可: {Path(file_path).suffix}ファイル"
        
        except Exception as e:
            return f"プレビューエラー: {str(e)}"
    
    def _format_json_preview(self, content: str, max_length: int) -> str:
        """JSONファイルのプレビューをフォーマット"""
        try:
            # JSONをパースして整形
            data = json.loads(content)
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            
            if len(formatted) > max_length:
                return formatted[:max_length] + "..."
            else:
                return formatted
        except:
            # JSONパースに失敗した場合は生のテキストを返す
            return content[:max_length]