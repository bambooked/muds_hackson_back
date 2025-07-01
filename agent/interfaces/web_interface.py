"""
Webインターフェース
FlaskベースのWeb UIとAPIエンドポイントを提供
"""
from typing import Optional

try:
    from flask import Flask, jsonify, request, render_template_string
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None

from ..config import Config
from ..data_management.data_manager import DataManager
from ..search.search_engine import SearchEngine
from ..consultation.llm_advisor import LLMAdvisor
from ..consultation.recommender import DataRecommender


class WebInterface:
    """Webインターフェースを提供するクラス"""
    
    def __init__(self, data_manager: DataManager,
                 search_engine: SearchEngine,
                 advisor: LLMAdvisor,
                 recommender: DataRecommender,
                 config: Config):
        """
        Webインターフェースの初期化
        
        Args:
            data_manager: データマネージャ
            search_engine: 検索エンジン
            advisor: LLM研究相談アドバイザー
            recommender: データ推薦エンジン
            config: 設定オブジェクト
        """
        self.data_manager = data_manager
        self.search_engine = search_engine
        self.advisor = advisor
        self.recommender = recommender
        self.config = config
        self.app = None
    
    def create_app(self):
        """Flaskアプリケーションを作成"""
        if not FLASK_AVAILABLE:
            raise ImportError("Flask が利用できません。pip install flask でインストールしてください。")
        
        app = Flask(__name__)
        app.config['MAX_CONTENT_LENGTH'] = self.config.max_file_size
        
        # メインルート
        @app.route('/')
        def index():
            return render_template_string(self._get_main_template())
        
        # システム状態API
        @app.route('/api/system/status')
        def system_status():
            stats = self.data_manager.get_statistics()
            return jsonify({
                'success': True,
                'system': {
                    'name': self.config.system_name,
                    'version': self.config.system_version,
                    'status': 'running'
                },
                'database': stats
            })
        
        # 検索API
        @app.route('/api/search')
        def search():
            query = request.args.get('query', '')
            data_type = request.args.get('data_type')
            research_field = request.args.get('research_field')
            sort_by = request.args.get('sort_by', 'relevance')
            limit = int(request.args.get('limit', 20))
            offset = int(request.args.get('offset', 0))
            
            filters = {}
            if data_type:
                filters['data_type'] = data_type
            if research_field:
                filters['research_field'] = research_field
            
            results = self.search_engine.search(
                query=query,
                filters=filters,
                sort_by=sort_by,
                limit=limit,
                offset=offset
            )
            
            return jsonify({
                'success': True,
                'results': results
            })
        
        # 相談API
        @app.route('/api/consultation', methods=['POST'])
        def consultation():
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({
                    'success': False,
                    'error': 'クエリが必要です'
                }), 400
            
            result = self.advisor.consult(
                user_query=data['query'],
                consultation_type=data.get('type', 'general'),
                session_id=data.get('session_id'),
                user_id=data.get('user_id', 'web_user')
            )
            
            return jsonify({
                'success': True,
                'consultation': result
            })
        
        # チャットセッション管理API
        @app.route('/api/chat/sessions', methods=['POST'])
        def create_chat_session():
            data = request.get_json() or {}
            user_id = data.get('user_id', 'web_user')
            session_id = self.advisor.create_chat_session(user_id)
            
            return jsonify({
                'success': True,
                'session_id': session_id
            })
        
        @app.route('/api/chat/sessions/<session_id>/history')
        def get_chat_history(session_id):
            limit = int(request.args.get('limit', 20))
            history = self.advisor.get_chat_history(session_id, limit)
            
            return jsonify({
                'success': True,
                'session_id': session_id,
                'history': history
            })
        
        @app.route('/api/chat/sessions/<session_id>', methods=['DELETE'])
        def end_chat_session(session_id):
            success = self.advisor.end_chat_session(session_id)
            
            return jsonify({
                'success': success,
                'message': 'セッションを終了しました' if success else 'セッションが見つかりません'
            })
        
        @app.route('/api/chat/users/<user_id>/sessions')
        def get_user_sessions(user_id):
            limit = int(request.args.get('limit', 10))
            sessions = self.advisor.get_user_sessions(user_id, limit)
            
            return jsonify({
                'success': True,
                'user_id': user_id,
                'sessions': sessions
            })
        
        @app.route('/api/chat/statistics')
        def get_chat_statistics():
            stats = self.advisor.get_chat_statistics()
            
            return jsonify({
                'success': True,
                'statistics': stats
            })
        
        # 推薦API
        @app.route('/api/recommendations')
        def recommendations():
            rec_type = request.args.get('type', 'trending')
            limit = int(request.args.get('limit', 10))
            
            if rec_type == 'trending':
                recs = self.recommender.recommend_trending(limit=limit)
            elif rec_type == 'field':
                field = request.args.get('field')
                if not field:
                    return jsonify({'success': False, 'error': '分野の指定が必要です'}), 400
                recs = self.recommender.recommend_by_field(field, limit=limit)
            elif rec_type == 'type':
                data_type = request.args.get('data_type')
                if not data_type:
                    return jsonify({'success': False, 'error': 'データタイプの指定が必要です'}), 400
                recs = self.recommender.recommend_by_type(data_type, limit=limit)
            else:
                return jsonify({'success': False, 'error': '無効な推薦タイプです'}), 400
            
            return jsonify({
                'success': True,
                'recommendations': recs
            })
        
        # データ詳細API
        @app.route('/api/data/<data_id>')
        def get_data_detail(data_id):
            data = self.data_manager.get_data_info(data_id)
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
        
        # 類似データAPI
        @app.route('/api/similar/<data_id>')
        def get_similar_data(data_id):
            limit = int(request.args.get('limit', 5))
            similar_data = self.search_engine.get_similar_data(data_id, limit)
            
            return jsonify({
                'success': True,
                'data_id': data_id,
                'similar_data': similar_data
            })
        
        # トレンドAPI
        @app.route('/api/trending')
        def get_trending():
            days = int(request.args.get('days', 7))
            trending = self.search_engine.get_trending_topics(days)
            
            return jsonify({
                'success': True,
                'trending_topics': trending
            })
        
        # ファセットAPI
        @app.route('/api/facets')
        def get_facets():
            # 全データを対象にファセット情報を生成
            all_data = self.data_manager.search_data(limit=1000)
            facets = self.search_engine.result_processor.generate_facets(all_data)
            
            return jsonify({
                'success': True,
                'facets': facets
            })
        
        # エラーハンドラ
        @app.errorhandler(404)
        def not_found(error):
            return jsonify({
                'success': False,
                'error': 'エンドポイントが見つかりません'
            }), 404
        
        @app.errorhandler(500)
        def internal_error(error):
            return jsonify({
                'success': False,
                'error': '内部サーバーエラー'
            }), 500
        
        self.app = app
        return app
    
    def _get_main_template(self) -> str:
        """メインページのHTMLテンプレートを取得"""
        return """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ config.system_name }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
            color: white;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .main-content {
            background: white;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .search-section {
            margin-bottom: 40px;
        }
        
        .search-box {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .search-input {
            flex: 1;
            padding: 15px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 16px;
        }
        
        .search-btn {
            padding: 15px 30px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 16px;
            transition: background 0.3s;
        }
        
        .search-btn:hover {
            background: #5a67d8;
        }
        
        .filters {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .filter-group {
            display: flex;
            flex-direction: column;
        }
        
        .filter-group label {
            margin-bottom: 5px;
            font-weight: bold;
            color: #555;
        }
        
        .filter-group select {
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        
        .menu-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .menu-item {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            text-align: center;
            text-decoration: none;
            transition: transform 0.3s, box-shadow 0.3s;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .menu-item:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        }
        
        .menu-item h3 {
            margin-bottom: 10px;
            font-size: 1.5em;
        }
        
        .menu-item p {
            opacity: 0.9;
        }
        
        .results {
            margin-top: 30px;
        }
        
        .result-item {
            background: #f8f9fa;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }
        
        .result-title {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 5px;
            color: #333;
        }
        
        .result-meta {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
        }
        
        .result-summary {
            color: #555;
        }
        
        .api-info {
            margin-top: 40px;
            padding: 30px;
            background: #f8f9fa;
            border-radius: 15px;
        }
        
        .api-info h3 {
            margin-bottom: 20px;
            color: #333;
        }
        
        .api-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }
        
        .api-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }
        
        .api-method {
            font-weight: bold;
            color: #667eea;
        }
        
        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
        }
        
        .error {
            background: #fee;
            border: 1px solid #fcc;
            color: #c33;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .main-content {
                padding: 20px;
            }
            
            .search-box {
                flex-direction: column;
            }
            
            .filters {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔬 研究データ基盤システム</h1>
            <p>ローカルデータベースベースの研究データ管理・検索・相談システム</p>
        </div>
        
        <div class="main-content">
            <!-- 検索セクション -->
            <div class="search-section">
                <h2>🔍 データ検索</h2>
                <div class="search-box">
                    <input type="text" id="searchQuery" class="search-input" placeholder="キーワードを入力してください...">
                    <button onclick="performSearch()" class="search-btn">検索</button>
                </div>
                
                <div class="filters">
                    <div class="filter-group">
                        <label for="dataType">データタイプ</label>
                        <select id="dataType">
                            <option value="">すべて</option>
                            <option value="dataset">データセット</option>
                            <option value="paper">論文</option>
                            <option value="poster">ポスター</option>
                        </select>
                    </div>
                    
                    <div class="filter-group">
                        <label for="researchField">研究分野</label>
                        <select id="researchField">
                            <option value="">すべて</option>
                            <option value="機械学習">機械学習</option>
                            <option value="自然言語処理">自然言語処理</option>
                            <option value="コンピュータビジョン">コンピュータビジョン</option>
                            <option value="データサイエンス">データサイエンス</option>
                        </select>
                    </div>
                    
                    <div class="filter-group">
                        <label for="sortBy">ソート</label>
                        <select id="sortBy">
                            <option value="relevance">関連度</option>
                            <option value="date">更新日</option>
                            <option value="title">タイトル</option>
                        </select>
                    </div>
                </div>
                
                <div id="searchResults" class="results"></div>
            </div>
            
            <!-- メニューセクション -->
            <div class="menu-grid">
                <div class="menu-item" onclick="showSystemStatus()">
                    <h3>📊 システム状態</h3>
                    <p>データベースの統計情報と状態を確認</p>
                </div>
                
                <div class="menu-item" onclick="showTrending()">
                    <h3>📈 トレンドトピック</h3>
                    <p>最近注目されている研究分野</p>
                </div>
                
                <div class="menu-item" onclick="showRecommendations()">
                    <h3>💡 データ推薦</h3>
                    <p>あなたの研究に役立つデータを発見</p>
                </div>
                
                <div class="menu-item" onclick="showConsultation()">
                    <h3>🤖 AI相談</h3>
                    <p>研究相談とアドバイスを受ける</p>
                </div>
                
                <div class="menu-item" onclick="showChatConsultation()">
                    <h3>💬 チャット相談</h3>
                    <p>継続的な会話で研究相談</p>
                </div>
            </div>
            
            <!-- 結果表示エリア -->
            <div id="contentArea"></div>
            
            <!-- API情報 -->
            <div class="api-info">
                <h3>🔌 API エンドポイント</h3>
                <div class="api-list">
                    <div class="api-item">
                        <div class="api-method">GET</div>
                        <strong>/api/search</strong><br>
                        データ検索とフィルタリング
                    </div>
                    <div class="api-item">
                        <div class="api-method">GET</div>
                        <strong>/api/system/status</strong><br>
                        システム状態とデータベース統計
                    </div>
                    <div class="api-item">
                        <div class="api-method">POST</div>
                        <strong>/api/consultation</strong><br>
                        AI研究相談とアドバイス
                    </div>
                    <div class="api-item">
                        <div class="api-method">GET</div>
                        <strong>/api/recommendations</strong><br>
                        パーソナライズされたデータ推薦
                    </div>
                    <div class="api-item">
                        <div class="api-method">GET</div>
                        <strong>/api/similar/&lt;data_id&gt;</strong><br>
                        類似データの検索
                    </div>
                    <div class="api-item">
                        <div class="api-method">GET</div>
                        <strong>/api/trending</strong><br>
                        トレンディングトピック
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        async function performSearch() {
            const query = document.getElementById('searchQuery').value;
            const dataType = document.getElementById('dataType').value;
            const researchField = document.getElementById('researchField').value;
            const sortBy = document.getElementById('sortBy').value;
            
            const resultsDiv = document.getElementById('searchResults');
            resultsDiv.innerHTML = '<div class="loading">検索中...</div>';
            
            try {
                const params = new URLSearchParams({
                    query: query,
                    sort_by: sortBy,
                    limit: 10
                });
                
                if (dataType) params.append('data_type', dataType);
                if (researchField) params.append('research_field', researchField);
                
                const response = await fetch(`/api/search?${params}`);
                const data = await response.json();
                
                if (data.success) {
                    displaySearchResults(data.results);
                } else {
                    resultsDiv.innerHTML = `<div class="error">検索エラー: ${data.error}</div>`;
                }
            } catch (error) {
                resultsDiv.innerHTML = `<div class="error">通信エラー: ${error.message}</div>`;
            }
        }
        
        function displaySearchResults(results) {
            const resultsDiv = document.getElementById('searchResults');
            
            if (results.results.length === 0) {
                resultsDiv.innerHTML = '<div class="loading">検索結果が見つかりませんでした。</div>';
                return;
            }
            
            let html = `<h3>検索結果 (${results.returned_count}件)</h3>`;
            
            results.results.forEach(item => {
                html += `
                    <div class="result-item">
                        <div class="result-title">${item.title || '無題'}</div>
                        <div class="result-meta">
                            タイプ: ${item.data_type || 'N/A'} | 
                            分野: ${item.research_field || '未分類'} | 
                            ID: ${item.data_id}
                        </div>
                        <div class="result-summary">${item.summary || '概要なし'}</div>
                    </div>
                `;
            });
            
            resultsDiv.innerHTML = html;
        }
        
        async function showSystemStatus() {
            const contentArea = document.getElementById('contentArea');
            contentArea.innerHTML = '<div class="loading">読み込み中...</div>';
            
            try {
                const response = await fetch('/api/system/status');
                const data = await response.json();
                
                if (data.success) {
                    const stats = data.database;
                    let html = '<h3>📊 システム状態</h3>';
                    html += `<p>総データ数: ${stats.total_count}件</p>`;
                    
                    if (stats.type_counts) {
                        html += '<h4>データタイプ別</h4><ul>';
                        Object.entries(stats.type_counts).forEach(([type, count]) => {
                            html += `<li>${type}: ${count}件</li>`;
                        });
                        html += '</ul>';
                    }
                    
                    contentArea.innerHTML = html;
                } else {
                    contentArea.innerHTML = `<div class="error">エラー: ${data.error}</div>`;
                }
            } catch (error) {
                contentArea.innerHTML = `<div class="error">通信エラー: ${error.message}</div>`;
            }
        }
        
        async function showTrending() {
            const contentArea = document.getElementById('contentArea');
            contentArea.innerHTML = '<div class="loading">読み込み中...</div>';
            
            try {
                const response = await fetch('/api/trending');
                const data = await response.json();
                
                if (data.success) {
                    let html = '<h3>📈 トレンドトピック</h3>';
                    
                    if (data.trending_topics.length > 0) {
                        data.trending_topics.forEach(topic => {
                            html += `
                                <div class="result-item">
                                    <div class="result-title">${topic.topic}</div>
                                    <div class="result-meta">
                                        ${topic.count}件のデータ | 
                                        トレンドスコア: ${topic.trend_score.toFixed(1)}
                                    </div>
                                </div>
                            `;
                        });
                    } else {
                        html += '<p>トレンドデータがありません。</p>';
                    }
                    
                    contentArea.innerHTML = html;
                } else {
                    contentArea.innerHTML = `<div class="error">エラー: ${data.error}</div>`;
                }
            } catch (error) {
                contentArea.innerHTML = `<div class="error">通信エラー: ${error.message}</div>`;
            }
        }
        
        async function showRecommendations() {
            const contentArea = document.getElementById('contentArea');
            contentArea.innerHTML = '<div class="loading">読み込み中...</div>';
            
            try {
                const response = await fetch('/api/recommendations?type=trending');
                const data = await response.json();
                
                if (data.success) {
                    let html = '<h3>💡 推薦データ</h3>';
                    
                    data.recommendations.forEach(item => {
                        html += `
                            <div class="result-item">
                                <div class="result-title">${item.title || '無題'}</div>
                                <div class="result-meta">
                                    タイプ: ${item.data_type || 'N/A'} | 
                                    分野: ${item.research_field || '未分類'}
                                </div>
                                <div class="result-summary">
                                    推薦理由: ${item.recommendation_reason || 'N/A'}
                                </div>
                            </div>
                        `;
                    });
                    
                    contentArea.innerHTML = html;
                } else {
                    contentArea.innerHTML = `<div class="error">エラー: ${data.error}</div>`;
                }
            } catch (error) {
                contentArea.innerHTML = `<div class="error">通信エラー: ${error.message}</div>`;
            }
        }
        
        function showConsultation() {
            const contentArea = document.getElementById('contentArea');
            
            const html = `
                <h3>🤖 AI研究相談</h3>
                <div style="margin-bottom: 20px;">
                    <label for="consultationQuery" style="display: block; margin-bottom: 10px; font-weight: bold;">
                        相談内容を入力してください:
                    </label>
                    <textarea id="consultationQuery" 
                              style="width: 100%; height: 100px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;"
                              placeholder="例: 自然言語処理のデータセットを探しています"></textarea>
                </div>
                <div style="margin-bottom: 20px;">
                    <label for="consultationType" style="display: block; margin-bottom: 10px; font-weight: bold;">
                        相談タイプ:
                    </label>
                    <select id="consultationType" style="padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                        <option value="general">一般的な相談</option>
                        <option value="dataset">データセット相談</option>
                        <option value="idea">研究アイデア相談</option>
                    </select>
                </div>
                <button onclick="submitConsultation()" class="search-btn">相談する</button>
                <div id="consultationResult" style="margin-top: 20px;"></div>
            `;
            
            contentArea.innerHTML = html;
        }
        
        async function submitConsultation() {
            const query = document.getElementById('consultationQuery').value;
            const type = document.getElementById('consultationType').value;
            const resultDiv = document.getElementById('consultationResult');
            
            if (!query.trim()) {
                resultDiv.innerHTML = '<div class="error">相談内容を入力してください。</div>';
                return;
            }
            
            resultDiv.innerHTML = '<div class="loading">AI相談を処理中...</div>';
            
            try {
                const response = await fetch('/api/consultation', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        query: query,
                        type: type
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    const consultation = data.consultation;
                    let html = '<h4>💬 アドバイス</h4>';
                    html += `<div class="result-item">${consultation.advice}</div>`;
                    
                    if (consultation.recommendations && consultation.recommendations.length > 0) {
                        html += '<h4>📋 推薦データ</h4>';
                        consultation.recommendations.forEach(rec => {
                            html += `
                                <div class="result-item">
                                    <div class="result-title">${rec.title}</div>
                                    <div class="result-meta">
                                        タイプ: ${rec.data_type} | 分野: ${rec.research_field}
                                    </div>
                                    <div class="result-summary">理由: ${rec.reason}</div>
                                </div>
                            `;
                        });
                    }
                    
                    resultDiv.innerHTML = html;
                } else {
                    resultDiv.innerHTML = `<div class="error">相談エラー: ${data.error}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="error">通信エラー: ${error.message}</div>`;
            }
        }
        
        // チャット相談機能
        let currentChatSession = null;
        
        async function showChatConsultation() {
            const contentArea = document.getElementById('contentArea');
            
            const html = `
                <h3>💬 チャット相談</h3>
                <div style="margin-bottom: 20px;">
                    <button onclick="startNewChat()" class="search-btn" style="margin-right: 10px;">新しいチャット</button>
                    <button onclick="loadChatSessions()" class="search-btn">履歴から継続</button>
                </div>
                <div id="chatSessionsList" style="margin-bottom: 20px;"></div>
                <div id="chatArea" style="display: none;">
                    <div id="chatHistory" style="max-height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; background: #f9f9f9; border-radius: 8px;"></div>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="chatInput" placeholder="メッセージを入力..." style="flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                        <button onclick="sendChatMessage()" class="search-btn">送信</button>
                        <button onclick="endCurrentChat()" style="background: #dc3545; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer;">終了</button>
                    </div>
                    <div id="chatInfo" style="margin-top: 10px; color: #666; font-size: 0.9em;"></div>
                </div>
            `;
            
            contentArea.innerHTML = html;
            
            // Enterキーでメッセージ送信
            document.getElementById('chatInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendChatMessage();
                }
            });
        }
        
        async function startNewChat() {
            try {
                const response = await fetch('/api/chat/sessions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: 'web_user' })
                });
                
                const data = await response.json();
                if (data.success) {
                    currentChatSession = data.session_id;
                    showChatInterface();
                    addChatMessage('system', `新しいチャットセッションを開始しました (ID: ${currentChatSession.substring(0, 8)}...)`);
                } else {
                    alert('チャットセッションの作成に失敗しました: ' + data.error);
                }
            } catch (error) {
                alert('エラー: ' + error.message);
            }
        }
        
        async function loadChatSessions() {
            try {
                const response = await fetch('/api/chat/users/web_user/sessions');
                const data = await response.json();
                
                if (data.success && data.sessions.length > 0) {
                    let html = '<h4>既存のチャットセッション:</h4>';
                    data.sessions.forEach(session => {
                        const lastActivity = new Date(session.last_activity).toLocaleString();
                        const status = session.is_active ? 'アクティブ' : '終了済み';
                        html += `
                            <div style="border: 1px solid #ddd; padding: 10px; margin: 5px 0; border-radius: 5px; cursor: pointer;" 
                                 onclick="loadChatSession('${session.session_id}')">
                                <strong>セッション ${session.session_id.substring(0, 8)}...</strong><br>
                                最終活動: ${lastActivity} (${status})
                            </div>
                        `;
                    });
                    document.getElementById('chatSessionsList').innerHTML = html;
                } else {
                    document.getElementById('chatSessionsList').innerHTML = '<p>既存のセッションがありません。</p>';
                }
            } catch (error) {
                alert('セッション一覧の取得に失敗しました: ' + error.message);
            }
        }
        
        async function loadChatSession(sessionId) {
            try {
                const response = await fetch(`/api/chat/sessions/${sessionId}/history`);
                const data = await response.json();
                
                if (data.success) {
                    currentChatSession = sessionId;
                    showChatInterface();
                    
                    // 履歴を表示
                    data.history.forEach(msg => {
                        if (msg.type === 'user') {
                            addChatMessage('user', msg.content);
                        } else if (msg.type === 'assistant') {
                            const advice = msg.metadata?.advice || msg.content;
                            addChatMessage('assistant', advice);
                        }
                    });
                    
                    addChatMessage('system', `セッション ${sessionId.substring(0, 8)}... を継続しています`);
                } else {
                    alert('セッション履歴の読み込みに失敗しました: ' + data.error);
                }
            } catch (error) {
                alert('エラー: ' + error.message);
            }
        }
        
        function showChatInterface() {
            document.getElementById('chatSessionsList').style.display = 'none';
            document.getElementById('chatArea').style.display = 'block';
            document.getElementById('chatHistory').innerHTML = '';
            updateChatInfo();
        }
        
        function addChatMessage(type, content) {
            const chatHistory = document.getElementById('chatHistory');
            const timestamp = new Date().toLocaleTimeString();
            
            let messageClass = '';
            let sender = '';
            
            if (type === 'user') {
                messageClass = 'user-message';
                sender = 'あなた';
            } else if (type === 'assistant') {
                messageClass = 'ai-message';
                sender = 'AI';
            } else {
                messageClass = 'system-message';
                sender = 'システム';
            }
            
            const messageDiv = document.createElement('div');
            messageDiv.className = messageClass;
            messageDiv.style.cssText = `
                margin-bottom: 15px; 
                padding: 10px; 
                border-radius: 8px; 
                ${type === 'user' ? 'background: #007bff; color: white; margin-left: 20%;' : 
                  type === 'assistant' ? 'background: #f8f9fa; border-left: 4px solid #28a745;' : 
                  'background: #fff3cd; color: #856404; text-align: center;'}
            `;
            
            messageDiv.innerHTML = `
                <div style="font-size: 0.8em; opacity: 0.7; margin-bottom: 5px;">
                    ${sender} - ${timestamp}
                </div>
                <div>${content}</div>
            `;
            
            chatHistory.appendChild(messageDiv);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
        
        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            
            if (!message || !currentChatSession) return;
            
            // ユーザーメッセージを表示
            addChatMessage('user', message);
            input.value = '';
            
            // AI応答中表示
            addChatMessage('system', 'AI が回答を生成中...');
            
            try {
                const response = await fetch('/api/consultation', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: message,
                        type: 'general',
                        session_id: currentChatSession,
                        user_id: 'web_user'
                    })
                });
                
                const data = await response.json();
                
                // "AI が回答を生成中..." メッセージを削除
                const chatHistory = document.getElementById('chatHistory');
                chatHistory.removeChild(chatHistory.lastChild);
                
                if (data.success) {
                    const consultation = data.consultation;
                    
                    // AI応答を表示
                    addChatMessage('assistant', consultation.advice);
                    
                    // 追加情報があれば表示
                    if (consultation.search_suggestions && consultation.search_suggestions.length > 0) {
                        addChatMessage('system', `💡 検索のヒント: ${consultation.search_suggestions.slice(0, 3).join(', ')}`);
                    }
                    
                    updateChatInfo();
                } else {
                    addChatMessage('system', '❌ エラー: ' + data.error);
                }
            } catch (error) {
                // エラーメッセージを削除
                const chatHistory = document.getElementById('chatHistory');
                chatHistory.removeChild(chatHistory.lastChild);
                addChatMessage('system', '❌ 通信エラー: ' + error.message);
            }
        }
        
        async function endCurrentChat() {
            if (!currentChatSession) return;
            
            if (confirm('このチャットセッションを終了しますか？')) {
                try {
                    const response = await fetch(`/api/chat/sessions/${currentChatSession}`, {
                        method: 'DELETE'
                    });
                    
                    const data = await response.json();
                    if (data.success) {
                        addChatMessage('system', 'チャットセッションを終了しました');
                        currentChatSession = null;
                        setTimeout(() => {
                            showChatConsultation();
                        }, 2000);
                    }
                } catch (error) {
                    alert('セッション終了エラー: ' + error.message);
                }
            }
        }
        
        function updateChatInfo() {
            if (currentChatSession) {
                document.getElementById('chatInfo').innerHTML = 
                    `セッション ID: ${currentChatSession.substring(0, 8)}... | 'quit' や 'exit' で終了`;
            }
        }
        
        // エンターキーで検索
        document.getElementById('searchQuery').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
    </script>
</body>
</html>
        """
    
    def run(self, host: str = None, port: int = None, debug: bool = None):
        """Webサーバーを起動"""
        if not self.app:
            self.create_app()
        
        self.app.run(
            host=host or self.config.api_host,
            port=port or self.config.api_port,
            debug=debug if debug is not None else self.config.api_debug
        )