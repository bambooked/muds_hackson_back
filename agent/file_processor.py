"""
ファイル処理モジュール
ファイルの解析、要約生成、研究分野の推定などを行う
"""
import os
import json
import re
from typing import Dict, Any, Optional, List
from pathlib import Path
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
from .config import Config


class FileProcessor:
    """ファイルを処理して情報を抽出するクラス"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        ファイルプロセッサの初期化
        
        Args:
            config: 設定オブジェクト
        """
        self.config = config or Config()
        self._init_gemini()
    
    def _init_gemini(self):
        """Gemini APIの初期化"""
        if GEMINI_AVAILABLE and self.config.gemini_api_key:
            genai.configure(api_key=self.config.gemini_api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None
    
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
        
        # ファイルタイプに応じた処理
        if file_path.endswith('.json'):
            result.update(self._process_json_file(file_path))
        elif file_path.endswith(('.txt', '.md')):
            result.update(self._process_text_file(file_path))
        elif file_path.endswith('.pdf'):
            result.update(self._process_pdf_file(file_path))
        
        # Gemini APIによる解析（利用可能な場合）
        if self.model and self.config.use_gemini_for_analysis:
            gemini_result = self._analyze_with_gemini(file_path, result)
            result.update(gemini_result)
        
        return result
    
    def _process_json_file(self, file_path: str) -> Dict[str, Any]:
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
                for key in ['title', 'name', 'dataset_name', '名前', 'タイトル']:
                    if key in data:
                        result['title'] = str(data[key])
                        break
                
                # 概要の抽出
                for key in ['description', 'summary', 'abstract', '説明', '概要']:
                    if key in data:
                        result['summary'] = str(data[key])[:500]  # 最大500文字
                        break
                
                # 研究分野の抽出
                for key in ['field', 'category', 'research_field', '分野', 'カテゴリー']:
                    if key in data:
                        result['research_field'] = str(data[key])
                        break
                
                # データセットの特徴抽出
                if 'data' in data and isinstance(data['data'], list):
                    sample_count = len(data['data'])
                    result['additional_metadata'] = {
                        'sample_count': sample_count,
                        'data_structure': 'list_of_records'
                    }
                    
                    # サンプルデータから特徴を抽出
                    if data['data'] and isinstance(data['data'][0], dict):
                        result['additional_metadata']['fields'] = list(data['data'][0].keys())
            
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
    
    def _process_text_file(self, file_path: str) -> Dict[str, Any]:
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
            
            else:
                # プレーンテキストの処理
                # 最初の非空行をタイトルとする
                for line in lines:
                    if line.strip():
                        result['title'] = line.strip()[:100]
                        break
                
                # 最初の数行を概要とする
                non_empty_lines = [line.strip() for line in lines if line.strip()]
                if len(non_empty_lines) > 1:
                    result['summary'] = ' '.join(non_empty_lines[1:4])[:500]
            
            # キーワード抽出による研究分野の推定
            result['research_field'] = self._infer_research_field_from_text(content)
            
            return result
            
        except Exception as e:
            return {
                'parse_error': str(e),
                'title': Path(file_path).stem
            }
    
    def _process_pdf_file(self, file_path: str) -> Dict[str, Any]:
        """
        PDFファイルを処理（基本情報のみ）
        
        Args:
            file_path: PDFファイルパス
        
        Returns:
            処理結果
        """
        # PDF処理ライブラリがない場合は基本情報のみ
        return {
            'title': Path(file_path).stem,
            'summary': 'PDFファイル（詳細解析にはPyPDF2等が必要）',
            'additional_metadata': {
                'file_type': 'pdf',
                'requires_ocr': True
            }
        }
    
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
            # ファイル内容の読み取り（最大10KB）
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(10240)  # 最大10KB
            
            # プロンプトの構築
            prompt = f"""
            以下のファイル内容を分析して、JSON形式で情報を抽出してください：
            
            ファイル名: {os.path.basename(file_path)}
            内容の一部:
            {content[:2000]}
            
            以下の情報を抽出してください：
            1. title: 適切なタイトル（ファイル内容から推定）
            2. summary: 100文字程度の要約
            3. research_field: 研究分野（機械学習、自然言語処理、データサイエンスなど）
            4. keywords: 主要なキーワード（最大5個）
            
            JSONフォーマットで回答してください。
            """
            
            # Gemini APIの呼び出し
            response = self.model.generate_content(prompt)
            
            # レスポンスの解析
            try:
                # JSON部分を抽出
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    gemini_data = json.loads(json_match.group())
                    
                    result = {}
                    
                    # 既存の結果がない場合のみGeminiの結果を使用
                    if not current_result.get('title'):
                        result['title'] = gemini_data.get('title')
                    
                    if not current_result.get('summary'):
                        result['summary'] = gemini_data.get('summary', '')
                    
                    if not current_result.get('research_field') or current_result.get('research_field') == '未分類':
                        result['research_field'] = gemini_data.get('research_field', '')
                    
                    # キーワードは追加メタデータとして保存
                    if 'keywords' in gemini_data:
                        result['additional_metadata'] = current_result.get('additional_metadata', {})
                        result['additional_metadata']['keywords'] = gemini_data['keywords']
                    
                    return result
            except:
                # JSON解析に失敗した場合は、テキストから直接抽出を試みる
                pass
            
            return {}
            
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