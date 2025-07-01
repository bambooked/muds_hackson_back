from typing import List, Optional
from datetime import datetime
import logging

from .connection import db_connection
from .new_models import Dataset, Paper, Poster, DatasetFile

logger = logging.getLogger(__name__)


class DatasetRepository:
    """データセットテーブルのリポジトリ"""
    
    def __init__(self):
        self.db = db_connection
    
    def create(self, dataset: Dataset) -> Dataset:
        """データセットを作成"""
        query = """
        INSERT INTO datasets (name, description, file_count, total_size, summary)
        VALUES (?, ?, ?, ?, ?)
        """
        params = (dataset.name, dataset.description, dataset.file_count, 
                 dataset.total_size, dataset.summary)
        
        cursor = self.db.execute_query(query, params)
        dataset.id = cursor.lastrowid
        logger.info(f"データセットを登録: {dataset.name}")
        return dataset
    
    def find_by_id(self, dataset_id: int) -> Optional[Dataset]:
        """IDでデータセットを検索"""
        query = "SELECT * FROM datasets WHERE id = ?"
        row = self.db.fetch_one(query, (dataset_id,))
        return Dataset.from_dict(dict(row)) if row else None
    
    def find_by_name(self, name: str) -> Optional[Dataset]:
        """名前でデータセットを検索"""
        query = "SELECT * FROM datasets WHERE name = ?"
        row = self.db.fetch_one(query, (name,))
        return Dataset.from_dict(dict(row)) if row else None
    
    def find_all(self) -> List[Dataset]:
        """全データセットを取得"""
        query = "SELECT * FROM datasets ORDER BY created_at DESC"
        rows = self.db.fetch_all(query)
        return [Dataset.from_dict(dict(row)) for row in rows]
    
    def update(self, dataset: Dataset) -> bool:
        """データセットを更新"""
        query = """
        UPDATE datasets SET
            description = ?, file_count = ?, total_size = ?, 
            summary = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """
        params = (dataset.description, dataset.file_count, dataset.total_size,
                 dataset.summary, dataset.id)
        
        cursor = self.db.execute_query(query, params)
        success = cursor.rowcount > 0
        if success:
            logger.info(f"データセットを更新: {dataset.name}")
        return success
    
    def delete(self, dataset_id: int) -> bool:
        """データセットを削除"""
        query = "DELETE FROM datasets WHERE id = ?"
        cursor = self.db.execute_query(query, (dataset_id,))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"データセットを削除: ID={dataset_id}")
        return success


class PaperRepository:
    """論文テーブルのリポジトリ"""
    
    def __init__(self):
        self.db = db_connection
    
    def create(self, paper: Paper) -> Paper:
        """論文を作成"""
        query = """
        INSERT INTO papers (
            file_path, file_name, file_size, created_at, updated_at,
            title, authors, abstract, keywords, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (paper.file_path, paper.file_name, paper.file_size,
                 paper.created_at, paper.updated_at, paper.title,
                 paper.authors, paper.abstract, paper.keywords, paper.content_hash)
        
        cursor = self.db.execute_query(query, params)
        paper.id = cursor.lastrowid
        logger.info(f"論文を登録: {paper.file_name}")
        return paper
    
    def find_by_id(self, paper_id: int) -> Optional[Paper]:
        """IDで論文を検索"""
        query = "SELECT * FROM papers WHERE id = ?"
        row = self.db.fetch_one(query, (paper_id,))
        return Paper.from_dict(dict(row)) if row else None
    
    def find_by_path(self, file_path: str) -> Optional[Paper]:
        """パスで論文を検索"""
        query = "SELECT * FROM papers WHERE file_path = ?"
        row = self.db.fetch_one(query, (file_path,))
        return Paper.from_dict(dict(row)) if row else None
    
    def find_all(self) -> List[Paper]:
        """全論文を取得"""
        query = "SELECT * FROM papers ORDER BY indexed_at DESC"
        rows = self.db.fetch_all(query)
        return [Paper.from_dict(dict(row)) for row in rows]
    
    def update(self, paper: Paper) -> bool:
        """論文を更新"""
        query = """
        UPDATE papers SET
            file_name = ?, file_size = ?, updated_at = ?, title = ?,
            authors = ?, abstract = ?, keywords = ?, content_hash = ?
        WHERE id = ?
        """
        params = (paper.file_name, paper.file_size, paper.updated_at,
                 paper.title, paper.authors, paper.abstract, paper.keywords,
                 paper.content_hash, paper.id)
        
        cursor = self.db.execute_query(query, params)
        success = cursor.rowcount > 0
        if success:
            logger.info(f"論文を更新: {paper.file_name}")
        return success
    
    def search(self, keyword: str) -> List[Paper]:
        """キーワードで論文を検索"""
        query = """
        SELECT * FROM papers 
        WHERE file_name LIKE ? OR title LIKE ? OR abstract LIKE ? OR keywords LIKE ?
        ORDER BY indexed_at DESC
        """
        keyword_pattern = f"%{keyword}%"
        params = (keyword_pattern, keyword_pattern, keyword_pattern, keyword_pattern)
        
        rows = self.db.fetch_all(query, params)
        return [Paper.from_dict(dict(row)) for row in rows]


class PosterRepository:
    """ポスターテーブルのリポジトリ"""
    
    def __init__(self):
        self.db = db_connection
    
    def create(self, poster: Poster) -> Poster:
        """ポスターを作成"""
        query = """
        INSERT INTO posters (
            file_path, file_name, file_size, created_at, updated_at,
            title, authors, abstract, keywords, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (poster.file_path, poster.file_name, poster.file_size,
                 poster.created_at, poster.updated_at, poster.title,
                 poster.authors, poster.abstract, poster.keywords, poster.content_hash)
        
        cursor = self.db.execute_query(query, params)
        poster.id = cursor.lastrowid
        logger.info(f"ポスターを登録: {poster.file_name}")
        return poster
    
    def find_by_id(self, poster_id: int) -> Optional[Poster]:
        """IDでポスターを検索"""
        query = "SELECT * FROM posters WHERE id = ?"
        row = self.db.fetch_one(query, (poster_id,))
        return Poster.from_dict(dict(row)) if row else None
    
    def find_by_path(self, file_path: str) -> Optional[Poster]:
        """パスでポスターを検索"""
        query = "SELECT * FROM posters WHERE file_path = ?"
        row = self.db.fetch_one(query, (file_path,))
        return Poster.from_dict(dict(row)) if row else None
    
    def find_all(self) -> List[Poster]:
        """全ポスターを取得"""
        query = "SELECT * FROM posters ORDER BY indexed_at DESC"
        rows = self.db.fetch_all(query)
        return [Poster.from_dict(dict(row)) for row in rows]
    
    def update(self, poster: Poster) -> bool:
        """ポスターを更新"""
        query = """
        UPDATE posters SET
            file_name = ?, file_size = ?, updated_at = ?, title = ?,
            authors = ?, abstract = ?, keywords = ?, content_hash = ?
        WHERE id = ?
        """
        params = (poster.file_name, poster.file_size, poster.updated_at,
                 poster.title, poster.authors, poster.abstract, poster.keywords,
                 poster.content_hash, poster.id)
        
        cursor = self.db.execute_query(query, params)
        success = cursor.rowcount > 0
        if success:
            logger.info(f"ポスターを更新: {poster.file_name}")
        return success
    
    def search(self, keyword: str) -> List[Poster]:
        """キーワードでポスターを検索"""
        query = """
        SELECT * FROM posters 
        WHERE file_name LIKE ? OR title LIKE ? OR abstract LIKE ? OR keywords LIKE ?
        ORDER BY indexed_at DESC
        """
        keyword_pattern = f"%{keyword}%"
        params = (keyword_pattern, keyword_pattern, keyword_pattern, keyword_pattern)
        
        rows = self.db.fetch_all(query, params)
        return [Poster.from_dict(dict(row)) for row in rows]


class DatasetFileRepository:
    """データセットファイルテーブルのリポジトリ"""
    
    def __init__(self):
        self.db = db_connection
    
    def create(self, dataset_file: DatasetFile) -> DatasetFile:
        """データセットファイルを作成"""
        query = """
        INSERT INTO dataset_files (
            dataset_id, file_path, file_name, file_type, file_size,
            created_at, updated_at, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (dataset_file.dataset_id, dataset_file.file_path, dataset_file.file_name,
                 dataset_file.file_type, dataset_file.file_size, dataset_file.created_at,
                 dataset_file.updated_at, dataset_file.content_hash)
        
        cursor = self.db.execute_query(query, params)
        dataset_file.id = cursor.lastrowid
        logger.info(f"データセットファイルを登録: {dataset_file.file_name}")
        return dataset_file
    
    def find_by_dataset_id(self, dataset_id: int) -> List[DatasetFile]:
        """データセットIDでファイルを検索"""
        query = "SELECT * FROM dataset_files WHERE dataset_id = ? ORDER BY indexed_at DESC"
        rows = self.db.fetch_all(query, (dataset_id,))
        return [DatasetFile.from_dict(dict(row)) for row in rows]
    
    def find_by_path(self, file_path: str) -> Optional[DatasetFile]:
        """パスでファイルを検索"""
        query = "SELECT * FROM dataset_files WHERE file_path = ?"
        row = self.db.fetch_one(query, (file_path,))
        return DatasetFile.from_dict(dict(row)) if row else None
    
    def delete_by_dataset_id(self, dataset_id: int) -> bool:
        """データセットIDでファイルを削除"""
        query = "DELETE FROM dataset_files WHERE dataset_id = ?"
        cursor = self.db.execute_query(query, (dataset_id,))
        return cursor.rowcount > 0