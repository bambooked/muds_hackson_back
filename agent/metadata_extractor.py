"""
メタデータ抽出モジュール
ファイルから研究データのメタデータを抽出
"""
import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
import mimetypes
from pathlib import Path


class MetadataExtractor:
    """ファイルからメタデータを抽出するクラス"""
    
    def __init__(self):
        """メタデータ抽出器の初期化"""
        # サポートするデータタイプのマッピング
        self.type_mapping = {
            'datasets': 'dataset',
            'paper': 'paper',
            'poster': 'poster'
        }
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        ファイルからメタデータを抽出
        
        Args:
            file_path: ファイルパス
        
        Returns:
            メタデータの辞書
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")
        
        # 基本メタデータの抽出
        metadata = self._extract_basic_metadata(file_path)
        
        # ファイルタイプ別の追加メタデータ
        if file_path.endswith('.json'):
            metadata.update(self._extract_json_metadata(file_path))
        elif file_path.endswith(('.txt', '.md')):
            metadata.update(self._extract_text_metadata(file_path))
        elif file_path.endswith('.pdf'):
            metadata.update(self._extract_pdf_metadata(file_path))
        
        # データタイプの推定
        metadata['data_type'] = self._infer_data_type(file_path)
        
        # データIDの生成
        metadata['data_id'] = self._generate_data_id(file_path)
        
        return metadata
    
    def _extract_basic_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        ファイルの基本メタデータを抽出
        
        Args:
            file_path: ファイルパス
        
        Returns:
            基本メタデータ
        """
        path = Path(file_path)
        stat = os.stat(file_path)
        
        return {
            'file_path': file_path,
            'file_name': path.name,
            'file_size': stat.st_size,
            'file_extension': path.suffix.lower(),
            'mime_type': mimetypes.guess_type(file_path)[0] or 'unknown',
            'created_date': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_date': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'parent_directory': path.parent.name
        }
    
    def _extract_json_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        JSONファイルからメタデータを抽出
        
        Args:
            file_path: JSONファイルパス
        
        Returns:
            追加メタデータ
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metadata = {}
            
            # よくあるフィールドの抽出
            if isinstance(data, dict):
                # タイトル候補
                for key in ['title', 'name', 'dataset_name', '名前', 'タイトル']:
                    if key in data:
                        metadata['title'] = str(data[key])
                        break
                
                # 説明候補
                for key in ['description', 'summary', 'abstract', '説明', '概要']:
                    if key in data:
                        metadata['summary'] = str(data[key])
                        break
                
                # 分野候補
                for key in ['field', 'category', 'research_field', '分野', 'カテゴリー']:
                    if key in data:
                        metadata['research_field'] = str(data[key])
                        break
                
                # その他の有用な情報
                metadata['json_keys'] = list(data.keys())[:10]  # 最初の10個のキー
                
                # データセットの場合のサンプル数
                if 'data' in data and isinstance(data['data'], list):
                    metadata['sample_count'] = len(data['data'])
            
            elif isinstance(data, list):
                metadata['sample_count'] = len(data)
                if data and isinstance(data[0], dict):
                    metadata['json_keys'] = list(data[0].keys())[:10]
            
            return metadata
            
        except Exception as e:
            return {'json_parse_error': str(e)}
    
    def _extract_text_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        テキストファイルからメタデータを抽出
        
        Args:
            file_path: テキストファイルパス
        
        Returns:
            追加メタデータ
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            metadata = {
                'line_count': len(lines),
                'character_count': len(content),
                'word_count': len(content.split())
            }
            
            # 最初の非空行をタイトル候補とする
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    metadata['first_line'] = line[:100]
                    break
            
            # Markdownの場合
            if file_path.endswith('.md'):
                # 最初の見出しをタイトルとして抽出
                for line in lines:
                    if line.startswith('# '):
                        metadata['title'] = line[2:].strip()
                        break
            
            return metadata
            
        except Exception as e:
            return {'text_parse_error': str(e)}
    
    def _extract_pdf_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        PDFファイルからメタデータを抽出（基本情報のみ）
        
        Args:
            file_path: PDFファイルパス
        
        Returns:
            追加メタデータ
        """
        # PDF処理ライブラリがない場合は基本情報のみ
        return {
            'pdf_file': True,
            'note': 'PDF詳細メタデータの抽出にはPyPDF2等が必要です'
        }
    
    def _infer_data_type(self, file_path: str) -> str:
        """
        ファイルパスからデータタイプを推定
        
        Args:
            file_path: ファイルパス
        
        Returns:
            データタイプ
        """
        path_parts = Path(file_path).parts
        
        for part in path_parts:
            if part in self.type_mapping:
                return self.type_mapping[part]
        
        # ファイル名からの推定
        file_name = os.path.basename(file_path).lower()
        if 'dataset' in file_name:
            return 'dataset'
        elif 'paper' in file_name:
            return 'paper'
        elif 'poster' in file_name:
            return 'poster'
        
        # 拡張子からの推定
        if file_path.endswith('.pdf'):
            return 'paper'
        elif file_path.endswith(('.png', '.jpg', '.jpeg')):
            return 'poster'
        
        return 'unknown'
    
    def _generate_data_id(self, file_path: str) -> str:
        """
        ファイルパスからユニークなデータIDを生成
        
        Args:
            file_path: ファイルパス
        
        Returns:
            データID
        """
        # ファイルパスのハッシュ値を使用
        hash_obj = hashlib.md5(file_path.encode())
        return hash_obj.hexdigest()[:12]
    
    def extract_from_directory(self, directory_path: str, 
                              recursive: bool = True) -> list[Dict[str, Any]]:
        """
        ディレクトリ内のすべてのファイルからメタデータを抽出
        
        Args:
            directory_path: ディレクトリパス
            recursive: サブディレクトリも処理するか
        
        Returns:
            メタデータのリスト
        """
        metadata_list = []
        
        if recursive:
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    if file.startswith('.'):
                        continue  # 隠しファイルはスキップ
                    
                    file_path = os.path.join(root, file)
                    try:
                        metadata = self.extract_metadata(file_path)
                        metadata_list.append(metadata)
                    except Exception as e:
                        print(f"メタデータ抽出エラー ({file_path}): {e}")
        else:
            for file in os.listdir(directory_path):
                if file.startswith('.'):
                    continue
                
                file_path = os.path.join(directory_path, file)
                if os.path.isfile(file_path):
                    try:
                        metadata = self.extract_metadata(file_path)
                        metadata_list.append(metadata)
                    except Exception as e:
                        print(f"メタデータ抽出エラー ({file_path}): {e}")
        
        return metadata_list