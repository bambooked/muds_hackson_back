"""
認証・認可インターフェースの具体実装

このモジュールは、auth_ports.pyで定義されたインターフェースの具体実装を提供します。
既存システムとの非破壊的統合を重視し、設定による機能切り替えをサポートします。

実装クラス：
- GoogleOAuth2Authentication: Google OAuth2認証実装
- DatabaseUserManagement: ユーザー管理実装  
- RoleBasedAuthorization: 役割ベース認可実装
- RedisSessionManager: Redisセッション管理（Optional）
"""

import os
import uuid
import json
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# Google OAuth2
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# JWT
import jwt
from cryptography.fernet import Fernet

# Redis (Optional)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .auth_ports import (
    AuthenticationPort, UserManagementPort, AuthorizationPort,
    UserRole, Permission, AuthPortRegistry
)
from .data_models import (
    UserContext, AuthConfig, AuthError, PaaSError
)

logger = logging.getLogger(__name__)


class GoogleOAuth2Authentication(AuthenticationPort):
    """
    Google OAuth2認証の具体実装
    
    機能:
    - Google OAuth2フロー管理
    - 大学ドメイン制限
    - JWT トークン生成・検証
    - セッション管理（Redis/Local）
    """
    
    def __init__(self, config: AuthConfig):
        self.config = config
        self.jwt_secret = os.getenv('JWT_SECRET_KEY', secrets.token_urlsafe(32))
        
        # Google OAuth2設定
        self.client_config = {
            "web": {
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [config.redirect_uri]
            }
        }
        
        # セッション管理設定
        self.session_manager = self._setup_session_manager()
        
        logger.info(f"GoogleOAuth2Authentication initialized with domains: {config.allowed_domains}")
    
    def _setup_session_manager(self):
        """セッション管理器の設定"""
        if REDIS_AVAILABLE:
            try:
                redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                return redis.from_url(redis_url, decode_responses=True)
            except Exception as e:
                logger.warning(f"Redis connection failed, using local storage: {e}")
                return {}  # Fallback to local dict
        else:
            logger.info("Redis not available, using local session storage")
            return {}  # Local storage fallback
    
    async def initiate_google_oauth(
        self,
        redirect_uri: str,
        state: Optional[str] = None
    ) -> Dict[str, str]:
        """Google OAuth認証開始"""
        try:
            flow = Flow.from_client_config(
                self.client_config,
                scopes=[
                    'openid',
                    'email', 
                    'profile',
                    'https://www.googleapis.com/auth/drive.readonly'  # Google Drive access
                ]
            )
            flow.redirect_uri = redirect_uri
            
            if state is None:
                state = secrets.token_urlsafe(32)
            
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                state=state,
                prompt='consent'  # 毎回同意画面を表示
            )
            
            # State をセッションに保存
            await self._store_oauth_state(state, flow.client_config)
            
            logger.info(f"OAuth flow initiated with state: {state}")
            return {'auth_url': auth_url, 'state': state}
            
        except Exception as e:
            logger.error(f"OAuth initiation failed: {e}")
            raise AuthError(f"OAuth initiation failed: {str(e)}")
    
    async def complete_google_oauth(
        self,
        authorization_code: str,
        state: str,
        redirect_uri: str
    ) -> UserContext:
        """Google OAuth認証完了"""
        try:
            # State検証
            stored_config = await self._get_oauth_state(state)
            if not stored_config:
                raise AuthError("Invalid or expired OAuth state")
            
            # OAuth2フロー完了
            flow = Flow.from_client_config(
                stored_config,
                scopes=[
                    'openid', 'email', 'profile',
                    'https://www.googleapis.com/auth/drive.readonly'
                ]
            )
            flow.redirect_uri = redirect_uri
            
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials
            
            # ユーザー情報取得
            user_info = await self._get_user_info(credentials)
            
            # ドメイン制限チェック
            if not await self.validate_domain(user_info['email'], self.config.allowed_domains):
                raise AuthError(f"Domain not allowed: {user_info['email']}")
            
            # ユーザーコンテキスト作成
            user_context = await self._create_user_context(user_info, credentials)
            
            # セッション作成
            await self._create_session(user_context)
            
            # State削除
            await self._remove_oauth_state(state)
            
            logger.info(f"OAuth completed for user: {user_context.email}")
            return user_context
            
        except AuthError:
            raise
        except Exception as e:
            logger.error(f"OAuth completion failed: {e}")
            raise AuthError(f"OAuth completion failed: {str(e)}")
    
    async def authenticate_token(
        self,
        access_token: str
    ) -> Optional[UserContext]:
        """JWTアクセストークン検証"""
        try:
            # JWT デコード
            payload = jwt.decode(
                access_token,
                self.jwt_secret,
                algorithms=['HS256'],
                options={"verify_exp": True}
            )
            
            # セッション確認
            session_id = payload.get('session_id')
            if session_id:
                session_data = await self._get_session(session_id)
                if not session_data:
                    logger.warning(f"Session not found: {session_id}")
                    return None
            
            # ユーザーコンテキスト復元
            user_context = UserContext(
                user_id=payload['user_id'],
                email=payload['email'],
                display_name=payload['display_name'],
                domain=payload['domain'],
                roles=payload['roles'],
                permissions=payload['permissions'],
                session_id=session_id,
                expires_at=datetime.fromtimestamp(payload['exp']),
                metadata=payload.get('metadata', {})
            )
            
            return user_context
            
        except jwt.ExpiredSignatureError:
            logger.info("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token authentication failed: {e}")
            return None
    
    async def refresh_token(
        self,
        refresh_token: str
    ) -> Optional[Dict[str, str]]:
        """リフレッシュトークンによるトークン更新"""
        try:
            # リフレッシュトークン検証
            payload = jwt.decode(
                refresh_token,
                self.jwt_secret,
                algorithms=['HS256']
            )
            
            if payload.get('token_type') != 'refresh':
                raise AuthError("Invalid refresh token type")
            
            # セッション確認
            session_id = payload['session_id']
            session_data = await self._get_session(session_id)
            if not session_data:
                raise AuthError("Session not found")
            
            # 新しいアクセストークン生成
            user_data = json.loads(session_data)
            user_context = UserContext(**user_data)
            
            new_access_token = await self._generate_access_token(user_context)
            new_refresh_token = await self._generate_refresh_token(user_context)
            
            return {
                'access_token': new_access_token,
                'refresh_token': new_refresh_token,
                'token_type': 'bearer',
                'expires_in': 3600  # 1 hour
            }
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return None
    
    async def logout(
        self,
        user_id: str,
        session_id: Optional[str] = None
    ) -> bool:
        """ログアウト処理"""
        try:
            if session_id:
                # 特定セッションのみ削除
                await self._remove_session(session_id)
            else:
                # 全セッション削除
                await self._remove_all_user_sessions(user_id)
            
            logger.info(f"Logout completed for user: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False
    
    async def validate_domain(
        self,
        email: str,
        allowed_domains: List[str]
    ) -> bool:
        """ドメイン制限チェック"""
        if not allowed_domains:
            return True
        
        domain = email.split('@')[-1].lower()
        return domain in [d.lower() for d in allowed_domains]
    
    # プライベートメソッド
    
    async def _get_user_info(self, credentials: Credentials) -> Dict[str, Any]:
        """Google APIからユーザー情報取得"""
        import httpx
        
        # Google UserInfo API呼び出し
        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {credentials.token}'}
            )
            response.raise_for_status()
            return response.json()
    
    async def _create_user_context(
        self,
        user_info: Dict[str, Any],
        credentials: Credentials
    ) -> UserContext:
        """ユーザーコンテキスト作成"""
        user_id = user_info['id']
        email = user_info['email']
        domain = email.split('@')[-1]
        
        # 役割の自動判定（ドメインベース）
        roles = await self._determine_user_roles(email, domain)
        
        # 権限マトリクス生成
        permissions = await self._generate_permissions(roles)
        
        return UserContext(
            user_id=user_id,
            email=email,
            display_name=user_info.get('name', email),
            domain=domain,
            roles=roles,
            permissions=permissions,
            session_id=str(uuid.uuid4()),
            expires_at=datetime.now() + timedelta(minutes=self.config.session_timeout_minutes),
            metadata={
                'google_credentials': {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'expires_at': credentials.expiry.isoformat() if credentials.expiry else None
                },
                'picture': user_info.get('picture'),
                'verified_email': user_info.get('verified_email', False)
            }
        )
    
    async def _determine_user_roles(self, email: str, domain: str) -> List[str]:
        """ユーザー役割の自動判定"""
        roles = ['guest']  # デフォルト
        
        # ドメインベースの判定（カスタマイズ可能）
        if domain in self.config.allowed_domains:
            roles = ['student']  # 大学ドメインは学生
            
            # 教員判定ロジック（メールアドレスパターン等）
            faculty_patterns = ['faculty', 'prof', 'teacher', 'staff']
            if any(pattern in email.lower() for pattern in faculty_patterns):
                roles = ['faculty']
        
        return roles
    
    async def _generate_permissions(self, roles: List[str]) -> Dict[str, List[str]]:
        """役割ベース権限生成"""
        from .auth_ports import create_default_permissions, UserRole
        
        default_perms = create_default_permissions()
        combined_perms = {}
        
        for role_str in roles:
            try:
                role_enum = UserRole(role_str)
                role_perms = default_perms.get(role_enum, {})
                
                for resource, perms in role_perms.items():
                    if resource not in combined_perms:
                        combined_perms[resource] = []
                    
                    for perm in perms:
                        if perm.value not in combined_perms[resource]:
                            combined_perms[resource].append(perm.value)
                            
            except ValueError:
                logger.warning(f"Unknown role: {role_str}")
        
        return combined_perms
    
    async def _generate_access_token(self, user_context: UserContext) -> str:
        """アクセストークン生成"""
        now = datetime.now()
        payload = {
            'user_id': user_context.user_id,
            'email': user_context.email,
            'display_name': user_context.display_name,
            'domain': user_context.domain,
            'roles': user_context.roles,
            'permissions': user_context.permissions,
            'session_id': user_context.session_id,
            'token_type': 'access',
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(hours=1)).timestamp()),  # 1時間有効
            'metadata': user_context.metadata
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    
    async def _generate_refresh_token(self, user_context: UserContext) -> str:
        """リフレッシュトークン生成"""
        now = datetime.now()
        payload = {
            'user_id': user_context.user_id,
            'session_id': user_context.session_id,
            'token_type': 'refresh',
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(days=30)).timestamp())  # 30日有効
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    
    async def _create_session(self, user_context: UserContext):
        """セッション作成"""
        session_data = json.dumps({
            'user_id': user_context.user_id,
            'email': user_context.email,
            'display_name': user_context.display_name,
            'domain': user_context.domain,
            'roles': user_context.roles,
            'permissions': user_context.permissions,
            'created_at': datetime.now().isoformat(),
            'expires_at': user_context.expires_at.isoformat() if user_context.expires_at else None,
            'metadata': user_context.metadata
        })
        
        if isinstance(self.session_manager, dict):
            # Local storage
            self.session_manager[user_context.session_id] = session_data
        else:
            # Redis storage
            await self.session_manager.setex(
                f"session:{user_context.session_id}",
                self.config.session_timeout_minutes * 60,
                session_data
            )
    
    async def _get_session(self, session_id: str) -> Optional[str]:
        """セッション取得"""
        if isinstance(self.session_manager, dict):
            return self.session_manager.get(session_id)
        else:
            return await self.session_manager.get(f"session:{session_id}")
    
    async def _remove_session(self, session_id: str):
        """セッション削除"""
        if isinstance(self.session_manager, dict):
            self.session_manager.pop(session_id, None)
        else:
            await self.session_manager.delete(f"session:{session_id}")
    
    async def _remove_all_user_sessions(self, user_id: str):
        """ユーザーの全セッション削除"""
        if isinstance(self.session_manager, dict):
            # Local storage: 全セッションを確認
            to_remove = []
            for session_id, session_data in self.session_manager.items():
                data = json.loads(session_data)
                if data.get('user_id') == user_id:
                    to_remove.append(session_id)
            
            for session_id in to_remove:
                del self.session_manager[session_id]
        else:
            # Redis: パターンマッチで削除
            keys = await self.session_manager.keys(f"session:*")
            for key in keys:
                session_data = await self.session_manager.get(key)
                if session_data:
                    data = json.loads(session_data)
                    if data.get('user_id') == user_id:
                        await self.session_manager.delete(key)
    
    async def _store_oauth_state(self, state: str, client_config: Dict[str, Any]):
        """OAuth state保存"""
        state_data = json.dumps(client_config)
        
        if isinstance(self.session_manager, dict):
            self.session_manager[f"oauth_state:{state}"] = state_data
        else:
            await self.session_manager.setex(
                f"oauth_state:{state}",
                600,  # 10分有効
                state_data
            )
    
    async def _get_oauth_state(self, state: str) -> Optional[Dict[str, Any]]:
        """OAuth state取得"""
        if isinstance(self.session_manager, dict):
            state_data = self.session_manager.get(f"oauth_state:{state}")
        else:
            state_data = await self.session_manager.get(f"oauth_state:{state}")
        
        if state_data:
            return json.loads(state_data)
        return None
    
    async def _remove_oauth_state(self, state: str):
        """OAuth state削除"""
        if isinstance(self.session_manager, dict):
            self.session_manager.pop(f"oauth_state:{state}", None)
        else:
            await self.session_manager.delete(f"oauth_state:{state}")


class DatabaseUserManagement(UserManagementPort):
    """
    データベースベースのユーザー管理実装
    
    機能:
    - ユーザー情報の永続化
    - 役割管理
    - ユーザー検索
    
    注意: 現在は簡易実装、本格運用時はSQLite/PostgreSQL等のDB使用推奨
    """
    
    def __init__(self):
        self.users_storage = {}  # 簡易実装: 実際はDBを使用
        logger.info("DatabaseUserManagement initialized with in-memory storage")
    
    async def create_user(
        self,
        email: str,
        display_name: str,
        roles: List[UserRole] = None,
        metadata: Dict[str, Any] = None
    ) -> UserContext:
        """ユーザー作成"""
        if roles is None:
            roles = [UserRole.STUDENT]
        
        # 重複チェック
        for user in self.users_storage.values():
            if user['email'] == email:
                raise AuthError(f"User already exists: {email}")
        
        user_id = str(uuid.uuid4())
        domain = email.split('@')[-1]
        
        # 権限生成
        from .auth_ports import create_default_permissions
        default_perms = create_default_permissions()
        permissions = {}
        
        for role in roles:
            role_perms = default_perms.get(role, {})
            for resource, perms in role_perms.items():
                if resource not in permissions:
                    permissions[resource] = []
                for perm in perms:
                    if perm.value not in permissions[resource]:
                        permissions[resource].append(perm.value)
        
        user_context = UserContext(
            user_id=user_id,
            email=email,
            display_name=display_name,
            domain=domain,
            roles=[role.value for role in roles],
            permissions=permissions,
            metadata=metadata or {}
        )
        
        # 保存
        self.users_storage[user_id] = {
            'user_id': user_id,
            'email': email,
            'display_name': display_name,
            'domain': domain,
            'roles': [role.value for role in roles],
            'permissions': permissions,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        logger.info(f"User created: {email} with roles: {[r.value for r in roles]}")
        return user_context
    
    async def get_user(self, user_id: str) -> Optional[UserContext]:
        """ユーザー情報取得"""
        user_data = self.users_storage.get(user_id)
        if not user_data:
            return None
        
        return UserContext(
            user_id=user_data['user_id'],
            email=user_data['email'],
            display_name=user_data['display_name'],
            domain=user_data['domain'],
            roles=user_data['roles'],
            permissions=user_data['permissions'],
            metadata=user_data.get('metadata', {})
        )
    
    async def update_user_roles(
        self,
        user_id: str,
        roles: List[UserRole],
        updated_by: str
    ) -> bool:
        """ユーザー役割更新"""
        if user_id not in self.users_storage:
            return False
        
        # 管理者権限チェック（簡易実装）
        updater = self.users_storage.get(updated_by)
        if not updater or 'admin' not in updater.get('roles', []):
            raise AuthError("Insufficient permissions to update user roles")
        
        # 自分自身の管理者権限削除防止
        if user_id == updated_by and UserRole.ADMIN not in roles:
            if 'admin' in self.users_storage[user_id]['roles']:
                raise AuthError("Cannot remove admin role from yourself")
        
        # 権限再生成
        from .auth_ports import create_default_permissions
        default_perms = create_default_permissions()
        permissions = {}
        
        for role in roles:
            role_perms = default_perms.get(role, {})
            for resource, perms in role_perms.items():
                if resource not in permissions:
                    permissions[resource] = []
                for perm in perms:
                    if perm.value not in permissions[resource]:
                        permissions[resource].append(perm.value)
        
        # 更新
        self.users_storage[user_id]['roles'] = [role.value for role in roles]
        self.users_storage[user_id]['permissions'] = permissions
        self.users_storage[user_id]['updated_at'] = datetime.now().isoformat()
        
        logger.info(f"User roles updated: {user_id} -> {[r.value for r in roles]}")
        return True
    
    async def search_users(
        self,
        query: str,
        roles: Optional[List[UserRole]] = None,
        limit: int = 50
    ) -> List[UserContext]:
        """ユーザー検索"""
        results = []
        query_lower = query.lower()
        
        for user_data in self.users_storage.values():
            # 検索マッチング
            if (query_lower in user_data['email'].lower() or 
                query_lower in user_data['display_name'].lower()):
                
                # 役割フィルタ
                if roles:
                    role_strings = [role.value for role in roles]
                    if not any(role in user_data['roles'] for role in role_strings):
                        continue
                
                user_context = UserContext(
                    user_id=user_data['user_id'],
                    email=user_data['email'],
                    display_name=user_data['display_name'],
                    domain=user_data['domain'],
                    roles=user_data['roles'],
                    permissions=user_data['permissions'],
                    metadata=user_data.get('metadata', {})
                )
                results.append(user_context)
                
                if len(results) >= limit:
                    break
        
        return results
    
    async def list_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """アクティブセッション一覧（簡易実装）"""
        # 実際の実装では認証システムと連携
        return [
            {
                'session_id': 'example_session',
                'created_at': datetime.now().isoformat(),
                'last_access': datetime.now().isoformat(),
                'ip_address': '127.0.0.1',
                'user_agent': 'FastAPI Client'
            }
        ]


class RoleBasedAuthorization(AuthorizationPort):
    """
    役割ベース認可システムの実装
    
    機能:
    - リソース別権限チェック
    - 役割継承
    - 細かい権限制御
    """
    
    def __init__(self):
        from .auth_ports import create_default_permissions
        self.default_permissions = create_default_permissions()
        logger.info("RoleBasedAuthorization initialized")
    
    async def check_permission(
        self,
        user_context: UserContext,
        resource: str,
        action: Permission,
        resource_id: Optional[str] = None
    ) -> bool:
        """権限チェック"""
        # 管理者は全権限
        if 'admin' in user_context.roles:
            return True
        
        # ユーザーの権限確認
        user_permissions = user_context.permissions.get(resource, [])
        if action.value in user_permissions:
            return True
        
        # 役割ベース権限確認
        for role_str in user_context.roles:
            try:
                from .auth_ports import UserRole
                role = UserRole(role_str)
                role_permissions = self.default_permissions.get(role, {}).get(resource, [])
                
                if action in role_permissions:
                    return True
                    
            except ValueError:
                continue
        
        logger.debug(f"Permission denied: {user_context.email} -> {resource}:{action.value}")
        return False
    
    async def get_user_permissions(
        self,
        user_context: UserContext
    ) -> Dict[str, List[Permission]]:
        """ユーザー権限一覧取得"""
        combined_permissions = {}
        
        # 役割ベース権限収集
        for role_str in user_context.roles:
            try:
                from .auth_ports import UserRole
                role = UserRole(role_str)
                role_perms = self.default_permissions.get(role, {})
                
                for resource, permissions in role_perms.items():
                    if resource not in combined_permissions:
                        combined_permissions[resource] = []
                    
                    for perm in permissions:
                        if perm not in combined_permissions[resource]:
                            combined_permissions[resource].append(perm)
                            
            except ValueError:
                continue
        
        return combined_permissions
    
    async def check_resource_ownership(
        self,
        user_context: UserContext,
        resource_type: str,
        resource_id: str
    ) -> bool:
        """リソース所有権チェック（簡易実装）"""
        # 実際の実装では、文書作成者情報等をDBから取得
        # 現在は管理者・教員に全権限を付与
        return ('admin' in user_context.roles or 
                'faculty' in user_context.roles)
    
    async def grant_permission(
        self,
        grantor: UserContext,
        grantee_id: str,
        resource: str,
        permissions: List[Permission],
        expires_at: Optional[datetime] = None
    ) -> bool:
        """権限付与（簡易実装）"""
        # 付与者の権限チェック
        if not ('admin' in grantor.roles or 'faculty' in grantor.roles):
            return False
        
        # 実際の実装では、一時的権限をDBに保存
        # 現在は基本権限のみサポート
        logger.info(f"Permission granted: {grantor.email} -> {grantee_id} for {resource}")
        return True


def create_auth_system(config: AuthConfig) -> AuthPortRegistry:
    """
    認証システム作成ヘルパー関数
    
    設定に基づいて必要な認証コンポーネントを作成し、
    AuthPortRegistryに登録して返します。
    
    Args:
        config: 認証設定
        
    Returns:
        AuthPortRegistry: 設定済み認証システム
    """
    registry = AuthPortRegistry()
    
    try:
        # 認証ポート作成・登録
        auth_port = GoogleOAuth2Authentication(config)
        registry.register_authentication_port(auth_port)
        
        # ユーザー管理ポート作成・登録
        user_mgmt_port = DatabaseUserManagement()
        registry.register_user_management_port(user_mgmt_port)
        
        # 認可ポート作成・登録
        authz_port = RoleBasedAuthorization()
        registry.register_authorization_port(authz_port)
        
        logger.info("Authentication system created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create authentication system: {e}")
        raise AuthError(f"Authentication system creation failed: {str(e)}")
    
    return registry