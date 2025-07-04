"""
認証・認可インターフェース定義

このモジュールは、Google OAuth2認証、ユーザー管理、権限制御機能を抽象化します。
既存の無認証システムを段階的にセキュア化し、大学環境での安全な運用を実現。

Claude Code実装ガイダンス：
- Google OAuth2認証必須（大学アカウント連携）
- ドメイン制限による学部メンバー限定
- 役割ベース権限制御（教員・学生・ゲスト）
- 既存APIの段階的セキュア化

実装優先順位：
1. AuthenticationPort (基本認証機能)
2. UserManagementPort (ユーザー管理)
3. AuthorizationPort (権限制御) 

セキュリティ要件：
- 学部ドメインのみ許可 (@university.ac.jp)
- セッション管理とトークン更新
- 適切な権限分離（教員 > 学生 > ゲスト）
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum

from .data_models import (
    UserContext,
    AuthConfig,
    AuthError
)


class UserRole(Enum):
    """ユーザー役割"""
    ADMIN = "admin"              # システム管理者
    FACULTY = "faculty"          # 教員
    STUDENT = "student"          # 学生
    GUEST = "guest"              # ゲスト
    RESEARCHER = "researcher"    # 研究者


class Permission(Enum):
    """権限種別"""
    READ = "read"                # 読み取り
    WRITE = "write"              # 書き込み
    DELETE = "delete"            # 削除
    ADMIN = "admin"              # 管理
    SHARE = "share"              # 共有
    EXPORT = "export"            # エクスポート


class AuthenticationPort(ABC):
    """
    認証インターフェース
    
    役割：
    - Google OAuth2認証処理
    - セッション管理
    - トークン検証・更新
    
    Claude Code実装ガイダンス：
    - Google OAuth2 flow実装必須
    - 大学ドメイン制限実装
    - JWT トークン使用推奨
    - セッション永続化（Redis推奨）
    
    推奨実装パッケージ：
    - google-auth-oauthlib
    - PyJWT
    - redis（セッション管理）
    """
    
    @abstractmethod
    async def initiate_google_oauth(
        self,
        redirect_uri: str,
        state: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Google OAuth認証開始
        
        Args:
            redirect_uri: 認証後のリダイレクトURI
            state: CSRF防止用のstate parameter
            
        Returns:
            Dict: {'auth_url': '...', 'state': '...'}
            
        Claude Code実装例：
        ```python
        from google_auth_oauthlib.flow import Flow
        
        async def initiate_google_oauth(self, redirect_uri, state=None):
            try:
                flow = Flow.from_client_config(
                    self.client_config,
                    scopes=['openid', 'email', 'profile']
                )
                flow.redirect_uri = redirect_uri
                
                auth_url, state = flow.authorization_url(
                    access_type='offline',
                    include_granted_scopes='true',
                    state=state
                )
                
                return {'auth_url': auth_url, 'state': state}
            except Exception as e:
                raise AuthError(f"OAuth initiation failed: {e}")
        ```
        """
        pass
    
    @abstractmethod
    async def complete_google_oauth(
        self,
        authorization_code: str,
        state: str,
        redirect_uri: str
    ) -> UserContext:
        """
        Google OAuth認証完了
        
        Args:
            authorization_code: 認証コード
            state: state parameter
            redirect_uri: リダイレクトURI
            
        Returns:
            UserContext: 認証済みユーザー情報
            
        Raises:
            AuthError: 認証失敗、ドメイン制限違反等
            
        Claude Code実装時の注意：
        - ドメイン制限チェック必須
        - ユーザー情報の初回登録処理
        - 役割の自動割り当て（デフォルト: STUDENT）
        """
        pass
    
    @abstractmethod
    async def authenticate_token(
        self,
        access_token: str
    ) -> Optional[UserContext]:
        """
        アクセストークン検証
        
        Args:
            access_token: JWTアクセストークン
            
        Returns:
            Optional[UserContext]: 有効時はユーザー情報、無効時はNone
            
        Claude Code実装例：
        ```python
        import jwt
        
        async def authenticate_token(self, access_token):
            try:
                payload = jwt.decode(
                    access_token,
                    self.secret_key,
                    algorithms=['HS256']
                )
                
                # トークン有効期限チェック
                if datetime.fromtimestamp(payload['exp']) < datetime.now():
                    return None
                
                # ユーザー情報取得
                user_id = payload['user_id']
                return await self._get_user_context(user_id)
                
            except (jwt.InvalidTokenError, KeyError):
                return None
        ```
        """
        pass
    
    @abstractmethod
    async def refresh_token(
        self,
        refresh_token: str
    ) -> Optional[Dict[str, str]]:
        """
        トークン更新
        
        Args:
            refresh_token: リフレッシュトークン
            
        Returns:
            Optional[Dict]: {'access_token': '...', 'refresh_token': '...'}
        """
        pass
    
    @abstractmethod
    async def logout(
        self,
        user_id: str,
        session_id: Optional[str] = None
    ) -> bool:
        """
        ログアウト処理
        
        Args:
            user_id: ユーザーID
            session_id: セッションID（指定時は該当セッションのみ無効化）
            
        Returns:
            bool: ログアウト成功可否
        """
        pass
    
    @abstractmethod
    async def validate_domain(
        self,
        email: str,
        allowed_domains: List[str]
    ) -> bool:
        """
        ドメイン制限チェック
        
        Args:
            email: ユーザーメールアドレス
            allowed_domains: 許可ドメインリスト
            
        Returns:
            bool: ドメイン許可可否
            
        Claude Code実装例：
        ```python
        async def validate_domain(self, email, allowed_domains):
            domain = email.split('@')[-1].lower()
            return domain in [d.lower() for d in allowed_domains]
        ```
        """
        pass


class UserManagementPort(ABC):
    """
    ユーザー管理インターフェース
    
    役割：
    - ユーザー情報管理
    - 役割・権限管理
    - ユーザー検索・一覧
    
    Claude Code実装ガイダンス：
    - ユーザー情報はデータベース永続化
    - 役割変更は管理者のみ可能
    - プライバシー情報の適切な管理
    """
    
    @abstractmethod
    async def create_user(
        self,
        email: str,
        display_name: str,
        roles: List[UserRole] = None,
        metadata: Dict[str, Any] = None
    ) -> UserContext:
        """
        ユーザー作成
        
        Args:
            email: メールアドレス
            display_name: 表示名
            roles: 初期役割（デフォルト: [UserRole.STUDENT]）
            metadata: 追加情報
            
        Returns:
            UserContext: 作成されたユーザー情報
            
        Claude Code実装時の注意：
        - 重複チェック（email重複回避）
        - デフォルト権限設定
        - 学部ドメインから役割推定可能
        """
        pass
    
    @abstractmethod
    async def get_user(
        self,
        user_id: str
    ) -> Optional[UserContext]:
        """
        ユーザー情報取得
        
        Args:
            user_id: ユーザーID
            
        Returns:
            Optional[UserContext]: ユーザー情報
        """
        pass
    
    @abstractmethod
    async def update_user_roles(
        self,
        user_id: str,
        roles: List[UserRole],
        updated_by: str
    ) -> bool:
        """
        ユーザー役割更新
        
        Args:
            user_id: 対象ユーザーID
            roles: 新しい役割リスト
            updated_by: 更新実行者ID
            
        Returns:
            bool: 更新成功可否
            
        Claude Code実装時の注意：
        - 管理者権限チェック必須
        - 変更履歴の記録
        - 自分自身の管理者権限削除防止
        """
        pass
    
    @abstractmethod
    async def search_users(
        self,
        query: str,
        roles: Optional[List[UserRole]] = None,
        limit: int = 50
    ) -> List[UserContext]:
        """
        ユーザー検索
        
        Args:
            query: 検索クエリ（名前・メール）
            roles: 役割フィルタ
            limit: 取得件数制限
            
        Returns:
            List[UserContext]: 検索結果
        """
        pass
    
    @abstractmethod
    async def list_active_sessions(
        self,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        アクティブセッション一覧
        
        Returns:
            List[Dict]: [{'session_id': '...', 'created_at': '...', 'last_access': '...'}, ...]
        """
        pass


class AuthorizationPort(ABC):
    """
    認可インターフェース
    
    役割：
    - リソースアクセス権限チェック
    - 役割ベース権限制御
    - 細かい権限管理
    
    Claude Code実装ガイダンス：
    - 既存APIエンドポイントのデコレータ実装
    - リソース別権限マトリクス定義
    - 権限継承（教員 > 学生 > ゲスト）
    """
    
    @abstractmethod
    async def check_permission(
        self,
        user_context: UserContext,
        resource: str,
        action: Permission,
        resource_id: Optional[str] = None
    ) -> bool:
        """
        権限チェック
        
        Args:
            user_context: ユーザーコンテキスト
            resource: リソース種別 ('documents', 'search', 'admin')
            action: 実行アクション
            resource_id: 特定リソースID（文書ID等）
            
        Returns:
            bool: 権限許可可否
            
        Claude Code実装例：
        ```python
        async def check_permission(self, user_context, resource, action, resource_id=None):
            # 管理者は全権限
            if UserRole.ADMIN in user_context.roles:
                return True
            
            # リソース別権限チェック
            if resource == 'documents':
                if action == Permission.READ:
                    return True  # 全ユーザー読み取り可能
                elif action == Permission.WRITE:
                    return UserRole.FACULTY in user_context.roles or UserRole.STUDENT in user_context.roles
                elif action == Permission.DELETE:
                    return UserRole.FACULTY in user_context.roles
            elif resource == 'admin':
                return UserRole.ADMIN in user_context.roles or UserRole.FACULTY in user_context.roles
            
            return False
        ```
        """
        pass
    
    @abstractmethod
    async def get_user_permissions(
        self,
        user_context: UserContext
    ) -> Dict[str, List[Permission]]:
        """
        ユーザー権限一覧取得
        
        Returns:
            Dict: {'documents': [Permission.READ, Permission.WRITE], 'search': [Permission.READ]}
        """
        pass
    
    @abstractmethod
    async def check_resource_ownership(
        self,
        user_context: UserContext,
        resource_type: str,
        resource_id: str
    ) -> bool:
        """
        リソース所有権チェック
        
        Args:
            user_context: ユーザーコンテキスト
            resource_type: 'document', 'dataset', etc.
            resource_id: リソースID
            
        Returns:
            bool: 所有権の有無
        """
        pass
    
    @abstractmethod
    async def grant_permission(
        self,
        grantor: UserContext,
        grantee_id: str,
        resource: str,
        permissions: List[Permission],
        expires_at: Optional[datetime] = None
    ) -> bool:
        """
        権限付与
        
        Args:
            grantor: 権限付与者
            grantee_id: 権限付与対象ユーザーID
            resource: リソース
            permissions: 付与する権限リスト
            expires_at: 権限有効期限
            
        Returns:
            bool: 権限付与成功可否
            
        Claude Code実装時の注意：
        - 付与者の権限チェック必須
        - 権限付与の監査ログ記録
        - 一時的権限の自動失効処理
        """
        pass


# ========================================
# Implementation Helper Classes
# ========================================

class AuthPortRegistry:
    """
    認証・認可ポートの統合管理クラス
    
    Claude Code実装ガイダンス：
    - 各認証ポートを統合管理
    - 認証フローの一元制御
    - エラー時のフォールバック処理
    """
    
    def __init__(self):
        self.auth_port: Optional[AuthenticationPort] = None
        self.user_mgmt_port: Optional[UserManagementPort] = None
        self.authz_port: Optional[AuthorizationPort] = None
        self._auth_enabled = False
    
    def register_authentication_port(self, port: AuthenticationPort):
        """認証ポート登録"""
        self.auth_port = port
    
    def register_user_management_port(self, port: UserManagementPort):
        """ユーザー管理ポート登録"""
        self.user_mgmt_port = port
    
    def register_authorization_port(self, port: AuthorizationPort):
        """認可ポート登録"""
        self.authz_port = port
    
    def enable_authentication(self, enabled: bool = True):
        """認証機能の有効/無効切り替え"""
        self._auth_enabled = enabled
    
    async def authenticate_request(
        self,
        access_token: Optional[str] = None
    ) -> Optional[UserContext]:
        """
        リクエスト認証
        
        Claude Code実装時の注意：
        - 認証無効時はNoneを返却（既存システム継続）
        - 認証有効時はトークン必須
        """
        if not self._auth_enabled:
            return None  # 認証無効時は既存システム継続
        
        if not access_token or not self.auth_port:
            return None
        
        return await self.auth_port.authenticate_token(access_token)
    
    async def authorize_action(
        self,
        user_context: Optional[UserContext],
        resource: str,
        action: Permission,
        resource_id: Optional[str] = None
    ) -> bool:
        """
        アクション認可
        
        Claude Code実装時の注意：
        - 認証無効時は常にTrue（既存システム継続）
        - 認証有効時は権限チェック実行
        """
        if not self._auth_enabled:
            return True  # 認証無効時は全許可
        
        if not user_context or not self.authz_port:
            return False  # 認証有効だがユーザー情報なしは拒否
        
        return await self.authz_port.check_permission(
            user_context, resource, action, resource_id
        )


# ========================================
# Decorators for Claude Code
# ========================================

def require_authentication(registry: AuthPortRegistry):
    """
    認証必須デコレータ
    
    Claude Code実装時の使用例：
    ```python
    @require_authentication(auth_registry)
    async def secure_endpoint(request):
        # 認証済みユーザーのみアクセス可能
        user_context = request.state.user_context
        # ...
    ```
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # リクエストからトークン取得
            access_token = kwargs.get('access_token') or getattr(args[0], 'headers', {}).get('Authorization')
            if access_token and access_token.startswith('Bearer '):
                access_token = access_token[7:]
            
            user_context = await registry.authenticate_request(access_token)
            
            if registry._auth_enabled and not user_context:
                raise AuthError("Authentication required")
            
            # ユーザーコンテキストを関数に渡す
            kwargs['user_context'] = user_context
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(registry: AuthPortRegistry, resource: str, action: Permission):
    """
    権限必須デコレータ
    
    Claude Code実装時の使用例：
    ```python
    @require_permission(auth_registry, 'documents', Permission.WRITE)
    async def upload_document(request, user_context=None):
        # 文書書き込み権限必須
        # ...
    ```
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            user_context = kwargs.get('user_context')
            resource_id = kwargs.get('resource_id')
            
            authorized = await registry.authorize_action(
                user_context, resource, action, resource_id
            )
            
            if not authorized:
                raise AuthError(f"Permission denied: {resource}:{action.value}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ========================================
# Utility Functions for Claude Code
# ========================================

def create_default_permissions() -> Dict[UserRole, Dict[str, List[Permission]]]:
    """
    デフォルト権限マトリクス作成
    
    Claude Code実装時の注意：
    - 大学環境に適した権限設計
    - 最小権限の原則
    - 段階的権限昇格
    """
    return {
        UserRole.ADMIN: {
            'documents': [Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN],
            'search': [Permission.READ, Permission.ADMIN],
            'users': [Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN],
            'system': [Permission.READ, Permission.WRITE, Permission.ADMIN]
        },
        UserRole.FACULTY: {
            'documents': [Permission.READ, Permission.WRITE, Permission.DELETE, Permission.SHARE],
            'search': [Permission.READ],
            'users': [Permission.READ],
            'system': [Permission.READ]
        },
        UserRole.STUDENT: {
            'documents': [Permission.READ, Permission.WRITE],
            'search': [Permission.READ],
            'users': [],
            'system': []
        },
        UserRole.GUEST: {
            'documents': [Permission.READ],
            'search': [Permission.READ],
            'users': [],
            'system': []
        }
    }


async def setup_auth_system(
    config: AuthConfig,
    enable_auth: bool = True
) -> AuthPortRegistry:
    """
    認証システムセットアップヘルパー
    
    Claude Code実装時の使用例：
    ```python
    auth_config = AuthConfig(
        provider='google_oauth2',
        client_id='...',
        client_secret='...',
        redirect_uri='http://localhost:8000/auth/callback',
        allowed_domains=['university.ac.jp']
    )
    
    auth_registry = await setup_auth_system(auth_config, enable_auth=True)
    ```
    """
    registry = AuthPortRegistry()
    
    if enable_auth:
        # 各ポートの実装を設定から作成
        # (実際の実装は具体的なポート実装クラスで行う)
        pass
    
    registry.enable_authentication(enable_auth)
    return registry