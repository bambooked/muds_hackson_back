"""
API共通ユーティリティ
レスポンス作成、パラメータ解析、バリデーションなどの共通処理
"""
from typing import Dict, Any, Optional, List, Union
from flask import request, jsonify
from functools import wraps
import re


def create_success_response(data: Any, status_code: int = 200) -> tuple:
    """
    成功レスポンスを作成
    
    Args:
        data: レスポンスデータ
        status_code: HTTPステータスコード
    
    Returns:
        JSONレスポンスとステータスコードのタプル
    """
    return jsonify({
        'success': True,
        'data': data
    }), status_code


def create_error_response(error_message: str, status_code: int = 400) -> tuple:
    """
    エラーレスポンスを作成
    
    Args:
        error_message: エラーメッセージ
        status_code: HTTPステータスコード
    
    Returns:
        JSONレスポンスとステータスコードのタプル
    """
    return jsonify({
        'success': False,
        'error': error_message
    }), status_code


def create_validation_error_response(validation_errors: Dict[str, str]) -> tuple:
    """
    バリデーションエラーレスポンスを作成
    
    Args:
        validation_errors: フィールド名とエラーメッセージの辞書
    
    Returns:
        JSONレスポンスとステータスコードのタプル
    """
    return jsonify({
        'success': False,
        'error': 'バリデーションエラー',
        'validation_errors': validation_errors
    }), 400


def get_request_data() -> Dict[str, Any]:
    """
    リクエストからデータを取得（GET/POST両対応）
    
    Returns:
        リクエストデータの辞書
    """
    if request.method == 'POST':
        return request.get_json() or {}
    else:
        return request.args.to_dict()


def parse_int_param(value: Any, default: int = 0, min_value: int = 0, max_value: int = None) -> int:
    """
    パラメータを整数として解析
    
    Args:
        value: 解析する値
        default: デフォルト値
        min_value: 最小値
        max_value: 最大値
    
    Returns:
        解析された整数値
    """
    try:
        parsed_value = int(value)
        
        if parsed_value < min_value:
            return min_value
        
        if max_value is not None and parsed_value > max_value:
            return max_value
        
        return parsed_value
    except (ValueError, TypeError):
        return default


def parse_bool_param(value: Any, default: bool = False) -> bool:
    """
    パラメータをブール値として解析
    
    Args:
        value: 解析する値
        default: デフォルト値
    
    Returns:
        解析されたブール値
    """
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'yes', 'on']
    
    return default


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> Dict[str, str]:
    """
    必須フィールドの検証
    
    Args:
        data: 検証するデータ
        required_fields: 必須フィールドのリスト
    
    Returns:
        バリデーションエラーの辞書（エラーがない場合は空辞書）
    """
    errors = {}
    
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            errors[field] = f'{field}は必須です'
    
    return errors


def validate_string_length(value: str, field_name: str, max_length: int = None, min_length: int = 0) -> Optional[str]:
    """
    文字列の長さを検証
    
    Args:
        value: 検証する文字列
        field_name: フィールド名
        max_length: 最大長
        min_length: 最小長
    
    Returns:
        エラーメッセージ（エラーがない場合はNone）
    """
    if not isinstance(value, str):
        return f'{field_name}は文字列である必要があります'
    
    if len(value) < min_length:
        return f'{field_name}は{min_length}文字以上である必要があります'
    
    if max_length and len(value) > max_length:
        return f'{field_name}は{max_length}文字以下である必要があります'
    
    return None


def validate_email(email: str) -> bool:
    """
    メールアドレスの形式を検証
    
    Args:
        email: 検証するメールアドレス
    
    Returns:
        有効な形式の場合True
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """
    ファイル拡張子の検証
    
    Args:
        filename: ファイル名
        allowed_extensions: 許可された拡張子のセット
    
    Returns:
        許可された拡張子の場合True
    """
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in allowed_extensions


def sanitize_filename(filename: str) -> str:
    """
    ファイル名のサニタイズ
    
    Args:
        filename: 元のファイル名
    
    Returns:
        サニタイズされたファイル名
    """
    # 危険な文字を除去
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # 連続するアンダースコアを単一に
    filename = re.sub(r'_+', '_', filename)
    
    # 前後の空白とアンダースコアを除去
    filename = filename.strip(' _')
    
    # 空の場合はデフォルト名
    if not filename:
        filename = 'untitled'
    
    return filename


def paginate_results(results: List[Any], limit: int, offset: int) -> Dict[str, Any]:
    """
    結果をページ分割
    
    Args:
        results: 結果のリスト
        limit: 1ページあたりの件数
        offset: オフセット
    
    Returns:
        ページ分割情報を含む辞書
    """
    total_count = len(results)
    paginated_results = results[offset:offset + limit]
    
    return {
        'results': paginated_results,
        'pagination': {
            'total_count': total_count,
            'returned_count': len(paginated_results),
            'limit': limit,
            'offset': offset,
            'has_next': offset + limit < total_count,
            'has_previous': offset > 0
        }
    }


def extract_filters_from_request(allowed_filters: List[str]) -> Dict[str, Any]:
    """
    リクエストからフィルター条件を抽出
    
    Args:
        allowed_filters: 許可されたフィルターフィールドのリスト
    
    Returns:
        フィルター条件の辞書
    """
    data = get_request_data()
    filters = {}
    
    for field in allowed_filters:
        if field in data and data[field]:
            filters[field] = data[field]
    
    return filters


def standardize_response_format(result: Dict[str, Any], data_key: str = None) -> Dict[str, Any]:
    """
    レスポンス形式を標準化
    
    Args:
        result: 元の結果
        data_key: データキー名（指定された場合、resultをそのキーでラップ）
    
    Returns:
        標準化されたレスポンス
    """
    if 'success' not in result:
        result['success'] = True
    
    if data_key and data_key not in result:
        # 既存のデータを指定されたキーでラップ
        data = {k: v for k, v in result.items() if k != 'success'}
        result = {'success': result['success'], data_key: data}
    
    return result


def require_json_content_type(f):
    """
    JSON Content-Typeを必須とするデコレータ
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return create_error_response(
                'Content-Type must be application/json'
            )
        return f(*args, **kwargs)
    return decorated_function


def validate_api_key(api_key: str, valid_keys: set) -> bool:
    """
    APIキーの検証
    
    Args:
        api_key: 検証するAPIキー
        valid_keys: 有効なAPIキーのセット
    
    Returns:
        有効なAPIキーの場合True
    """
    return api_key in valid_keys


def rate_limit_key_generator(identifier: str = None) -> str:
    """
    レート制限用のキーを生成
    
    Args:
        identifier: 識別子（指定されない場合はIPアドレスを使用）
    
    Returns:
        レート制限キー
    """
    if identifier:
        return f"rate_limit:{identifier}"
    
    # クライアントIPアドレスを取得
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    return f"rate_limit:{client_ip}"


def format_file_size(size_bytes: int) -> str:
    """
    ファイルサイズを人間が読みやすい形式にフォーマット
    
    Args:
        size_bytes: バイト単位のサイズ
    
    Returns:
        フォーマットされたサイズ文字列
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def clean_dict(data: Dict[str, Any], remove_none: bool = True, remove_empty: bool = False) -> Dict[str, Any]:
    """
    辞書をクリーンアップ
    
    Args:
        data: クリーンアップする辞書
        remove_none: None値を除去するか
        remove_empty: 空文字列を除去するか
    
    Returns:
        クリーンアップされた辞書
    """
    cleaned = {}
    
    for key, value in data.items():
        if remove_none and value is None:
            continue
        
        if remove_empty and value == '':
            continue
        
        cleaned[key] = value
    
    return cleaned