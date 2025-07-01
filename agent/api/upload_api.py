"""
アップロードAPI
ファイルアップロードとデータ登録を統合したAPIエンドポイント
"""
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from ..data_management.data_manager import DataManager
from ..database_handler import DatabaseHandler


# Blueprintの作成
upload_api = Blueprint('upload_api', __name__)

# 設定
UPLOAD_FOLDER = 'agent/source/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'json', 'csv', 'md', 'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# グローバルなデータマネージャインスタンス
data_manager = None


def init_upload_api(db_handler: Optional[DatabaseHandler] = None):
    """
    APIの初期化
    
    Args:
        db_handler: データベースハンドラ
    """
    global data_manager
    data_manager = DataManager(db_handler)
    
    # アップロードフォルダの作成
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    """
    ファイルが許可された拡張子かチェック
    
    Args:
        filename: ファイル名
    
    Returns:
        許可されているかどうか
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@upload_api.route('/upload', methods=['POST'])
def upload_file():
    """
    ファイルをアップロードして登録
    
    Form Data:
        - file: アップロードするファイル（必須）
        - title: タイトル（オプション）
        - summary: 概要（オプション）
        - research_field: 研究分野（オプション）
        - auto_register: 自動的にデータベースに登録するか（デフォルト: true）
    
    Returns:
        アップロード結果
    """
    try:
        # ファイルの確認
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'ファイルが指定されていません'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'ファイルが選択されていません'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'許可されていないファイル形式です。許可: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # ファイルサイズチェック
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'success': False,
                'error': f'ファイルサイズが大きすぎます。最大: {MAX_FILE_SIZE // (1024*1024)}MB'
            }), 400
        
        # セキュアなファイル名を生成
        filename = secure_filename(file.filename)
        
        # ユニークなファイル名を生成（タイムスタンプとUUID）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}_{unique_id}{ext}"
        
        # ファイルを保存
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(file_path)
        
        result = {
            'success': True,
            'file_path': file_path,
            'original_filename': file.filename,
            'saved_filename': unique_filename,
            'file_size': file_size
        }
        
        # 自動登録が有効な場合
        auto_register = request.form.get('auto_register', 'true').lower() == 'true'
        
        if auto_register:
            # データベースに登録
            register_result = data_manager.register_data(
                file_path=file_path,
                title=request.form.get('title'),
                summary=request.form.get('summary'),
                research_field=request.form.get('research_field')
            )
            
            if register_result['success']:
                result['data_id'] = register_result['data_id']
                result['message'] = 'ファイルがアップロードされ、データベースに登録されました'
            else:
                result['warning'] = f'ファイルはアップロードされましたが、データベース登録に失敗: {register_result.get("error")}'
        else:
            result['message'] = 'ファイルがアップロードされました（データベース未登録）'
        
        return jsonify(result), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'アップロードエラー: {str(e)}'
        }), 500


@upload_api.route('/upload/multiple', methods=['POST'])
def upload_multiple_files():
    """
    複数ファイルを一括アップロード
    
    Form Data:
        - files: アップロードするファイル（複数）
        - research_field: 全ファイル共通の研究分野（オプション）
        - auto_register: 自動的にデータベースに登録するか（デフォルト: true）
    
    Returns:
        アップロード結果のサマリー
    """
    try:
        if 'files' not in request.files:
            return jsonify({
                'success': False,
                'error': 'ファイルが指定されていません'
            }), 400
        
        files = request.files.getlist('files')
        
        if not files:
            return jsonify({
                'success': False,
                'error': 'ファイルが選択されていません'
            }), 400
        
        results = {
            'total_files': len(files),
            'successful': 0,
            'failed': 0,
            'files': []
        }
        
        auto_register = request.form.get('auto_register', 'true').lower() == 'true'
        common_research_field = request.form.get('research_field')
        
        for file in files:
            if file.filename == '':
                results['failed'] += 1
                results['files'].append({
                    'filename': '',
                    'success': False,
                    'error': 'ファイル名が空です'
                })
                continue
            
            if not allowed_file(file.filename):
                results['failed'] += 1
                results['files'].append({
                    'filename': file.filename,
                    'success': False,
                    'error': '許可されていないファイル形式'
                })
                continue
            
            try:
                # ファイルサイズチェック
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_FILE_SIZE:
                    results['failed'] += 1
                    results['files'].append({
                        'filename': file.filename,
                        'success': False,
                        'error': 'ファイルサイズが大きすぎます'
                    })
                    continue
                
                # ファイル保存
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_id = str(uuid.uuid4())[:8]
                name, ext = os.path.splitext(filename)
                unique_filename = f"{name}_{timestamp}_{unique_id}{ext}"
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                
                file.save(file_path)
                
                file_result = {
                    'filename': file.filename,
                    'success': True,
                    'file_path': file_path,
                    'saved_filename': unique_filename
                }
                
                # 自動登録
                if auto_register:
                    register_result = data_manager.register_data(
                        file_path=file_path,
                        research_field=common_research_field
                    )
                    
                    if register_result['success']:
                        file_result['data_id'] = register_result['data_id']
                    else:
                        file_result['register_error'] = register_result.get('error')
                
                results['successful'] += 1
                results['files'].append(file_result)
                
            except Exception as e:
                results['failed'] += 1
                results['files'].append({
                    'filename': file.filename,
                    'success': False,
                    'error': str(e)
                })
        
        results['success'] = results['failed'] == 0
        
        return jsonify(results), 201 if results['successful'] > 0 else 400
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'一括アップロードエラー: {str(e)}'
        }), 500


@upload_api.route('/upload/url', methods=['POST'])
def upload_from_url():
    """
    URLからファイルをダウンロードして登録
    
    Request Body:
        - url: ダウンロードするURL（必須）
        - title: タイトル（オプション）
        - summary: 概要（オプション）
        - research_field: 研究分野（オプション）
    
    Returns:
        ダウンロード・登録結果
    """
    try:
        import requests
        from urllib.parse import urlparse
        
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'URLが指定されていません'
            }), 400
        
        url = data['url']
        
        # URLからファイル名を推定
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        
        if not filename:
            filename = 'downloaded_file'
        
        # ファイルをダウンロード
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Content-Typeから拡張子を推定
        content_type = response.headers.get('Content-Type', '')
        if 'json' in content_type:
            if not filename.endswith('.json'):
                filename += '.json'
        elif 'pdf' in content_type:
            if not filename.endswith('.pdf'):
                filename += '.pdf'
        elif 'text' in content_type:
            if not filename.endswith('.txt'):
                filename += '.txt'
        
        # ファイルを保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}_{unique_id}{ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # データベースに登録
        register_result = data_manager.register_data(
            file_path=file_path,
            title=data.get('title'),
            summary=data.get('summary'),
            research_field=data.get('research_field')
        )
        
        if register_result['success']:
            return jsonify({
                'success': True,
                'data_id': register_result['data_id'],
                'file_path': file_path,
                'original_url': url,
                'saved_filename': unique_filename,
                'message': 'URLからファイルをダウンロードし、データベースに登録しました'
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': f'ファイルはダウンロードされましたが、データベース登録に失敗: {register_result.get("error")}',
                'file_path': file_path
            }), 500
            
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'ダウンロードエラー: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'URLアップロードエラー: {str(e)}'
        }), 500


@upload_api.route('/upload/status', methods=['GET'])
def get_upload_status():
    """
    アップロードディレクトリの状態を取得
    
    Returns:
        ディレクトリ情報
    """
    try:
        # アップロードディレクトリの統計
        total_files = 0
        total_size = 0
        file_types = {}
        
        if os.path.exists(UPLOAD_FOLDER):
            for filename in os.listdir(UPLOAD_FOLDER):
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.isfile(file_path):
                    total_files += 1
                    file_size = os.path.getsize(file_path)
                    total_size += file_size
                    
                    # 拡張子別の集計
                    ext = os.path.splitext(filename)[1].lower()
                    if ext:
                        file_types[ext] = file_types.get(ext, 0) + 1
        
        return jsonify({
            'success': True,
            'upload_directory': UPLOAD_FOLDER,
            'total_files': total_files,
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'file_types': file_types,
            'allowed_extensions': list(ALLOWED_EXTENSIONS),
            'max_file_size_mb': MAX_FILE_SIZE // (1024 * 1024)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'状態取得エラー: {str(e)}'
        }), 500


# エラーハンドラ
@upload_api.errorhandler(413)
def request_entity_too_large(error):
    """ファイルサイズ超過エラー"""
    return jsonify({
        'success': False,
        'error': 'ファイルサイズが大きすぎます'
    }), 413


@upload_api.errorhandler(404)
def not_found(error):
    """404エラーハンドラ"""
    return jsonify({
        'success': False,
        'error': 'エンドポイントが見つかりません'
    }), 404


@upload_api.errorhandler(500)
def internal_error(error):
    """500エラーハンドラ"""
    return jsonify({
        'success': False,
        'error': '内部サーバーエラー'
    }), 500