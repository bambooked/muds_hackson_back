"""
認証・OAuth統合機能
Google OAuth、JWT認証、セッション管理を提供
"""

import os
import jwt
import json
import secrets
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import logging

try:
    from google.auth.transport import requests
    from google.oauth2 import id_token
    from google_auth_oauthlib.flow import Flow
    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False

logger = logging.getLogger(__name__)

class AuthenticationManager:
    """認証管理クラス"""
    
    def __init__(self):
        self.enabled = os.getenv('ENABLE_AUTHENTICATION', 'false').lower() == 'true'
        self.oauth_provider = os.getenv('OAUTH_PROVIDER', 'google')
        self.client_id = os.getenv('OAUTH_CLIENT_ID', '')
        self.client_secret = os.getenv('OAUTH_CLIENT_SECRET', '')
        self.redirect_uri = os.getenv('OAUTH_REDIRECT_URI', 'http://localhost:8000/auth/callback')
        self.jwt_secret = os.getenv('JWT_SECRET_KEY', self._generate_secret())
        self.session_timeout = int(os.getenv('SESSION_TIMEOUT', '60'))  # minutes
        self.cookie_secure = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
        
        self.active_sessions = {}
        
        if not OAUTH_AVAILABLE and self.enabled:
            logger.warning("OAuth libraries not installed. Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2")
            self.enabled = False
        
        if self.enabled:
            self._validate_config()
    
    def _generate_secret(self) -> str:
        """JWT秘密鍵を生成"""
        return secrets.token_urlsafe(32)
    
    def _validate_config(self) -> bool:
        """設定を検証"""
        if not self.client_id or not self.client_secret:
            logger.error("OAuth client ID and secret must be configured")
            self.enabled = False
            return False
        
        return True
    
    def is_enabled(self) -> bool:
        """認証機能が有効かどうか"""
        return self.enabled
    
    def create_oauth_flow(self) -> Optional[Any]:
        """OAuth認証フローを作成"""
        if not self.is_enabled() or self.oauth_provider != 'google':
            return None
        
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=['openid', 'email', 'profile', 'https://www.googleapis.com/auth/drive.readonly']
            )
            flow.redirect_uri = self.redirect_uri
            return flow
            
        except Exception as e:
            logger.error(f"Failed to create OAuth flow: {e}")
            return None
    
    def get_authorization_url(self) -> Optional[str]:
        """認証URLを取得"""
        flow = self.create_oauth_flow()
        if not flow:
            return None
        
        try:
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            return authorization_url
            
        except Exception as e:
            logger.error(f"Failed to get authorization URL: {e}")
            return None
    
    def handle_oauth_callback(self, authorization_code: str) -> Optional[Dict[str, Any]]:
        """OAuth認証コールバックを処理"""
        flow = self.create_oauth_flow()
        if not flow:
            return None
        
        try:
            # 認証コードをトークンに交換
            flow.fetch_token(code=authorization_code)
            
            # ユーザー情報を取得
            credentials = flow.credentials
            request = requests.Request()
            
            # ID トークンを検証
            id_info = id_token.verify_oauth2_token(
                credentials.id_token, request, self.client_id
            )
            
            user_info = {
                'user_id': id_info['sub'],
                'email': id_info['email'],
                'name': id_info.get('name', ''),
                'picture': id_info.get('picture', ''),
                'email_verified': id_info.get('email_verified', False)
            }
            
            # JWTトークンを生成
            jwt_token = self.create_jwt_token(user_info)
            
            # セッションを作成
            session_id = self.create_session(user_info)
            
            return {
                'user': user_info,
                'jwt_token': jwt_token,
                'session_id': session_id,
                'expires_at': datetime.now() + timedelta(minutes=self.session_timeout)
            }
            
        except Exception as e:
            logger.error(f"OAuth callback handling failed: {e}")
            return None
    
    def create_jwt_token(self, user_info: Dict[str, Any]) -> str:
        """JWTトークンを生成"""
        try:
            payload = {
                'user_id': user_info['user_id'],
                'email': user_info['email'],
                'exp': datetime.utcnow() + timedelta(minutes=self.session_timeout),
                'iat': datetime.utcnow()
            }
            
            token = jwt.encode(payload, self.jwt_secret, algorithm='HS256')
            return token
            
        except Exception as e:
            logger.error(f"JWT token creation failed: {e}")
            return ''
    
    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """JWTトークンを検証"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"JWT verification failed: {e}")
            return None
    
    def create_session(self, user_info: Dict[str, Any]) -> str:
        """セッションを作成"""
        session_id = secrets.token_urlsafe(32)
        
        self.active_sessions[session_id] = {
            'user_info': user_info,
            'created_at': datetime.now(),
            'last_access': datetime.now(),
            'expires_at': datetime.now() + timedelta(minutes=self.session_timeout)
        }
        
        logger.info(f"Session created for user: {user_info['email']}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """セッション情報を取得"""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        # セッション有効期限チェック
        if datetime.now() > session['expires_at']:
            self.destroy_session(session_id)
            return None
        
        # 最終アクセス時刻を更新
        session['last_access'] = datetime.now()
        return session
    
    def refresh_session(self, session_id: str) -> bool:
        """セッションを更新"""
        session = self.active_sessions.get(session_id)
        if not session:
            return False
        
        session['expires_at'] = datetime.now() + timedelta(minutes=self.session_timeout)
        session['last_access'] = datetime.now()
        return True
    
    def destroy_session(self, session_id: str) -> bool:
        """セッションを削除"""
        if session_id in self.active_sessions:
            user_email = self.active_sessions[session_id]['user_info'].get('email', 'unknown')
            del self.active_sessions[session_id]
            logger.info(f"Session destroyed for user: {user_email}")
            return True
        return False
    
    def cleanup_expired_sessions(self) -> int:
        """期限切れセッションをクリーンアップ"""
        current_time = datetime.now()
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            if current_time > session['expires_at']:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.destroy_session(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        return len(expired_sessions)
    
    def get_user_permissions(self, user_id: str) -> Dict[str, bool]:
        """ユーザー権限を取得"""
        # 基本的な権限設定（実際の実装では外部データベースから取得）
        default_permissions = {
            'read_data': True,
            'write_data': True,
            'delete_data': False,
            'admin_access': False,
            'google_drive_access': True,
            'api_access': True
        }
        
        # 管理者ユーザーの設定（環境変数から）
        admin_users = os.getenv('ADMIN_USERS', '').split(',')
        if user_id in admin_users:
            default_permissions.update({
                'delete_data': True,
                'admin_access': True
            })
        
        return default_permissions
    
    def check_permission(self, session_id: str, permission: str) -> bool:
        """権限をチェック"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        user_id = session['user_info']['user_id']
        permissions = self.get_user_permissions(user_id)
        
        return permissions.get(permission, False)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """セッション統計を取得"""
        active_count = len(self.active_sessions)
        
        if active_count == 0:
            return {
                'active_sessions': 0,
                'total_users': 0,
                'oldest_session': None,
                'newest_session': None
            }
        
        sessions = list(self.active_sessions.values())
        created_times = [s['created_at'] for s in sessions]
        
        return {
            'active_sessions': active_count,
            'total_users': len(set(s['user_info']['user_id'] for s in sessions)),
            'oldest_session': min(created_times),
            'newest_session': max(created_times)
        }

# グローバルインスタンス
auth_manager = AuthenticationManager()