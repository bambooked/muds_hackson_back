import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import logging

from config import DATA_DIR, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE_BYTES
from ..database.models import File

logger = logging.getLogger(__name__)


class FileScanner:
    """データディレクトリのファイルをスキャンするクラス"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DATA_DIR
        self.supported_extensions = SUPPORTED_EXTENSIONS
    
    def scan_directory(self) -> List[File]:
        """データディレクトリを再帰的にスキャンしてデータセット単位で管理"""
        files = []
        
        if not self.data_dir.exists():
            logger.error(f"データディレクトリが存在しません: {self.data_dir}")
            return files
        
        logger.info(f"ディレクトリをスキャン中: {self.data_dir}")
        
        # データセット単位でスキャン
        datasets_discovered = set()
        
        for root, _, filenames in os.walk(self.data_dir):
            for filename in filenames:
                file_path = Path(root) / filename
                
                if self._should_process_file(file_path):
                    file_obj = self._create_file_object(file_path)
                    if file_obj:
                        files.append(file_obj)
                        
                        # データセット名を記録
                        if file_obj.category == "datasets":
                            dataset_name = self._get_dataset_name(file_path)
                            if dataset_name:
                                datasets_discovered.add(dataset_name)
        
        logger.info(f"スキャン完了: {len(files)}個のファイルを発見")
        logger.info(f"データセット: {len(datasets_discovered)}個 ({', '.join(sorted(datasets_discovered))})")
        return files
    
    def _should_process_file(self, file_path: Path) -> bool:
        """ファイルを処理すべきか判定"""
        # 隠しファイルをスキップ
        if file_path.name.startswith('.'):
            return False
        
        # サポートされている拡張子か確認
        if file_path.suffix.lower() not in self.supported_extensions:
            return False
        
        # ファイルサイズの確認
        try:
            file_size = file_path.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                logger.warning(f"ファイルサイズが大きすぎます: {file_path} ({file_size} bytes)")
                return False
        except Exception as e:
            logger.error(f"ファイル情報の取得に失敗: {file_path}, エラー: {e}")
            return False
        
        return True
    
    def _create_file_object(self, file_path: Path) -> Optional[File]:
        """ファイルオブジェクトを作成"""
        try:
            stat = file_path.stat()
            
            # カテゴリーを判定
            category = self._determine_category(file_path)
            
            # ファイルハッシュを計算
            content_hash = self._calculate_file_hash(file_path)
            
            file_obj = File(
                file_path=str(file_path.absolute()),
                file_name=file_path.name,
                file_type=file_path.suffix.lower()[1:],  # 拡張子（.を除く）
                category=category,
                file_size=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                updated_at=datetime.fromtimestamp(stat.st_mtime),
                indexed_at=datetime.now(),
                content_hash=content_hash
            )
            
            return file_obj
            
        except Exception as e:
            logger.error(f"ファイルオブジェクトの作成に失敗: {file_path}, エラー: {e}")
            return None
    
    def _determine_category(self, file_path: Path) -> str:
        """ファイルのカテゴリーを判定"""
        # パスからカテゴリーを推測
        path_parts = file_path.parts
        
        for part in path_parts:
            if part.lower() in ['paper', 'papers']:
                return 'paper'
            elif part.lower() in ['poster', 'posters']:
                return 'poster'
            elif part.lower() in ['dataset', 'datasets']:
                return 'datasets'
        
        # デフォルトはファイルタイプから推測
        if file_path.suffix.lower() == '.pdf':
            # PDFファイルはファイル名から推測
            if 'poster' in file_path.name.lower():
                return 'poster'
            else:
                return 'paper'
        else:
            return 'datasets'
    
    def _get_dataset_name(self, file_path: Path) -> Optional[str]:
        """ファイルパスからデータセット名を取得"""
        path_parts = file_path.parts
        
        # data/datasets/[dataset_name]/file.ext の構造を想定
        try:
            data_index = path_parts.index('data')
            datasets_index = path_parts.index('datasets', data_index)
            
            if datasets_index + 1 < len(path_parts):
                return path_parts[datasets_index + 1]
        except (ValueError, IndexError):
            pass
        
        return None
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """ファイルのSHA256ハッシュを計算"""
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"ファイルハッシュの計算に失敗: {file_path}, エラー: {e}")
            return ""
    
    def check_file_modified(self, file_obj: File) -> bool:
        """ファイルが変更されているか確認"""
        file_path = Path(file_obj.file_path)
        
        if not file_path.exists():
            return False
        
        try:
            stat = file_path.stat()
            current_mtime = datetime.fromtimestamp(stat.st_mtime)
            
            # 更新時刻が異なるか、ハッシュが異なる場合は変更されている
            if file_obj.updated_at != current_mtime:
                return True
            
            current_hash = self._calculate_file_hash(file_path)
            if file_obj.content_hash != current_hash:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"ファイル変更チェックに失敗: {file_path}, エラー: {e}")
            return False