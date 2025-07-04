from typing import List, Dict, Any, Optional
from pathlib import Path
import shutil
import logging

from ..database.models import File
from ..database.repository import FileRepository, ResearchTopicRepository, AnalysisResultRepository
from ..indexer.indexer import FileIndexer

logger = logging.getLogger(__name__)


class DataManager:
    """データの管理を行うクラス"""
    
    def __init__(self):
        self.file_repo = FileRepository()
        self.topic_repo = ResearchTopicRepository()
        self.analysis_repo = AnalysisResultRepository()
        self.indexer = FileIndexer()
    
    def search_files(self, keyword: str = None, category: str = None, 
                    file_type: str = None) -> List[Dict[str, Any]]:
        """ファイルを検索"""
        if keyword:
            files = self.file_repo.search(keyword)
        else:
            files = self.file_repo.find_all(category=category, file_type=file_type)
        
        results = []
        for file in files:
            file_info = file.to_dict()
            
            # 関連するトピックを追加
            topics = self.topic_repo.find_by_file_id(file.id)
            file_info["topics"] = [topic.to_dict() for topic in topics]
            
            results.append(file_info)
        
        return results
    
    def get_file_details(self, file_id: int) -> Optional[Dict[str, Any]]:
        """ファイルの詳細情報を取得"""
        file = self.file_repo.find_by_id(file_id)
        if not file:
            return None
        
        details = file.to_dict()
        
        # トピック情報を追加
        topics = self.topic_repo.find_by_file_id(file_id)
        details["topics"] = [topic.to_dict() for topic in topics]
        
        # 解析結果を追加
        analysis_results = self.analysis_repo.find_by_file_id(file_id)
        details["analysis_results"] = [
            {
                "type": result.analysis_type,
                "created_at": result.created_at.isoformat() if result.created_at else None
            }
            for result in analysis_results
        ]
        
        # ファイルの実在確認
        file_path = Path(file.file_path)
        details["file_exists"] = file_path.exists()
        
        return details
    
    def update_file_metadata(self, file_id: int, metadata: Dict[str, Any]) -> bool:
        """ファイルのメタデータを更新"""
        file = self.file_repo.find_by_id(file_id)
        if not file:
            logger.error(f"ファイルが見つかりません: ID={file_id}")
            return False
        
        # メタデータを更新
        if file.metadata:
            file.metadata.update(metadata)
        else:
            file.metadata = metadata
        
        return self.file_repo.update(file)
    
    def register_new_file(self, file_path: str, category: str = None) -> Optional[int]:
        """新規ファイルを登録"""
        path = Path(file_path)
        
        if not path.exists():
            logger.error(f"ファイルが存在しません: {file_path}")
            return None
        
        # 既存チェック
        existing = self.file_repo.find_by_path(str(path.absolute()))
        if existing:
            logger.warning(f"ファイルは既に登録されています: {file_path}")
            return existing.id
        
        # インデックスに追加
        success = self.indexer.index_single_file(str(path.absolute()))
        if not success:
            return None
        
        # 登録されたファイルを取得
        registered = self.file_repo.find_by_path(str(path.absolute()))
        if registered:
            # カテゴリーを更新（指定された場合）
            if category:
                registered.category = category
                self.file_repo.update(registered)
            
            return registered.id
        
        return None
    
    def delete_file(self, file_id: int, delete_physical: bool = False) -> bool:
        """ファイルを削除"""
        file = self.file_repo.find_by_id(file_id)
        if not file:
            logger.error(f"ファイルが見つかりません: ID={file_id}")
            return False
        
        # 物理ファイルの削除（オプション）
        if delete_physical:
            file_path = Path(file.file_path)
            if file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(f"物理ファイルを削除: {file_path}")
                except Exception as e:
                    logger.error(f"物理ファイル削除エラー: {file_path}, {e}")
                    return False
        
        # データベースから削除
        return self.file_repo.delete(file_id)
    
    def move_file(self, file_id: int, new_directory: str) -> bool:
        """ファイルを移動"""
        file = self.file_repo.find_by_id(file_id)
        if not file:
            logger.error(f"ファイルが見つかりません: ID={file_id}")
            return False
        
        old_path = Path(file.file_path)
        new_dir = Path(new_directory)
        
        if not old_path.exists():
            logger.error(f"移動元ファイルが存在しません: {old_path}")
            return False
        
        if not new_dir.exists():
            logger.error(f"移動先ディレクトリが存在しません: {new_dir}")
            return False
        
        # 新しいパスを作成
        new_path = new_dir / old_path.name
        
        try:
            # ファイルを移動
            shutil.move(str(old_path), str(new_path))
            
            # データベースを更新
            file.file_path = str(new_path.absolute())
            self.file_repo.update(file)
            
            logger.info(f"ファイルを移動: {old_path} -> {new_path}")
            return True
            
        except Exception as e:
            logger.error(f"ファイル移動エラー: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return self.indexer.get_index_status()
    
    def refresh_index(self) -> Dict[str, Any]:
        """インデックスを更新"""
        return self.indexer.index_all_files()
    
    def export_file_list(self, format: str = "json") -> str:
        """ファイルリストをエクスポート"""
        files = self.file_repo.find_all()
        
        if format == "json":
            import json
            data = [file.to_dict() for file in files]
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        elif format == "csv":
            import csv
            from io import StringIO
            
            output = StringIO()
            if files:
                fieldnames = ["id", "file_name", "file_path", "category", 
                            "file_type", "file_size", "summary", "indexed_at"]
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for file in files:
                    row = {
                        "id": file.id,
                        "file_name": file.file_name,
                        "file_path": file.file_path,
                        "category": file.category,
                        "file_type": file.file_type,
                        "file_size": file.file_size,
                        "summary": file.summary or "",
                        "indexed_at": file.indexed_at.isoformat() if file.indexed_at else ""
                    }
                    writer.writerow(row)
            
            return output.getvalue()
        
        else:
            raise ValueError(f"未対応のフォーマット: {format}")