"""
PaaS統合テスト

RAGインターフェースとPaaS APIの動作確認用テストスクリプト
"""

import asyncio
import json
from datetime import datetime
from rag_interface import RAGInterface
from paas_api import PaaSClient


def test_rag_interface():
    """RAGインターフェースの基本動作テスト"""
    print("=" * 50)
    print("RAGインターフェースのテスト開始")
    print("=" * 50)
    
    try:
        # RAGインターフェース初期化
        print("1. RAGインターフェース初期化...")
        rag = RAGInterface()
        print("✓ 初期化成功")
        
        # システム統計取得
        print("\n2. システム統計取得...")
        stats = rag.get_system_stats()
        print(f"✓ 総文書数: {stats.total_documents}")
        print(f"✓ カテゴリ別: {stats.documents_by_category}")
        print(f"✓ 解析完了率: {stats.analysis_completion_rate:.1f}%")
        
        # 検索テスト
        print("\n3. 検索機能テスト...")
        search_queries = ["機械学習", "データ", "LLM", "バイアス"]
        
        for query in search_queries:
            try:
                result = rag.search_documents(query, limit=3)
                print(f"✓ '{query}': {result.total_count}件 ({result.execution_time_ms}ms)")
                
                for doc in result.documents[:2]:  # 最初の2件を表示
                    print(f"   - [{doc.category}] {doc.title[:50]}...")
                    
            except Exception as e:
                print(f"✗ '{query}': エラー - {e}")
        
        # 文書詳細取得テスト
        print("\n4. 文書詳細取得テスト...")
        categories = ['dataset', 'paper', 'poster']
        
        for category in categories:
            try:
                # ID=1の文書を取得してみる
                doc = rag.get_document_detail(1, category)
                if doc:
                    print(f"✓ {category}: {doc.title}")
                else:
                    print(f"- {category}: 文書が見つかりません")
            except Exception as e:
                print(f"✗ {category}: エラー - {e}")
        
        print("\n✓ RAGインターフェーステスト完了")
        return True
        
    except Exception as e:
        print(f"✗ RAGインターフェーステスト失敗: {e}")
        return False


def test_api_endpoints():
    """API エンドポイントのテスト（サーバーが起動している場合）"""
    print("\n" + "=" * 50)
    print("PaaS APIエンドポイントのテスト開始")
    print("=" * 50)
    
    try:
        # クライアント初期化
        print("1. PaaSクライアント初期化...")
        client = PaaSClient("http://localhost:8000")
        print("✓ クライアント初期化成功")
        
        # ヘルスチェック
        print("\n2. ヘルスチェック...")
        try:
            response = client.client.get(f"{client.base_url}/health")
            if response.status_code == 200:
                print("✓ サーバー応答正常")
                health_data = response.json()
                print(f"✓ ステータス: {health_data.get('status')}")
            else:
                print(f"✗ サーバー応答異常: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ サーバーに接続できません: {e}")
            print("注意: APIサーバーを先に起動してください")
            print("実行方法: python paas_api.py")
            return False
        
        # 統計情報取得
        print("\n3. 統計情報取得...")
        stats = client.get_statistics()
        print(f"✓ 総文書数: {stats['total_documents']}")
        print(f"✓ カテゴリ別: {stats['documents_by_category']}")
        
        # 検索テスト
        print("\n4. 検索APIテスト...")
        search_result = client.search_documents("データ", limit=5)
        print(f"✓ 検索結果: {search_result['total_count']}件")
        print(f"✓ 実行時間: {search_result['execution_time_ms']}ms")
        
        # カテゴリー取得
        print("\n5. カテゴリー一覧取得...")
        response = client.client.get(f"{client.base_url}/documents/categories")
        categories = response.json()
        for cat in categories['categories']:
            print(f"✓ {cat['id']}: {cat['name']}")
        
        print("\n✓ PaaS APIテスト完了")
        return True
        
    except Exception as e:
        print(f"✗ PaaS APIテスト失敗: {e}")
        return False


def generate_integration_example():
    """統合利用例のコード生成"""
    print("\n" + "=" * 50)
    print("統合利用例の生成")
    print("=" * 50)
    
    example_code = '''
# 学部内データ管理PaaS 統合利用例

from paas_api import PaaSClient

# 1. クライアント初期化
client = PaaSClient("http://your-paas-server:8000")

# 2. 文書検索（基本）
results = client.search_documents("機械学習", limit=10)
for doc in results['documents']:
    print(f"[{doc['category']}] {doc['title']}")
    print(f"要約: {doc['summary'][:100]}...")
    print(f"キーワード: {', '.join(doc['keywords'])}")
    print("-" * 40)

# 3. カテゴリ別検索
datasets = client.search_documents("環境", category="dataset")
papers = client.search_documents("バイアス", category="paper")

# 4. 特定文書の詳細取得
paper_detail = client.get_document("paper", document_id=1)
print(f"著者: {paper_detail['authors']}")
print(f"ファイルサイズ: {paper_detail['file_size']} bytes")

# 5. システム統計
stats = client.get_statistics()
print(f"データベース内の総文書数: {stats['total_documents']}")
print(f"解析完了率: {stats['analysis_completion_rate']:.1f}%")

# 6. 新しい文書の取り込み（管理者用）
result = client.ingest_documents()
print(f"取り込み完了: {result['processed_files']}件処理")
'''
    
    with open("integration_example.py", "w", encoding="utf-8") as f:
        f.write(example_code)
    
    print("✓ integration_example.py を生成しました")
    print("このファイルを参考に、PaaS機能を他のシステムに統合できます")


def main():
    """メインテスト実行"""
    print("学部内データ管理PaaS - 統合テスト")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # RAGインターフェースのテスト
    rag_success = test_rag_interface()
    
    # APIエンドポイントのテスト
    api_success = test_api_endpoints()
    
    # 統合例の生成
    generate_integration_example()
    
    # 結果サマリー
    print("\n" + "=" * 50)
    print("テスト結果サマリー")
    print("=" * 50)
    print(f"RAGインターフェース: {'✓ 成功' if rag_success else '✗ 失敗'}")
    print(f"PaaS API: {'✓ 成功' if api_success else '✗ 失敗'}")
    
    if rag_success and api_success:
        print("\n🎉 全てのテストが成功しました！")
        print("PaaS機能の統合準備が完了しています。")
    elif rag_success:
        print("\n⚠️ RAGインターフェースは動作していますが、APIサーバーの起動が必要です。")
        print("次のコマンドでAPIサーバーを起動してください:")
        print("python paas_api.py")
    else:
        print("\n❌ 問題が発生しています。ログを確認してください。")


if __name__ == "__main__":
    main()