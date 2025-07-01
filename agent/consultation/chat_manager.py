"""
チャットセッション管理
継続的な会話とコンテキスト保持機能
"""
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ..database_handler import DatabaseHandler


class ChatSession:
    """個別のチャットセッションを管理するクラス"""
    
    def __init__(self, session_id: str = None, user_id: str = None):
        """
        チャットセッションの初期化
        
        Args:
            session_id: セッションID（Noneの場合は自動生成）
            user_id: ユーザーID
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.user_id = user_id or "anonymous"
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.messages: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}
        self.is_active = True
    
    def add_message(self, message_type: str, content: str, 
                   metadata: Dict[str, Any] = None) -> str:
        """
        メッセージを追加
        
        Args:
            message_type: メッセージタイプ（user, assistant, system）
            content: メッセージ内容
            metadata: 追加メタデータ
        
        Returns:
            メッセージID
        """
        message_id = str(uuid.uuid4())
        message = {
            'message_id': message_id,
            'type': message_type,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self.messages.append(message)
        self.last_activity = datetime.now()
        
        return message_id
    
    def get_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        最近のメッセージを取得
        
        Args:
            limit: 取得件数
        
        Returns:
            メッセージリスト
        """
        return self.messages[-limit:] if self.messages else []
    
    def get_conversation_context(self, context_length: int = 5) -> str:
        """
        会話コンテキストを文字列として取得
        
        Args:
            context_length: コンテキストに含める過去のやり取り数
        
        Returns:
            会話コンテキスト文字列
        """
        recent_messages = self.get_recent_messages(context_length * 2)
        
        context_parts = []
        for msg in recent_messages:
            if msg['type'] == 'user':
                context_parts.append(f"ユーザー: {msg['content']}")
            elif msg['type'] == 'assistant':
                # アドバイス部分のみを抽出
                advice = msg.get('metadata', {}).get('advice', msg['content'])
                context_parts.append(f"AI: {advice}")
        
        return "\n".join(context_parts)
    
    def update_context(self, key: str, value: Any):
        """
        セッションコンテキストを更新
        
        Args:
            key: コンテキストキー
            value: 値
        """
        self.context[key] = value
        self.last_activity = datetime.now()
    
    def is_expired(self, timeout_hours: int = 24) -> bool:
        """
        セッションが期限切れかチェック
        
        Args:
            timeout_hours: タイムアウト時間（時間）
        
        Returns:
            期限切れの場合True
        """
        return datetime.now() - self.last_activity > timedelta(hours=timeout_hours)
    
    def to_dict(self) -> Dict[str, Any]:
        """セッションを辞書形式に変換"""
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'messages': self.messages,
            'context': self.context,
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatSession':
        """辞書からセッションを復元"""
        session = cls(data['session_id'], data['user_id'])
        session.created_at = datetime.fromisoformat(data['created_at'])
        session.last_activity = datetime.fromisoformat(data['last_activity'])
        session.messages = data.get('messages', [])
        session.context = data.get('context', {})
        session.is_active = data.get('is_active', True)
        return session


class ChatManager:
    """チャットセッション全体を管理するクラス"""
    
    def __init__(self, db_handler: DatabaseHandler):
        """
        チャットマネージャの初期化
        
        Args:
            db_handler: データベースハンドラ
        """
        self.db_handler = db_handler
        self.active_sessions: Dict[str, ChatSession] = {}
        self._init_chat_tables()
    
    def _init_chat_tables(self):
        """チャット用テーブルの初期化"""
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            # チャットセッションテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_activity TEXT NOT NULL,
                    context_data TEXT,  -- JSON形式
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # チャットメッセージテーブル
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    message_type TEXT NOT NULL,  -- user, assistant, system
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,  -- JSON形式
                    FOREIGN KEY (session_id) REFERENCES chat_sessions (session_id)
                )
            """)
            
            # インデックス作成
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_session_user ON chat_sessions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_session_activity ON chat_sessions(last_activity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_message_session ON chat_messages(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_message_timestamp ON chat_messages(timestamp)")
            
            conn.commit()
    
    def create_session(self, user_id: str = None) -> ChatSession:
        """
        新しいチャットセッションを作成
        
        Args:
            user_id: ユーザーID
        
        Returns:
            作成されたセッション
        """
        session = ChatSession(user_id=user_id)
        self.active_sessions[session.session_id] = session
        self._save_session(session)
        
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        セッションを取得
        
        Args:
            session_id: セッションID
        
        Returns:
            セッション（存在しない場合はNone）
        """
        # アクティブセッションから取得を試行
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            if not session.is_expired():
                return session
            else:
                # 期限切れの場合は削除
                del self.active_sessions[session_id]
        
        # データベースから復元を試行
        session = self._load_session(session_id)
        if session and not session.is_expired():
            self.active_sessions[session_id] = session
            return session
        
        return None
    
    def get_or_create_session(self, session_id: str = None, user_id: str = None) -> ChatSession:
        """
        セッションを取得または作成
        
        Args:
            session_id: セッションID（Noneの場合は新規作成）
            user_id: ユーザーID
        
        Returns:
            セッション
        """
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        
        return self.create_session(user_id)
    
    def add_message_to_session(self, session_id: str, message_type: str, 
                              content: str, metadata: Dict[str, Any] = None) -> Optional[str]:
        """
        セッションにメッセージを追加
        
        Args:
            session_id: セッションID
            message_type: メッセージタイプ
            content: メッセージ内容
            metadata: 追加メタデータ
        
        Returns:
            メッセージID（失敗の場合はNone）
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        message_id = session.add_message(message_type, content, metadata)
        self._save_message(session_id, message_id, message_type, content, metadata)
        self._update_session_activity(session)
        
        return message_id
    
    def get_user_sessions(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        ユーザーのセッション一覧を取得
        
        Args:
            user_id: ユーザーID
            limit: 取得件数
        
        Returns:
            セッション情報のリスト
        """
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT session_id, created_at, last_activity, is_active
                FROM chat_sessions 
                WHERE user_id = ? 
                ORDER BY last_activity DESC 
                LIMIT ?
            """, (user_id, limit))
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    'session_id': row['session_id'],
                    'created_at': row['created_at'],
                    'last_activity': row['last_activity'],
                    'is_active': bool(row['is_active'])
                })
            
            return sessions
    
    def cleanup_expired_sessions(self, timeout_hours: int = 24):
        """
        期限切れセッションをクリーンアップ
        
        Args:
            timeout_hours: タイムアウト時間（時間）
        """
        cutoff_time = datetime.now() - timedelta(hours=timeout_hours)
        
        # アクティブセッションから期限切れを削除
        expired_sessions = []
        for session_id, session in self.active_sessions.items():
            if session.is_expired(timeout_hours):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
        
        # データベースの期限切れセッションを無効化
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE chat_sessions 
                SET is_active = 0 
                WHERE last_activity < ? AND is_active = 1
            """, (cutoff_time.isoformat(),))
            conn.commit()
    
    def _save_session(self, session: ChatSession):
        """セッションをデータベースに保存"""
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO chat_sessions 
                (session_id, user_id, created_at, last_activity, context_data, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session.session_id,
                session.user_id,
                session.created_at.isoformat(),
                session.last_activity.isoformat(),
                json.dumps(session.context, ensure_ascii=False),
                session.is_active
            ))
            
            conn.commit()
    
    def _save_message(self, session_id: str, message_id: str, 
                     message_type: str, content: str, metadata: Dict[str, Any] = None):
        """メッセージをデータベースに保存"""
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO chat_messages 
                (message_id, session_id, message_type, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                message_id,
                session_id,
                message_type,
                content,
                datetime.now().isoformat(),
                json.dumps(metadata or {}, ensure_ascii=False)
            ))
            
            conn.commit()
    
    def _load_session(self, session_id: str) -> Optional[ChatSession]:
        """データベースからセッションを復元"""
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            # セッション情報を取得
            cursor.execute("""
                SELECT user_id, created_at, last_activity, context_data, is_active
                FROM chat_sessions 
                WHERE session_id = ? AND is_active = 1
            """, (session_id,))
            
            session_row = cursor.fetchone()
            if not session_row:
                return None
            
            # セッションを復元
            session = ChatSession(session_id, session_row['user_id'])
            session.created_at = datetime.fromisoformat(session_row['created_at'])
            session.last_activity = datetime.fromisoformat(session_row['last_activity'])
            session.is_active = bool(session_row['is_active'])
            
            if session_row['context_data']:
                session.context = json.loads(session_row['context_data'])
            
            # メッセージを取得
            cursor.execute("""
                SELECT message_id, message_type, content, timestamp, metadata
                FROM chat_messages 
                WHERE session_id = ? 
                ORDER BY timestamp ASC
            """, (session_id,))
            
            for msg_row in cursor.fetchall():
                metadata = json.loads(msg_row['metadata']) if msg_row['metadata'] else {}
                session.messages.append({
                    'message_id': msg_row['message_id'],
                    'type': msg_row['message_type'],
                    'content': msg_row['content'],
                    'timestamp': msg_row['timestamp'],
                    'metadata': metadata
                })
            
            return session
    
    def _update_session_activity(self, session: ChatSession):
        """セッションの最終活動時刻を更新"""
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE chat_sessions 
                SET last_activity = ? 
                WHERE session_id = ?
            """, (session.last_activity.isoformat(), session.session_id))
            
            conn.commit()
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """チャットセッションの統計情報を取得"""
        with self.db_handler.get_connection() as conn:
            cursor = conn.cursor()
            
            # アクティブセッション数
            cursor.execute("SELECT COUNT(*) as count FROM chat_sessions WHERE is_active = 1")
            active_sessions = cursor.fetchone()['count']
            
            # 総メッセージ数
            cursor.execute("SELECT COUNT(*) as count FROM chat_messages")
            total_messages = cursor.fetchone()['count']
            
            # 今日のメッセージ数
            today = datetime.now().date().isoformat()
            cursor.execute("SELECT COUNT(*) as count FROM chat_messages WHERE timestamp LIKE ?", (f"{today}%",))
            today_messages = cursor.fetchone()['count']
            
            return {
                'active_sessions': active_sessions,
                'total_messages': total_messages,
                'today_messages': today_messages,
                'active_memory_sessions': len(self.active_sessions)
            }