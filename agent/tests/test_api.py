"""
API機能のテスト
"""
import tempfile
import os
import json
import pytest

# Flaskのインポート（利用可能な場合のみ）
try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None

# Flaskが利用できない場合はテストをスキップ
pytest_mark_skipif_no_flask = pytest.mark.skipif(
    not FLASK_AVAILABLE, 
    reason="Flask not available"
)

from agent.database_handler import DatabaseHandler

if FLASK_AVAILABLE:
    from agent.api.data_api import data_api, init_data_api
    from agent.api.search_api import search_api, init_search_api


@pytest_mark_skipif_no_flask
class TestDataAPI:
    """データAPIのテストクラス"""
    
    @pytest.fixture
    def app(self):
        """テスト用Flaskアプリ"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        # テスト用データベース
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db_handler = DatabaseHandler(db_path)
        
        # APIの初期化
        init_data_api(db_handler)
        app.register_blueprint(data_api, url_prefix='/api/data')
        
        yield app
        
        # クリーンアップ
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def client(self, app):
        """テスト用クライアント"""
        return app.test_client()
    
    @pytest.fixture
    def temp_test_file(self):
        """テスト用ファイル"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            test_data = {
                'title': 'テストデータセット',
                'description': 'API テスト用データ',
                'data': [{'id': 1, 'value': 'test'}]
            }
            json.dump(test_data, f, ensure_ascii=False)
            file_path = f.name
        
        yield file_path
        
        # クリーンアップ
        if os.path.exists(file_path):
            os.unlink(file_path)
    
    def test_register_data(self, client, temp_test_file):
        """データ登録APIのテスト"""
        # データ登録リクエスト
        response = client.post('/api/data', 
                              json={
                                  'file_path': temp_test_file,
                                  'title': 'APIテストデータ',
                                  'research_field': '機械学習'
                              })
        
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data_id' in data
    
    def test_register_data_missing_file_path(self, client):
        """ファイルパス未指定でのデータ登録テスト"""
        response = client.post('/api/data', json={})
        
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'file_pathは必須です' in data['error']
    
    def test_get_data(self, client, temp_test_file):
        """データ取得APIのテスト"""
        # まずデータを登録
        register_response = client.post('/api/data',
                                       json={'file_path': temp_test_file})
        
        register_data = json.loads(register_response.data)
        data_id = register_data['data_id']
        
        # データ取得
        response = client.get(f'/api/data/{data_id}')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'data' in data
        assert data['data']['data_id'] == data_id
    
    def test_get_nonexistent_data(self, client):
        """存在しないデータの取得テスト"""
        response = client.get('/api/data/nonexistent_id')
        
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_update_data(self, client, temp_test_file):
        """データ更新APIのテスト"""
        # まずデータを登録
        register_response = client.post('/api/data',
                                       json={'file_path': temp_test_file})
        
        register_data = json.loads(register_response.data)
        data_id = register_data['data_id']
        
        # データ更新
        update_data = {
            'title': '更新されたタイトル',
            'summary': '更新された概要'
        }
        
        response = client.put(f'/api/data/{data_id}', json=update_data)
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
    
    def test_delete_data(self, client, temp_test_file):
        """データ削除APIのテスト"""
        # まずデータを登録
        register_response = client.post('/api/data',
                                       json={'file_path': temp_test_file})
        
        register_data = json.loads(register_response.data)
        data_id = register_data['data_id']
        
        # データ削除
        response = client.delete(f'/api/data/{data_id}')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        
        # 削除確認
        get_response = client.get(f'/api/data/{data_id}')
        assert get_response.status_code == 404
    
    def test_get_statistics(self, client, temp_test_file):
        """統計取得APIのテスト"""
        # テストデータを登録
        client.post('/api/data', json={'file_path': temp_test_file})
        
        # 統計取得
        response = client.get('/api/statistics')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'statistics' in data
        assert 'total_count' in data['statistics']
        assert data['statistics']['total_count'] >= 1
    
    def test_export_data(self, client, temp_test_file):
        """データエクスポートAPIのテスト"""
        # テストデータを登録
        client.post('/api/data', json={'file_path': temp_test_file})
        
        # エクスポート
        response = client.post('/api/data/export',
                              json={'format': 'json'})
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'export_path' in data
        assert data['count'] >= 1


@pytest_mark_skipif_no_flask
class TestSearchAPI:
    """検索APIのテストクラス"""
    
    @pytest.fixture
    def app(self):
        """テスト用Flaskアプリ"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        # テスト用データベース
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        db_handler = DatabaseHandler(db_path)
        
        # テストデータの挿入
        test_data = [
            {
                'data_id': 'test_001',
                'data_type': 'dataset',
                'title': '機械学習データセット',
                'summary': '機械学習用データセット',
                'research_field': '機械学習'
            },
            {
                'data_id': 'test_002',
                'data_type': 'paper',
                'title': '深層学習の研究',
                'summary': '深層学習に関する論文',
                'research_field': '機械学習'
            }
        ]
        
        for data in test_data:
            db_handler.insert_data(data)
        
        # APIの初期化
        init_search_api(db_handler)
        app.register_blueprint(search_api, url_prefix='/api/search')
        
        yield app
        
        # クリーンアップ
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def client(self, app):
        """テスト用クライアント"""
        return app.test_client()
    
    def test_search_get(self, client):
        """GET検索APIのテスト"""
        response = client.get('/api/search?query=機械学習')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'search_result' in data
        assert 'results' in data['search_result']
        assert len(data['search_result']['results']) > 0
    
    def test_search_post(self, client):
        """POST検索APIのテスト"""
        search_data = {
            'query': '機械学習',
            'data_type': 'dataset',
            'limit': 10
        }
        
        response = client.post('/api/search', json=search_data)
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'search_result' in data
    
    def test_search_with_filters(self, client):
        """フィルタ付き検索APIのテスト"""
        response = client.get('/api/search?data_type=dataset&research_field=機械学習')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        
        # フィルタが適用されていることを確認
        for result in data['search_result']['results']:
            if 'data_type' in result:
                assert result['data_type'] == 'dataset'
    
    def test_similar_search(self, client):
        """類似検索APIのテスト"""
        response = client.get('/api/search/similar/test_001')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'similar_data' in data
        assert data['data_id'] == 'test_001'
    
    def test_similar_search_nonexistent(self, client):
        """存在しないデータの類似検索テスト"""
        response = client.get('/api/search/similar/nonexistent_id')
        
        # 成功だが空の結果が返される
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['similar_data'] == []
    
    def test_trending_search(self, client):
        """トレンド検索APIのテスト"""
        response = client.get('/api/search/trending?days=30')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'trending_topics' in data
        assert data['days'] == 30
    
    def test_search_history(self, client):
        """検索履歴APIのテスト"""
        # まず検索を実行して履歴を作成
        client.get('/api/search?query=テスト検索')
        
        # 履歴取得
        response = client.get('/api/search/history')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'search_history' in data
    
    def test_facets(self, client):
        """ファセット取得APIのテスト"""
        response = client.get('/api/search/facets')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'facets' in data
        assert 'data_type' in data['facets']
        assert 'research_field' in data['facets']
    
    def test_advanced_search(self, client):
        """高度な検索APIのテスト"""
        search_data = {
            'queries': [
                {
                    'field': 'title',
                    'operator': 'contains',
                    'value': '機械学習'
                }
            ]
        }
        
        response = client.post('/api/search/advanced', json=search_data)
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'search_result' in data
    
    def test_advanced_search_missing_queries(self, client):
        """クエリなしの高度な検索テスト"""
        response = client.post('/api/search/advanced', json={})
        
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'queriesパラメータが必要です' in data['error']


@pytest_mark_skipif_no_flask
class TestErrorHandling:
    """エラーハンドリングのテストクラス"""
    
    @pytest.fixture
    def app(self):
        """テスト用Flaskアプリ"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        # 無効なパスでデータベースハンドラを作成（エラーテスト用）
        db_handler = DatabaseHandler('/invalid/path/test.db')
        
        init_data_api(db_handler)
        app.register_blueprint(data_api, url_prefix='/api/data')
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """テスト用クライアント"""
        return app.test_client()
    
    def test_404_error(self, client):
        """404エラーのテスト"""
        response = client.get('/api/data/nonexistent/endpoint')
        
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_malformed_json(self, client):
        """不正なJSONのテスト"""
        response = client.post('/api/data',
                              data='invalid json',
                              content_type='application/json')
        
        assert response.status_code == 400


if __name__ == '__main__':
    pytest.main([__file__])