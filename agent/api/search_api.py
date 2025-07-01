"""
検索API
データ検索、フィルタリング、類似検索などのAPIエンドポイント
"""
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify
from ..search.search_engine import SearchEngine
from ..database_handler import DatabaseHandler


# Blueprintの作成
search_api = Blueprint('search_api', __name__)

# グローバルな検索エンジンインスタンス
search_engine = None


def init_search_api(db_handler: Optional[DatabaseHandler] = None):
    """
    APIの初期化
    
    Args:
        db_handler: データベースハンドラ
    """
    global search_engine
    search_engine = SearchEngine(db_handler)


@search_api.route('/search', methods=['GET', 'POST'])
def search():
    """
    データを検索するエンドポイント
    
    Query Parameters / Request Body:
        - query: 検索クエリ（オプション）
        - data_type: データタイプでフィルタ（オプション）
        - research_field: 研究分野でフィルタ（オプション）
        - sort_by: ソート基準（relevance, date, title）デフォルト: relevance
        - limit: 取得件数（デフォルト: 50）
        - offset: オフセット（デフォルト: 0）
    
    Returns:
        検索結果のJSON
    """
    try:
        # GETとPOSTの両方をサポート
        if request.method == 'POST':
            params = request.get_json() or {}
        else:
            params = request.args.to_dict()
        
        # パラメータの取得
        query = params.get('query')
        filters = {}
        
        if params.get('data_type'):
            filters['data_type'] = params['data_type']
        
        if params.get('research_field'):
            filters['research_field'] = params['research_field']
        
        # 数値パラメータの変換
        try:
            limit = int(params.get('limit', 50))
            offset = int(params.get('offset', 0))
        except ValueError:
            limit = 50
            offset = 0
        
        # 検索実行
        result = search_engine.search(
            query=query,
            filters=filters,
            sort_by=params.get('sort_by', 'relevance'),
            limit=limit,
            offset=offset
        )
        
        return jsonify({
            'success': True,
            'search_result': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'検索エラー: {str(e)}'
        }), 500


@search_api.route('/search/similar/<data_id>', methods=['GET'])
def get_similar(data_id: str):
    """
    類似データを取得
    
    Args:
        data_id: 基準となるデータID
    
    Query Parameters:
        - limit: 取得件数（デフォルト: 5）
    
    Returns:
        類似データのリスト
    """
    try:
        limit = int(request.args.get('limit', 5))
        
        similar_data = search_engine.get_similar_data(data_id, limit)
        
        if similar_data or similar_data == []:
            return jsonify({
                'success': True,
                'data_id': data_id,
                'similar_data': similar_data
            })
        else:
            return jsonify({
                'success': False,
                'error': '基準データが見つかりません'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'類似検索エラー: {str(e)}'
        }), 500


@search_api.route('/search/trending', methods=['GET'])
def get_trending():
    """
    トレンディングトピックを取得
    
    Query Parameters:
        - days: 過去何日間のデータを対象とするか（デフォルト: 7）
    
    Returns:
        トレンディングトピックのリスト
    """
    try:
        days = int(request.args.get('days', 7))
        
        trending = search_engine.get_trending_topics(days)
        
        return jsonify({
            'success': True,
            'days': days,
            'trending_topics': trending
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'トレンド取得エラー: {str(e)}'
        }), 500


@search_api.route('/search/history', methods=['GET'])
def get_search_history():
    """
    検索履歴を取得
    
    Query Parameters:
        - limit: 取得件数（デフォルト: 10）
    
    Returns:
        検索履歴のリスト
    """
    try:
        limit = int(request.args.get('limit', 10))
        
        history = search_engine.db_handler.get_search_history(limit)
        
        return jsonify({
            'success': True,
            'search_history': history
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'履歴取得エラー: {str(e)}'
        }), 500


@search_api.route('/search/facets', methods=['GET'])
def get_facets():
    """
    ファセット情報を取得（全データの集計）
    
    Returns:
        ファセット情報
    """
    try:
        # 全データを対象にファセット情報を生成
        all_data = search_engine.db_handler.search_data(limit=10000)
        facets = search_engine._generate_facets(all_data)
        
        return jsonify({
            'success': True,
            'facets': facets,
            'total_count': len(all_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'ファセット取得エラー: {str(e)}'
        }), 500


@search_api.route('/search/advanced', methods=['POST'])
def advanced_search():
    """
    高度な検索（複数条件の組み合わせ）
    
    Request Body:
        - queries: 検索条件のリスト
            - field: 検索対象フィールド（title, summary, research_field）
            - operator: 演算子（contains, equals, starts_with, ends_with）
            - value: 検索値
            - combine: 結合方法（AND, OR）デフォルト: AND
    
    Returns:
        検索結果
    """
    try:
        data = request.get_json()
        
        if not data or 'queries' not in data:
            return jsonify({
                'success': False,
                'error': 'queriesパラメータが必要です'
            }), 400
        
        # 検索条件を組み立て
        # 簡易実装：最初の条件のみ使用
        if data['queries']:
            first_query = data['queries'][0]
            query = first_query.get('value', '')
        else:
            query = ''
        
        # 通常の検索を実行
        result = search_engine.search(
            query=query,
            limit=data.get('limit', 50),
            offset=data.get('offset', 0)
        )
        
        # 追加の条件でフィルタリング（簡易実装）
        if len(data['queries']) > 1:
            # 複数条件がある場合の追加フィルタリング
            filtered_results = []
            for item in result['results']:
                match = True
                for condition in data['queries'][1:]:
                    field = condition.get('field')
                    operator = condition.get('operator', 'contains')
                    value = condition.get('value', '').lower()
                    
                    if field in item:
                        field_value = str(item[field]).lower()
                        
                        if operator == 'contains' and value not in field_value:
                            match = False
                        elif operator == 'equals' and field_value != value:
                            match = False
                        elif operator == 'starts_with' and not field_value.startswith(value):
                            match = False
                        elif operator == 'ends_with' and not field_value.endswith(value):
                            match = False
                
                if match:
                    filtered_results.append(item)
            
            result['results'] = filtered_results
            result['returned_count'] = len(filtered_results)
        
        return jsonify({
            'success': True,
            'search_result': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'高度検索エラー: {str(e)}'
        }), 500


# エラーハンドラ
@search_api.errorhandler(404)
def not_found(error):
    """404エラーハンドラ"""
    return jsonify({
        'success': False,
        'error': 'エンドポイントが見つかりません'
    }), 404


@search_api.errorhandler(500)
def internal_error(error):
    """500エラーハンドラ"""
    return jsonify({
        'success': False,
        'error': '内部サーバーエラー'
    }), 500