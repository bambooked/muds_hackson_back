"""
API共通エラーハンドラ
エラー処理とレスポンス生成の統一化
"""
import traceback
import logging
from typing import Dict, Any, Optional
from flask import Blueprint, jsonify, request
from functools import wraps


# ロギング設定
logger = logging.getLogger(__name__)


class APIError(Exception):
    """カスタムAPIエラークラス"""
    
    def __init__(self, message: str, status_code: int = 400, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


class ValidationError(APIError):
    """バリデーションエラー"""
    
    def __init__(self, message: str, field_errors: Dict[str, str] = None):
        super().__init__(message, 400, 'VALIDATION_ERROR')
        self.field_errors = field_errors or {}


class NotFoundError(APIError):
    """リソースが見つからないエラー"""
    
    def __init__(self, message: str = 'リソースが見つかりません'):
        super().__init__(message, 404, 'NOT_FOUND')


class UnauthorizedError(APIError):
    """認証エラー"""
    
    def __init__(self, message: str = '認証が必要です'):
        super().__init__(message, 401, 'UNAUTHORIZED')


class ForbiddenError(APIError):
    """権限エラー"""
    
    def __init__(self, message: str = 'このリソースにアクセスする権限がありません'):
        super().__init__(message, 403, 'FORBIDDEN')


class RateLimitError(APIError):
    """レート制限エラー"""
    
    def __init__(self, message: str = 'リクエスト頻度が制限を超えています'):
        super().__init__(message, 429, 'RATE_LIMIT_EXCEEDED')


class InternalServerError(APIError):
    """内部サーバーエラー"""
    
    def __init__(self, message: str = '内部サーバーエラーが発生しました'):
        super().__init__(message, 500, 'INTERNAL_SERVER_ERROR')


def create_error_blueprint() -> Blueprint:
    """
    エラーハンドラ用のBlueprintを作成
    
    Returns:
        エラーハンドラが登録されたBlueprint
    """
    error_bp = Blueprint('error_handlers', __name__)
    
    @error_bp.errorhandler(APIError)
    def handle_api_error(error: APIError):
        """カスタムAPIエラーハンドラ"""
        response_data = {
            'success': False,
            'error': error.message,
            'error_code': error.error_code
        }
        
        # バリデーションエラーの場合はフィールドエラーも含める
        if isinstance(error, ValidationError) and error.field_errors:
            response_data['field_errors'] = error.field_errors
        
        return jsonify(response_data), error.status_code
    
    @error_bp.errorhandler(400)
    def handle_bad_request(error):
        """400エラーハンドラ"""
        return jsonify({
            'success': False,
            'error': 'リクエストが無効です',
            'error_code': 'BAD_REQUEST'
        }), 400
    
    @error_bp.errorhandler(404)
    def handle_not_found(error):
        """404エラーハンドラ"""
        return jsonify({
            'success': False,
            'error': 'エンドポイントが見つかりません',
            'error_code': 'NOT_FOUND'
        }), 404
    
    @error_bp.errorhandler(405)
    def handle_method_not_allowed(error):
        """405エラーハンドラ"""
        return jsonify({
            'success': False,
            'error': 'HTTPメソッドが許可されていません',
            'error_code': 'METHOD_NOT_ALLOWED'
        }), 405
    
    @error_bp.errorhandler(413)
    def handle_request_entity_too_large(error):
        """413エラーハンドラ（ファイルサイズ超過）"""
        return jsonify({
            'success': False,
            'error': 'リクエストサイズが大きすぎます',
            'error_code': 'REQUEST_TOO_LARGE'
        }), 413
    
    @error_bp.errorhandler(415)
    def handle_unsupported_media_type(error):
        """415エラーハンドラ"""
        return jsonify({
            'success': False,
            'error': 'サポートされていないメディアタイプです',
            'error_code': 'UNSUPPORTED_MEDIA_TYPE'
        }), 415
    
    @error_bp.errorhandler(429)
    def handle_rate_limit_exceeded(error):
        """429エラーハンドラ（レート制限）"""
        return jsonify({
            'success': False,
            'error': 'リクエスト頻度が制限を超えています',
            'error_code': 'RATE_LIMIT_EXCEEDED'
        }), 429
    
    @error_bp.errorhandler(500)
    def handle_internal_server_error(error):
        """500エラーハンドラ"""
        # エラーログを出力
        logger.error(f"Internal server error: {error}")
        
        return jsonify({
            'success': False,
            'error': '内部サーバーエラー',
            'error_code': 'INTERNAL_SERVER_ERROR'
        }), 500
    
    return error_bp


def handle_exceptions(f):
    """
    例外を統一的に処理するデコレータ
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except APIError:
            # カスタムAPIエラーはそのまま再発生
            raise
        except ValueError as e:
            # 値エラーはバリデーションエラーとして扱う
            raise ValidationError(str(e))
        except FileNotFoundError as e:
            # ファイルが見つからない場合
            raise NotFoundError(f'ファイルが見つかりません: {str(e)}')
        except PermissionError as e:
            # 権限エラー
            raise ForbiddenError(f'権限がありません: {str(e)}')
        except Exception as e:
            # その他の例外は内部サーバーエラーとして扱う
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise InternalServerError(f'予期しないエラーが発生しました: {str(e)}')
    
    return decorated_function


def log_api_error(error: Exception, request_data: Dict[str, Any] = None):
    """
    APIエラーをログに記録
    
    Args:
        error: 発生したエラー
        request_data: リクエストデータ
    """
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'endpoint': request.endpoint,
        'method': request.method,
        'url': request.url,
        'user_agent': request.headers.get('User-Agent'),
        'remote_addr': request.remote_addr
    }
    
    if request_data:
        error_info['request_data'] = request_data
    
    if isinstance(error, APIError):
        logger.warning(f"API Error: {error_info}")
    else:
        logger.error(f"Unexpected Error: {error_info}")
        logger.error(traceback.format_exc())


def create_standard_error_response(error_type: str, message: str, 
                                 status_code: int = 400, 
                                 additional_data: Dict[str, Any] = None) -> tuple:
    """
    標準的なエラーレスポンスを作成
    
    Args:
        error_type: エラータイプ
        message: エラーメッセージ
        status_code: HTTPステータスコード
        additional_data: 追加データ
    
    Returns:
        JSONレスポンスとステータスコードのタプル
    """
    response_data = {
        'success': False,
        'error': message,
        'error_code': error_type.upper()
    }
    
    if additional_data:
        response_data.update(additional_data)
    
    return jsonify(response_data), status_code


def validate_request_data(required_fields: list = None, 
                        optional_fields: list = None,
                        field_validators: Dict[str, callable] = None) -> callable:
    """
    リクエストデータを検証するデコレータ
    
    Args:
        required_fields: 必須フィールドのリスト
        optional_fields: オプションフィールドのリスト
        field_validators: フィールドごとのバリデータ関数
    
    Returns:
        デコレータ関数
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # リクエストデータを取得
                if request.method == 'POST':
                    data = request.get_json()
                    if data is None:
                        raise ValidationError('JSONデータが必要です')
                else:
                    data = request.args.to_dict()
                
                # 必須フィールドのチェック
                missing_fields = []
                if required_fields:
                    for field in required_fields:
                        if field not in data or not data[field]:
                            missing_fields.append(field)
                
                if missing_fields:
                    raise ValidationError(
                        f'必須フィールドが不足しています: {", ".join(missing_fields)}',
                        {field: f'{field}は必須です' for field in missing_fields}
                    )
                
                # フィールド別のバリデーション
                field_errors = {}
                if field_validators:
                    for field, validator in field_validators.items():
                        if field in data:
                            try:
                                validator(data[field])
                            except ValueError as e:
                                field_errors[field] = str(e)
                
                if field_errors:
                    raise ValidationError('バリデーションエラー', field_errors)
                
                # 無効なフィールドのチェック（オプション）
                if optional_fields is not None:
                    allowed_fields = set(required_fields or []) | set(optional_fields or [])
                    invalid_fields = set(data.keys()) - allowed_fields
                    if invalid_fields:
                        raise ValidationError(f'無効なフィールド: {", ".join(invalid_fields)}')
                
                return f(*args, **kwargs)
                
            except APIError:
                raise
            except Exception as e:
                log_api_error(e, data if 'data' in locals() else None)
                raise InternalServerError()
        
        return decorated_function
    return decorator


def handle_database_errors(f):
    """
    データベースエラーを処理するデコレータ
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_message = str(e).lower()
            
            if 'unique constraint' in error_message or 'duplicate' in error_message:
                raise ValidationError('データが既に存在します')
            elif 'foreign key constraint' in error_message:
                raise ValidationError('関連するデータが見つかりません')
            elif 'not null constraint' in error_message:
                raise ValidationError('必須項目が不足しています')
            elif 'check constraint' in error_message:
                raise ValidationError('データ形式が無効です')
            else:
                logger.error(f"Database error in {f.__name__}: {str(e)}")
                raise InternalServerError('データベースエラーが発生しました')
    
    return decorated_function


def create_success_response_with_metadata(data: Any, 
                                        metadata: Dict[str, Any] = None,
                                        status_code: int = 200) -> tuple:
    """
    メタデータ付きの成功レスポンスを作成
    
    Args:
        data: レスポンスデータ
        metadata: メタデータ
        status_code: HTTPステータスコード
    
    Returns:
        JSONレスポンスとステータスコードのタプル
    """
    response_data = {
        'success': True,
        'data': data
    }
    
    if metadata:
        response_data['metadata'] = metadata
    
    return jsonify(response_data), status_code