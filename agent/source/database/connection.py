import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator
import logging

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """データベース接続を管理するクラス"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DATABASE_PATH
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """データベースファイルが存在することを確認"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"データベースパス: {self.db_path}")
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """データベース接続を取得するコンテキストマネージャー"""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"データベースエラー: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def initialize_database(self):
        """データベースを初期化（カテゴリー別テーブル作成）"""
        create_tables_sql = """
        -- datasets テーブル（データセット単位で管理）
        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            file_count INTEGER DEFAULT 0,
            total_size INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            summary TEXT
        );

        -- papers テーブル（論文）
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_name TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            title TEXT,
            authors TEXT,
            abstract TEXT,
            keywords TEXT,
            content_hash TEXT
        );

        -- posters テーブル（ポスター）
        CREATE TABLE IF NOT EXISTS posters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_name TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            title TEXT,
            authors TEXT,
            abstract TEXT,
            keywords TEXT,
            content_hash TEXT
        );

        -- dataset_files テーブル（データセット内のファイル）
        CREATE TABLE IF NOT EXISTS dataset_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER NOT NULL,
            file_path TEXT UNIQUE NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content_hash TEXT,
            FOREIGN KEY (dataset_id) REFERENCES datasets (id) ON DELETE CASCADE
        );
        
        -- インデックス作成
        CREATE INDEX IF NOT EXISTS idx_datasets_name ON datasets(name);
        CREATE INDEX IF NOT EXISTS idx_papers_file_name ON papers(file_name);
        CREATE INDEX IF NOT EXISTS idx_posters_file_name ON posters(file_name);
        CREATE INDEX IF NOT EXISTS idx_dataset_files_dataset_id ON dataset_files(dataset_id);
        """
        
        with self.get_connection() as conn:
            conn.executescript(create_tables_sql)
            logger.info("データベースの初期化が完了しました")
    
    def execute_query(self, query: str, params: Optional[tuple] = None):
        """単一のクエリを実行"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
    
    def execute_many(self, query: str, params_list: list):
        """複数のパラメータで同じクエリを実行"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            return cursor
    
    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[sqlite3.Row]:
        """1行を取得"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchone()
    
    def fetch_all(self, query: str, params: Optional[tuple] = None) -> list:
        """全行を取得"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()


# シングルトンインスタンス
db_connection = DatabaseConnection()