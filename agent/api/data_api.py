"""
データ操作API
データの登録、更新、削除、取得などのAPIエンドポイント
"""
from typing import Dict, Any, Optional
import json
from flask import Blueprint, request, jsonify
from ..data_management.data_manager import DataManager
from ..database_handler import DatabaseHandler


# Blueprintの作成
data_api = Blueprint('data_api', __name__)

# グローバルなデータマネージャインスタンス
data_manager = None


def init_data_api(db_handler: Optional[DatabaseHandler] = None):
    """
    APIの初期化
    
    Args:
        db_handler: データベースハンドラ
    """
    global data_manager
    data_manager = DataManager(db_handler)


@data_api.route('/data', methods=['POST'])
def register_data():
    """
    データを登録するエンドポイント
    
    Request Body:
        - file_path: ファイルパス（必須）
        - title: タイトル（オプション）
        - summary: 概要（オプション）
        - research_field: 研究分野（オプション）
    
    Returns:
        登録結果のJSON
    """
    try:
        data = request.get_json()
        
        if not data or 'file_path' not in data:
            return jsonify({
                'success': False,
                'error': 'file_pathは必須です'
            }), 400
        
        result = data_manager.register_data(
            file_path=data['file_path'],
            title=data.get('title'),
            summary=data.get('summary'),
            research_field=data.get('research_field')
        )
        
        status_code = 201 if result['success'] else 400
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'内部エラー: {str(e)}'
        }), 500


@data_api.route('/data/batch', methods=['POST'])
def register_directory():
    """
    ディレクトリ内のファイルを一括登録
    
    Request Body:
        - directory_path: ディレクトリパス（必須）
        - recursive: サブディレクトリも処理するか（デフォルト: true）
    
    Returns:
        登録結果のサマリー
    """
    try:
        data = request.get_json()
        
        if not data or 'directory_path' not in data:
            return jsonify({
                'success': False,
                'error': 'directory_pathは必須です'
            }), 400
        
        result = data_manager.register_directory(
            directory_path=data['directory_path'],
            recursive=data.get('recursive', True)
        )
        
        status_code = 201 if result['success'] else 400
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'内部エラー: {str(e)}'
        }), 500


@data_api.route('/data/<data_id>', methods=['GET'])
def get_data(data_id: str):
    """
    データの詳細を取得
    
    Args:
        data_id: データID
    
    Returns:
        データ情報のJSON
    """
    try:
        data = data_manager.get_data_info(data_id)
        
        if data:
            return jsonify({
                'success': True,
                'data': data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'データが見つかりません'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'内部エラー: {str(e)}'
        }), 500


@data_api.route('/data/<data_id>', methods=['PUT'])
def update_data(data_id: str):
    """
    データを更新
    
    Args:
        data_id: データID
    
    Request Body:
        更新するフィールド（title, summary, research_field, metadata）
    
    Returns:
        更新結果のJSON
    """
    try:
        updates = request.get_json()
        
        if not updates:
            return jsonify({
                'success': False,
                'error': '更新データが必要です'
            }), 400
        
        result = data_manager.update_data(data_id, updates)
        
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'内部エラー: {str(e)}'
        }), 500


@data_api.route('/data/<data_id>', methods=['DELETE'])
def delete_data(data_id: str):
    """
    データを削除
    
    Args:
        data_id: データID
    
    Query Parameters:
        - delete_file: 実ファイルも削除するか（デフォルト: false）
    
    Returns:
        削除結果のJSON
    """
    try:
        delete_file = request.args.get('delete_file', 'false').lower() == 'true'
        
        result = data_manager.delete_data(data_id, delete_file)
        
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'内部エラー: {str(e)}'
        }), 500


@data_api.route('/data/export', methods=['POST'])
def export_data():
    """
    データをエクスポート
    
    Request Body:
        - data_ids: エクスポートするデータIDのリスト（オプション、省略時は全データ）
        - format: エクスポート形式（json, csv）デフォルト: json
    
    Returns:
        エクスポート結果
    """
    try:
        data = request.get_json() or {}
        
        result = data_manager.export_data(
            data_ids=data.get('data_ids'),
            format=data.get('format', 'json')
        )
        
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'内部エラー: {str(e)}'
        }), 500


@data_api.route('/statistics', methods=['GET'])
def get_statistics():
    """
    システム統計を取得
    
    Returns:
        統計情報のJSON
    """
    try:
        stats = data_manager.get_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'内部エラー: {str(e)}'
        }), 500


@data_api.route('/backup', methods=['POST'])
def backup_database():
    """
    データベースのバックアップを作成
    
    Returns:
        バックアップ結果
    """
    try:
        result = data_manager.backup_database()
        
        status_code = 200 if result['success'] else 500
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'内部エラー: {str(e)}'
        }), 500


# エラーハンドラ
@data_api.errorhandler(404)
def not_found(error):
    """404エラーハンドラ"""
    return jsonify({
        'success': False,
        'error': 'エンドポイントが見つかりません'
    }), 404


@data_api.errorhandler(500)
def internal_error(error):
    """500エラーハンドラ"""
    return jsonify({
        'success': False,
        'error': '内部サーバーエラー'
    }), 500