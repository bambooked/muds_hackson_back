"""
研究データ基盤システム メインモジュール
コマンドライン&Webインターフェースの統合システム
"""
import os
import sys
from typing import Dict, Any, List, Optional

try:
    from flask import Flask, jsonify, request, render_template_string
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None

# システムモジュールのインポート
from .config import get_config
from .database_handler import DatabaseHandler
from .data_management.data_manager import DataManager
from .search.search_engine import SearchEngine
from .consultation.llm_advisor import LLMAdvisor
from .consultation.recommender import DataRecommender

# APIモジュールのインポート（Flaskが利用可能な場合のみ）
if FLASK_AVAILABLE:
    from .api.data_api import data_api, init_data_api
    from .api.search_api import search_api, init_search_api
    from .api.upload_api import upload_api, init_upload_api


class ResearchDataPlatform:
    """研究データ基盤システムのメインクラス"""
    
    def __init__(self):
        """システムの初期化"""
        self.config = get_config()
        
        # コアコンポーネントの初期化
        self.db_handler = DatabaseHandler(self.config.database_path)
        self.data_manager = DataManager(self.db_handler)
        self.search_engine = SearchEngine(self.db_handler)
        self.advisor = LLMAdvisor(self.db_handler, self.config)
        self.recommender = DataRecommender(self.db_handler)
        
        # Flaskアプリの設定
        self.app = None
    
    def setup_flask_app(self):
        """Flaskアプリケーションを設定"""
        if not FLASK_AVAILABLE:
            raise ImportError("Flask が利用できません。pip install flask でインストールしてください。")
        
        app = Flask(__name__)
        app.config['MAX_CONTENT_LENGTH'] = self.config.max_file_size
        
        # API Blueprintの登録
        init_data_api(self.db_handler)
        init_search_api(self.db_handler)
        init_upload_api(self.db_handler)
        
        app.register_blueprint(data_api, url_prefix='/api/data')
        app.register_blueprint(search_api, url_prefix='/api/search')
        app.register_blueprint(upload_api, url_prefix='/api/upload')
        
        # メインルート
        @app.route('/')
        def index():
            return render_template_string(self._get_web_template())
        
        # 統計エンドポイント
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
        
        # 相談エンドポイント
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
                consultation_type=data.get('type', 'general')
            )
            
            return jsonify({
                'success': True,
                'consultation': result
            })
        
        # 推薦エンドポイント
        @app.route('/api/recommendations', methods=['GET'])
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
        
        self.app = app
        return app
    
    def _get_web_template(self) -> str:
        """Webインターフェースのテンプレートを取得"""
        return """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ config.system_name }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .header { text-align: center; margin-bottom: 30px; }
        .menu { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
        .menu-item { border: 1px solid #ddd; padding: 20px; border-radius: 8px; text-align: center; }
        .menu-item h3 { margin-top: 0; color: #333; }
        .api-info { margin-top: 30px; padding: 20px; background: #f5f5f5; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>研究データ基盤システム</h1>
        <p>ローカルデータベースベースの研究データ管理・検索・相談システム</p>
    </div>
    
    <div class="menu">
        <div class="menu-item">
            <h3>📊 データ統計</h3>
            <p><a href="/api/system/status">システム状態</a></p>
        </div>
        <div class="menu-item">
            <h3>🔍 データ検索</h3>
            <p><a href="/api/search">検索API</a></p>
        </div>
        <div class="menu-item">
            <h3>📁 データ管理</h3>
            <p><a href="/api/data">データAPI</a></p>
        </div>
        <div class="menu-item">
            <h3>⬆️ ファイルアップロード</h3>
            <p><a href="/api/upload">アップロードAPI</a></p>
        </div>
    </div>
    
    <div class="api-info">
        <h3>API エンドポイント</h3>
        <ul>
            <li><strong>GET /api/system/status</strong> - システム状態</li>
            <li><strong>GET /api/search</strong> - データ検索</li>
            <li><strong>POST /api/data</strong> - データ登録</li>
            <li><strong>POST /api/upload</strong> - ファイルアップロード</li>
            <li><strong>POST /api/consultation</strong> - 研究相談</li>
            <li><strong>GET /api/recommendations</strong> - データ推薦</li>
        </ul>
    </div>
</body>
</html>
        """
    
    def run_cli_interface(self):
        """コマンドラインインターフェースを実行"""
        # 改善されたCLIインターフェースを使用
        from .interfaces.cli_interface import CLIInterface
        cli = CLIInterface(self.data_manager, self.search_engine, self.advisor, self.config)
        cli.run()
    
    def _display_main_menu(self):
        """メインメニューを表示"""
        print("\n" + "=" * 50)
        print(f"    {self.config.system_name}")
        print("=" * 50)
        print("1. データを探す")
        print("2. データを登録する")
        print("3. データを管理する") 
        print("4. 研究相談をする")
        print("5. システム統計を見る")
        print("6. 終了")
        print("=" * 50)
    
    def _handle_search(self):
        """検索機能の処理"""
        print("\n--- データ検索 ---")
        query = input("検索キーワードを入力: ").strip()
        
        if query:
            results = self.search_engine.search(query, limit=10)
            
            if results['results']:
                print(f"\n{results['returned_count']}件見つかりました:")
                for i, data in enumerate(results['results'], 1):
                    print(f"\n{i}. {data.get('title', '無題')}")
                    print(f"   タイプ: {data.get('data_type', '不明')}")
                    print(f"   分野: {data.get('research_field', '未分類')}")
                    print(f"   概要: {data.get('summary', '')[:100]}...")
            else:
                print("該当するデータが見つかりませんでした。")
        else:
            print("キーワードが入力されませんでした。")
    
    def _handle_data_registration(self):
        """データ登録機能の処理"""
        print("\n--- データ登録 ---")
        print("1. 単一ファイルを登録")
        print("2. ディレクトリを一括登録")
        
        choice = input("選択 (1-2): ").strip()
        
        if choice == '1':
            file_path = input("ファイルパス: ").strip()
            if file_path:
                result = self.data_manager.register_data(file_path)
                if result['success']:
                    print(f"✓ 登録完了: {result['data_id']}")
                else:
                    print(f"✗ 登録失敗: {result['error']}")
        
        elif choice == '2':
            dir_path = input("ディレクトリパス: ").strip()
            if dir_path:
                result = self.data_manager.register_directory(dir_path)
                print(f"処理結果: 成功{result['successful']}件 / 失敗{result['failed']}件")
    
    def _handle_data_management(self):
        """データ管理機能の処理"""
        print("\n--- データ管理 ---")
        print("1. データの詳細表示")
        print("2. データの更新")
        print("3. データの削除")
        print("4. データのエクスポート")
        
        choice = input("選択 (1-4): ").strip()
        
        if choice == '1':
            data_id = input("データID: ").strip()
            data = self.data_manager.get_data_info(data_id)
            if data:
                print(f"\nタイトル: {data.get('title')}")
                print(f"タイプ: {data.get('data_type')}")
                print(f"分野: {data.get('research_field')}")
                print(f"概要: {data.get('summary')}")
                print(f"ファイル: {data.get('file_path')}")
            else:
                print("データが見つかりません。")
        
        elif choice == '4':
            format_type = input("エクスポート形式 (json/csv): ").strip()
            result = self.data_manager.export_data(format=format_type)
            if result['success']:
                print(f"✓ エクスポート完了: {result['export_path']}")
            else:
                print(f"✗ エクスポート失敗: {result['error']}")
    
    def _handle_consultation(self):
        """研究相談機能の処理"""
        print("\n--- 研究相談 ---")
        print("何をお探しですか？")
        print("1. データセット")
        print("2. 研究アイデア（論文・ポスター）")
        print("3. 一般的な相談")
        
        choice = input("選択 (1-3): ").strip()
        
        types = {'1': 'dataset', '2': 'idea', '3': 'general'}
        consultation_type = types.get(choice, 'general')
        
        query = input("相談内容を入力: ").strip()
        
        if query:
            print("LLMが相談に回答しています...")
            result = self.advisor.consult(query, consultation_type)
            
            print(f"\n【AI相談アドバイス】")
            print(result['advice'])
            
            if result.get('recommendations'):
                print(f"\n【推薦データ】")
                for i, rec in enumerate(result['recommendations'], 1):
                    print(f"{i}. {rec.get('title', '無題')}")
                    if rec.get('reason'):
                        print(f"   理由: {rec['reason']}")
            
            if result.get('search_suggestions'):
                print(f"\n【検索のヒント】")
                for suggestion in result['search_suggestions']:
                    print(f"  - {suggestion}")
            
            if result.get('research_direction'):
                print(f"\n【研究の方向性】")
                print(result['research_direction'])
    
    def _handle_statistics(self):
        """統計表示機能の処理"""
        print("\n--- システム統計 ---")
        stats = self.data_manager.get_statistics()
        
        print(f"総データ数: {stats['total_count']}")
        print(f"\nデータタイプ別:")
        for dtype, count in stats['type_counts'].items():
            print(f"  {dtype}: {count}件")
        
        print(f"\n研究分野別 (上位5位):")
        for field, count in list(stats['field_counts'].items())[:5]:
            print(f"  {field}: {count}件")
    
    def initialize_with_existing_data(self, data_directory: str = "data"):
        """既存のデータディレクトリをインデックス化"""
        if os.path.exists(data_directory):
            print(f"\n既存データの初期化を開始: {data_directory}")
            result = self.data_manager.register_directory(data_directory, recursive=True)
            print(f"初期化完了: 成功{result['successful']}件 / 失敗{result['failed']}件")
            
            if result['errors']:
                print("\nエラー:")
                for error in result['errors'][:5]:  # 最初の5個のエラーのみ表示
                    print(f"  - {error}")
        else:
            print(f"データディレクトリが見つかりません: {data_directory}")


def main():
    """メイン関数"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        platform = ResearchDataPlatform()
        
        if command == 'web':
            # Webサーバーモードで起動
            if not FLASK_AVAILABLE:
                print("エラー: Webサーバーモードには Flask が必要です。")
                print("pip install flask でインストールしてください。")
                return
            
            print(f"\n{platform.config.system_name} Webサーバーを起動中...")
            platform.config.display_config()
            
            app = platform.setup_flask_app()
            app.run(
                host=platform.config.api_host,
                port=platform.config.api_port,
                debug=platform.config.api_debug
            )
        
        elif command == 'init':
            # 既存データの初期化
            data_dir = sys.argv[2] if len(sys.argv) > 2 else "data"
            platform.initialize_with_existing_data(data_dir)
        
        elif command == 'config':
            # 設定表示
            platform.config.display_config()
        
        else:
            print(f"不明なコマンド: {command}")
            print("使用法: python -m agent.main [web|init|config] [data_directory]")
    
    else:
        # CLIモードで起動
        platform = ResearchDataPlatform()
        platform.config.display_config()
        
        # 既存データの初期化確認
        if os.path.exists("data"):
            init_choice = input("\n既存のdataディレクトリを初期化しますか？ (y/n): ")
            if init_choice.lower() == 'y':
                platform.initialize_with_existing_data()
        
        platform.run_cli_interface()


if __name__ == "__main__":
    main()