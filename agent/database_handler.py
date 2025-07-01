"""
データベース操作を管理するモジュール
SQLiteを使用してローカルデータベースを管理
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager


class DatabaseHandler:
    """研究データ基盤のデータベース操作を管理するクラス"""
    
    def __init__(self, db_path: str = "agent/database/research_data.db"):
        """
        データベースハンドラの初期化
        
        Args:
            db_path: データベースファイルのパス
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """データベース接続のコンテキストマネージャ"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        """データベースの初期化とテーブル作成"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 研究データテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS research_data (
                    data_id TEXT PRIMARY KEY,
                    data_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT,
                    research_field TEXT,
                    created_date TEXT,
                    file_path TEXT,
                    metadata TEXT,
                    indexed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 全文検索用のインデックス
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_title ON research_data(title)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_research_field ON research_data(research_field)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_data_type ON research_data(data_type)
            """)
            
            # 検索履歴テーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def insert_data(self, data: Dict[str, Any]) -> bool:
        """
        研究データをデータベースに挿入
        
        Args:
            data: 挿入するデータ
        
        Returns:
            挿入成功の可否
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # メタデータをJSON文字列に変換
                metadata_str = json.dumps(data.get('metadata', {}), ensure_ascii=False)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO research_data 
                    (data_id, data_type, title, summary, research_field, 
                     created_date, file_path, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data['data_id'],
                    data['data_type'],
                    data['title'],
                    data.get('summary', ''),
                    data.get('research_field', ''),
                    data.get('created_date', datetime.now().isoformat()),
                    data.get('file_path', ''),
                    metadata_str,
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"データ挿入エラー: {e}")
            return False
    
    def search_data(self, 
                   keyword: Optional[str] = None,
                   data_type: Optional[str] = None,
                   research_field: Optional[str] = None,
                   limit: int = 50) -> List[Dict[str, Any]]:
        """
        データを検索
        
        Args:
            keyword: 検索キーワード
            data_type: データタイプ
            research_field: 研究分野
            limit: 取得件数の上限
        
        Returns:
            検索結果のリスト
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # クエリ構築
            query = "SELECT * FROM research_data WHERE 1=1"
            params = []
            
            if keyword:
                query += " AND (title LIKE ? OR summary LIKE ? OR research_field LIKE ?)"
                keyword_pattern = f"%{keyword}%"
                params.extend([keyword_pattern, keyword_pattern, keyword_pattern])
            
            if data_type:
                query += " AND data_type = ?"
                params.append(data_type)
            
            if research_field:
                query += " AND research_field LIKE ?"
                params.append(f"%{research_field}%")
            
            query += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            # 検索履歴を記録
            if keyword:
                self._record_search_history(keyword)
            
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                # メタデータをJSONからパース
                if data.get('metadata'):
                    data['metadata'] = json.loads(data['metadata'])
                results.append(data)
            
            return results
    
    def get_data_by_id(self, data_id: str) -> Optional[Dict[str, Any]]:
        """
        IDでデータを取得
        
        Args:
            data_id: データID
        
        Returns:
            データ辞書またはNone
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM research_data WHERE data_id = ?", (data_id,))
            row = cursor.fetchone()
            
            if row:
                data = dict(row)
                if data.get('metadata'):
                    data['metadata'] = json.loads(data['metadata'])
                return data
            return None
    
    def update_data(self, data_id: str, updates: Dict[str, Any]) -> bool:
        """
        データを更新
        
        Args:
            data_id: データID
            updates: 更新するフィールド
        
        Returns:
            更新成功の可否
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 更新可能なフィールドのみ抽出
                allowed_fields = ['title', 'summary', 'research_field', 'metadata']
                update_fields = []
                values = []
                
                for field, value in updates.items():
                    if field in allowed_fields:
                        update_fields.append(f"{field} = ?")
                        if field == 'metadata':
                            values.append(json.dumps(value, ensure_ascii=False))
                        else:
                            values.append(value)
                
                if not update_fields:
                    return False
                
                # updated_atを追加
                update_fields.append("updated_at = ?")
                values.append(datetime.now().isoformat())
                values.append(data_id)
                
                query = f"UPDATE research_data SET {', '.join(update_fields)} WHERE data_id = ?"
                cursor.execute(query, values)
                conn.commit()
                
                return cursor.rowcount > 0
        except Exception as e:
            print(f"データ更新エラー: {e}")
            return False
    
    def delete_data(self, data_id: str) -> bool:
        """
        データを削除
        
        Args:
            data_id: データID
        
        Returns:
            削除成功の可否
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM research_data WHERE data_id = ?", (data_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"データ削除エラー: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        データベース統計を取得
        
        Returns:
            統計情報の辞書
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 全データ数
            cursor.execute("SELECT COUNT(*) as total FROM research_data")
            total_count = cursor.fetchone()['total']
            
            # データタイプ別の数
            cursor.execute("""
                SELECT data_type, COUNT(*) as count 
                FROM research_data 
                GROUP BY data_type
            """)
            type_counts = {row['data_type']: row['count'] for row in cursor.fetchall()}
            
            # 研究分野別の数
            cursor.execute("""
                SELECT research_field, COUNT(*) as count 
                FROM research_data 
                WHERE research_field IS NOT NULL AND research_field != ''
                GROUP BY research_field
                ORDER BY count DESC
                LIMIT 10
            """)
            field_counts = {row['research_field']: row['count'] for row in cursor.fetchall()}
            
            # 最近の更新
            cursor.execute("""
                SELECT data_id, title, updated_at 
                FROM research_data 
                ORDER BY updated_at DESC 
                LIMIT 5
            """)
            recent_updates = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_count': total_count,
                'type_counts': type_counts,
                'field_counts': field_counts,
                'recent_updates': recent_updates
            }
    
    def _record_search_history(self, query: str):
        """検索履歴を記録"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO search_history (query) VALUES (?)", (query,))
                conn.commit()
        except:
            pass  # 履歴記録の失敗は無視
    
    def get_search_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """
        最近の検索履歴を取得
        
        Args:
            limit: 取得件数
        
        Returns:
            検索履歴のリスト
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT query, timestamp 
                FROM search_history 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]