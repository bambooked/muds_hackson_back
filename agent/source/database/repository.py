from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from .connection import db_connection
from .models import File, ResearchTopic, AnalysisResult

logger = logging.getLogger(__name__)


class FileRepository:
    """ファイルテーブルのリポジトリ"""
    
    def __init__(self):
        self.db = db_connection
    
    def create(self, file: File) -> File:
        """ファイルを作成"""
        query = """
        INSERT INTO files (
            file_path, file_name, file_type, category, file_size,
            created_at, updated_at, indexed_at, summary, metadata, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            file.file_path, file.file_name, file.file_type, file.category,
            file.file_size, file.created_at, file.updated_at, file.indexed_at,
            file.summary, file.metadata, file.content_hash
        )
        
        cursor = self.db.execute_query(query, params)
        file.id = cursor.lastrowid
        logger.info(f"ファイルを登録しました: {file.file_name}")
        return file
    
    def find_by_id(self, file_id: int) -> Optional[File]:
        """IDでファイルを検索"""
        query = "SELECT * FROM files WHERE id = ?"
        row = self.db.fetch_one(query, (file_id,))
        return File.from_dict(dict(row)) if row else None
    
    def find_by_path(self, file_path: str) -> Optional[File]:
        """パスでファイルを検索"""
        query = "SELECT * FROM files WHERE file_path = ?"
        row = self.db.fetch_one(query, (file_path,))
        return File.from_dict(dict(row)) if row else None
    
    def find_all(self, category: Optional[str] = None, 
                 file_type: Optional[str] = None) -> List[File]:
        """条件に応じてファイルを検索"""
        query = "SELECT * FROM files WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if file_type:
            query += " AND file_type = ?"
            params.append(file_type)
        
        query += " ORDER BY indexed_at DESC"
        
        rows = self.db.fetch_all(query, tuple(params) if params else None)
        return [File.from_dict(dict(row)) for row in rows]
    
    def update(self, file: File) -> bool:
        """ファイルを更新"""
        query = """
        UPDATE files SET
            file_name = ?, file_type = ?, category = ?, file_size = ?,
            created_at = ?, updated_at = ?, summary = ?, metadata = ?, content_hash = ?
        WHERE id = ?
        """
        params = (
            file.file_name, file.file_type, file.category, file.file_size,
            file.created_at, file.updated_at, file.summary, file.metadata,
            file.content_hash, file.id
        )
        
        cursor = self.db.execute_query(query, params)
        success = cursor.rowcount > 0
        if success:
            logger.info(f"ファイルを更新しました: {file.file_name}")
        return success
    
    def delete(self, file_id: int) -> bool:
        """ファイルを削除"""
        query = "DELETE FROM files WHERE id = ?"
        cursor = self.db.execute_query(query, (file_id,))
        success = cursor.rowcount > 0
        if success:
            logger.info(f"ファイルを削除しました: ID={file_id}")
        return success
    
    def search(self, keyword: str) -> List[File]:
        """キーワードでファイルを検索"""
        query = """
        SELECT * FROM files 
        WHERE file_name LIKE ? OR summary LIKE ? OR metadata LIKE ?
        ORDER BY indexed_at DESC
        """
        keyword_pattern = f"%{keyword}%"
        params = (keyword_pattern, keyword_pattern, keyword_pattern)
        
        rows = self.db.fetch_all(query, params)
        return [File.from_dict(dict(row)) for row in rows]


class ResearchTopicRepository:
    """研究トピックテーブルのリポジトリ"""
    
    def __init__(self):
        self.db = db_connection
    
    def create(self, topic: ResearchTopic) -> ResearchTopic:
        """研究トピックを作成"""
        query = """
        INSERT INTO research_topics (file_id, topic, relevance_score, keywords)
        VALUES (?, ?, ?, ?)
        """
        params = (topic.file_id, topic.topic, topic.relevance_score, topic.keywords)
        
        cursor = self.db.execute_query(query, params)
        topic.id = cursor.lastrowid
        return topic
    
    def find_by_file_id(self, file_id: int) -> List[ResearchTopic]:
        """ファイルIDで研究トピックを検索"""
        query = "SELECT * FROM research_topics WHERE file_id = ? ORDER BY relevance_score DESC"
        rows = self.db.fetch_all(query, (file_id,))
        return [ResearchTopic.from_dict(dict(row)) for row in rows]
    
    def delete_by_file_id(self, file_id: int) -> bool:
        """ファイルIDで研究トピックを削除"""
        query = "DELETE FROM research_topics WHERE file_id = ?"
        cursor = self.db.execute_query(query, (file_id,))
        return cursor.rowcount > 0


class AnalysisResultRepository:
    """解析結果テーブルのリポジトリ"""
    
    def __init__(self):
        self.db = db_connection
    
    def create(self, result: AnalysisResult) -> AnalysisResult:
        """解析結果を作成"""
        query = """
        INSERT INTO analysis_results (file_id, analysis_type, result_data, created_at)
        VALUES (?, ?, ?, ?)
        """
        params = (result.file_id, result.analysis_type, result.result_data, result.created_at)
        
        cursor = self.db.execute_query(query, params)
        result.id = cursor.lastrowid
        return result
    
    def find_by_file_id(self, file_id: int, 
                       analysis_type: Optional[str] = None) -> List[AnalysisResult]:
        """ファイルIDで解析結果を検索"""
        query = "SELECT * FROM analysis_results WHERE file_id = ?"
        params = [file_id]
        
        if analysis_type:
            query += " AND analysis_type = ?"
            params.append(analysis_type)
        
        query += " ORDER BY created_at DESC"
        
        rows = self.db.fetch_all(query, tuple(params))
        return [AnalysisResult.from_dict(dict(row)) for row in rows]
    
    def find_latest_by_file_id(self, file_id: int, 
                              analysis_type: str) -> Optional[AnalysisResult]:
        """最新の解析結果を取得"""
        query = """
        SELECT * FROM analysis_results 
        WHERE file_id = ? AND analysis_type = ?
        ORDER BY created_at DESC
        LIMIT 1
        """
        row = self.db.fetch_one(query, (file_id, analysis_type))
        return AnalysisResult.from_dict(dict(row)) if row else None