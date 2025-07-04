from typing import List, Dict, Any
import logging
from pathlib import Path

from .scanner import FileScanner
from ..database.repository import FileRepository
from ..database.models import File

logger = logging.getLogger(__name__)


class FileIndexer:
    """ファイルインデックスを管理するクラス"""
    
    def __init__(self, auto_analyze: bool = True):
        self.scanner = FileScanner()
        self.file_repo = FileRepository()
        self.auto_analyze = auto_analyze
        
        # 循環インポートを避けるため、必要時に動的インポート
        self._analyzer = None
    
    @property
    def analyzer(self):
        """アナライザーの遅延初期化"""
        if self._analyzer is None and self.auto_analyze:
            try:
                from ..analyzer.file_analyzer import FileAnalyzer
                self._analyzer = FileAnalyzer()
            except ImportError as e:
                logger.warning(f"アナライザーのインポートに失敗: {e}")
                self.auto_analyze = False
        return self._analyzer
    
    def index_all_files(self) -> Dict[str, Any]:
        """全ファイルをインデックス化"""
        logger.info("ファイルのインデックス化を開始します")
        
        # ディレクトリをスキャン
        scanned_files = self.scanner.scan_directory()
        
        # 既存のファイル情報を取得
        existing_files = self.file_repo.find_all()
        existing_paths = {f.file_path: f for f in existing_files}
        
        results = {
            "new_files": 0,
            "updated_files": 0,
            "deleted_files": 0,
            "errors": 0,
            "details": []
        }
        
        # スキャンしたファイルを処理
        scanned_paths = set()
        for file_obj in scanned_files:
            scanned_paths.add(file_obj.file_path)
            
            if file_obj.file_path in existing_paths:
                # 既存ファイルの更新チェック
                existing_file = existing_paths[file_obj.file_path]
                if self.scanner.check_file_modified(existing_file):
                    if self._update_file(existing_file, file_obj):
                        results["updated_files"] += 1
                        results["details"].append({
                            "action": "updated",
                            "file": file_obj.file_name
                        })
                    else:
                        results["errors"] += 1
            else:
                # 新規ファイルの登録
                if self._register_new_file(file_obj):
                    results["new_files"] += 1
                    results["details"].append({
                        "action": "added",
                        "file": file_obj.file_name
                    })
                else:
                    results["errors"] += 1
        
        # 削除されたファイルの処理
        for existing_path, existing_file in existing_paths.items():
            if existing_path not in scanned_paths:
                if self.file_repo.delete(existing_file.id):
                    results["deleted_files"] += 1
                    results["details"].append({
                        "action": "deleted",
                        "file": existing_file.file_name
                    })
                else:
                    results["errors"] += 1
        
        logger.info(
            f"インデックス化完了: "
            f"新規={results['new_files']}, "
            f"更新={results['updated_files']}, "
            f"削除={results['deleted_files']}, "
            f"エラー={results['errors']}"
        )
        
        return results
    
    def index_single_file(self, file_path: str) -> bool:
        """単一ファイルをインデックス化"""
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"ファイルが存在しません: {file_path}")
            return False
        
        # ファイルオブジェクトを作成
        file_obj = self.scanner._create_file_object(path)
        if not file_obj:
            return False
        
        # 既存チェック
        existing_file = self.file_repo.find_by_path(file_path)
        
        if existing_file:
            # 更新
            return self._update_file(existing_file, file_obj)
        else:
            # 新規登録
            return self._register_new_file(file_obj)
    
    def _register_new_file(self, file_obj: File) -> bool:
        """新規ファイルを登録し、自動解析を実行"""
        try:
            created_file = self.file_repo.create(file_obj)
            logger.info(f"新規ファイルを登録: {file_obj.file_name}")
            
            # 自動解析を実行
            if self.auto_analyze and self.analyzer and created_file.id:
                try:
                    logger.info(f"自動解析を開始: {file_obj.file_name}")
                    self.analyzer.analyze_file(created_file.id, force=False)
                except Exception as e:
                    logger.warning(f"自動解析に失敗: {file_obj.file_name}, {e}")
            
            return True
        except Exception as e:
            logger.error(f"ファイル登録エラー: {file_obj.file_name}, {e}")
            return False
    
    def _update_file(self, existing_file: File, new_file: File) -> bool:
        """既存ファイルを更新し、必要に応じて再解析を実行"""
        try:
            # IDを引き継ぐ
            new_file.id = existing_file.id
            # インデックス時刻は既存のものを保持
            new_file.indexed_at = existing_file.indexed_at
            
            self.file_repo.update(new_file)
            logger.info(f"ファイルを更新: {new_file.file_name}")
            
            # ファイルが変更された場合は再解析
            if self.auto_analyze and self.analyzer and new_file.id:
                try:
                    logger.info(f"ファイル変更により再解析を開始: {new_file.file_name}")
                    self.analyzer.analyze_file(new_file.id, force=True)
                except Exception as e:
                    logger.warning(f"再解析に失敗: {new_file.file_name}, {e}")
            
            return True
        except Exception as e:
            logger.error(f"ファイル更新エラー: {new_file.file_name}, {e}")
            return False
    
    def get_index_status(self) -> Dict[str, Any]:
        """インデックスの状態を取得（データセット単位を含む）"""
        all_files = self.file_repo.find_all()
        
        status = {
            "total_files": len(all_files),
            "by_category": {},
            "by_type": {},
            "datasets": {},
            "total_size": 0
        }
        
        for file in all_files:
            # カテゴリー別集計
            if file.category not in status["by_category"]:
                status["by_category"][file.category] = 0
            status["by_category"][file.category] += 1
            
            # タイプ別集計
            if file.file_type not in status["by_type"]:
                status["by_type"][file.file_type] = 0
            status["by_type"][file.file_type] += 1
            
            # データセット別集計
            if file.category == "datasets":
                dataset_name = self.scanner._get_dataset_name(Path(file.file_path))
                if dataset_name:
                    if dataset_name not in status["datasets"]:
                        status["datasets"][dataset_name] = {"files": 0, "size": 0}
                    status["datasets"][dataset_name]["files"] += 1
                    status["datasets"][dataset_name]["size"] += file.file_size
            
            # 合計サイズ
            status["total_size"] += file.file_size
        
        # サイズを人間が読みやすい形式に変換
        status["total_size_mb"] = round(status["total_size"] / (1024 * 1024), 2)
        
        # データセット数を追加
        status["total_datasets"] = len(status["datasets"])
        
        return status