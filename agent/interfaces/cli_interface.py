"""
コマンドラインインターフェース
ユーザーとの対話的なCLI操作を提供
"""
from typing import Dict, Any, List

from ..config import Config
from ..data_management.data_manager import DataManager
from ..search.search_engine import SearchEngine
from ..consultation.llm_advisor import LLMAdvisor


class CLIInterface:
    """コマンドラインインターフェースを提供するクラス"""
    
    def __init__(self, data_manager: DataManager, 
                 search_engine: SearchEngine,
                 advisor: LLMAdvisor,
                 config: Config):
        """
        CLIインターフェースの初期化
        
        Args:
            data_manager: データマネージャ
            search_engine: 検索エンジン
            advisor: LLM研究相談アドバイザー
            config: 設定オブジェクト
        """
        self.data_manager = data_manager
        self.search_engine = search_engine
        self.advisor = advisor
        self.config = config
    
    def run(self):
        """コマンドラインインターフェースを実行"""
        print(f"\n{self.config.system_name} にようこそ！")
        self.config.display_config()
        
        while True:
            self._display_main_menu()
            choice = input("選択してください (1-6): ").strip()
            
            if choice == '1':
                self._handle_search()
            elif choice == '2':
                self._handle_data_registration()
            elif choice == '3':
                self._handle_data_management()
            elif choice == '4':
                self._handle_consultation()
            elif choice == '5':
                self._handle_statistics()
            elif choice == '6':
                print("システムを終了します。")
                break
            else:
                print("無効な選択です。")
            
            input("\nEnterキーを押して続行...")
    
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
        
        # 検索オプションの選択
        print("検索オプション:")
        print("1. キーワード検索")
        print("2. 高度な検索")
        print("3. 類似データ検索")
        
        option = input("選択 (1-3): ").strip()
        
        if option == '1':
            self._handle_keyword_search()
        elif option == '2':
            self._handle_advanced_search()
        elif option == '3':
            self._handle_similar_search()
        else:
            print("無効な選択です。")
    
    def _handle_keyword_search(self):
        """キーワード検索の処理"""
        query = input("検索キーワードを入力: ").strip()
        
        if query:
            results = self.search_engine.search(query, limit=10)
            self._display_search_results(results)
        else:
            print("キーワードが入力されませんでした。")
    
    def _handle_advanced_search(self):
        """高度な検索の処理"""
        query = input("検索キーワード: ").strip()
        
        # フィルターの設定
        print("\nフィルター設定（省略可能）:")
        data_type = input("データタイプ (dataset/paper/poster): ").strip()
        research_field = input("研究分野: ").strip()
        
        filters = {}
        if data_type:
            filters['data_type'] = data_type
        if research_field:
            filters['research_field'] = research_field
        
        results = self.search_engine.search(query, filters=filters, limit=10)
        self._display_search_results(results)
    
    def _handle_similar_search(self):
        """類似データ検索の処理"""
        data_id = input("基準となるデータID: ").strip()
        
        if data_id:
            similar_data = self.search_engine.get_similar_data(data_id, limit=5)
            
            if similar_data:
                print(f"\n類似データ ({len(similar_data)}件):")
                for i, data in enumerate(similar_data, 1):
                    print(f"\n{i}. {data.get('title', '無題')}")
                    print(f"   タイプ: {data.get('data_type', '不明')}")
                    print(f"   分野: {data.get('research_field', '未分類')}")
                    print(f"   類似度: {data.get('_similarity_score', 0):.2f}")
            else:
                print("類似データが見つかりませんでした。")
        else:
            print("データIDが入力されませんでした。")
    
    def _display_search_results(self, results: Dict[str, Any]):
        """検索結果を表示"""
        if results['results']:
            print(f"\n{results['returned_count']}件見つかりました:")
            
            for i, data in enumerate(results['results'], 1):
                print(f"\n{i}. {data.get('title', '無題')}")
                print(f"   ID: {data.get('data_id', 'N/A')}")
                print(f"   タイプ: {data.get('data_type', '不明')}")
                print(f"   分野: {data.get('research_field', '未分類')}")
                if data.get('summary'):
                    summary = data['summary'][:100] + "..." if len(data['summary']) > 100 else data['summary']
                    print(f"   概要: {summary}")
                if data.get('_score'):
                    print(f"   スコア: {data['_score']:.2f}")
            
            # ファセット情報の表示
            if results.get('facets'):
                self._display_facets(results['facets'])
            
            # 詳細表示の選択
            choice = input("\n詳細を見たいデータの番号を入力 (スキップは Enter): ").strip()
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(results['results']):
                    self._display_data_details(results['results'][index])
        else:
            print("該当するデータが見つかりませんでした。")
            
            # サジェスチョンの表示
            if results.get('suggestions'):
                print("\n検索のヒント:")
                for suggestion in results['suggestions']:
                    print(f"  - {suggestion}")
    
    def _display_facets(self, facets: Dict[str, List[Dict[str, Any]]]):
        """ファセット情報を表示"""
        print("\n--- 分布情報 ---")
        
        if facets.get('data_type'):
            print("データタイプ別:")
            for facet in facets['data_type']:
                print(f"  {facet['value']}: {facet['count']}件")
        
        if facets.get('research_field'):
            print("研究分野別:")
            for facet in facets['research_field'][:5]:  # 上位5件
                print(f"  {facet['value']}: {facet['count']}件")
    
    def _display_data_details(self, data: Dict[str, Any]):
        """データの詳細情報を表示"""
        print(f"\n--- データ詳細 ---")
        print(f"ID: {data.get('data_id', 'N/A')}")
        print(f"タイトル: {data.get('title', '無題')}")
        print(f"タイプ: {data.get('data_type', '不明')}")
        print(f"研究分野: {data.get('research_field', '未分類')}")
        print(f"ファイルパス: {data.get('file_path', 'N/A')}")
        print(f"作成日: {data.get('created_date', 'N/A')}")
        
        if data.get('summary'):
            print(f"概要: {data['summary']}")
        
        if data.get('metadata'):
            print("メタデータ:")
            metadata = data['metadata']
            if isinstance(metadata, dict):
                for key, value in list(metadata.items())[:5]:  # 最初の5個
                    print(f"  {key}: {value}")
    
    def _handle_data_registration(self):
        """データ登録機能の処理"""
        print("\n--- データ登録 ---")
        print("1. 単一ファイルを登録")
        print("2. ディレクトリを一括登録")
        print("3. ディレクトリをデータセットとして登録")
        
        choice = input("選択 (1-3): ").strip()
        
        if choice == '1':
            self._register_single_file()
        elif choice == '2':
            self._register_directory()
        elif choice == '3':
            self._register_dataset()
        else:
            print("無効な選択です。")
    
    def _register_single_file(self):
        """単一ファイル登録の処理"""
        file_path = input("ファイルパス: ").strip()
        
        if file_path:
            # 任意の詳細情報
            title = input("タイトル (省略可): ").strip() or None
            summary = input("概要 (省略可): ").strip() or None
            research_field = input("研究分野 (省略可): ").strip() or None
            
            result = self.data_manager.register_data(
                file_path, title, summary, research_field
            )
            
            if result['success']:
                print(f"✓ 登録完了: {result['data_id']}")
                print(f"  {result['message']}")
            else:
                print(f"✗ 登録失敗: {result['error']}")
        else:
            print("ファイルパスが入力されませんでした。")
    
    def _register_directory(self):
        """ディレクトリ一括登録の処理"""
        dir_path = input("ディレクトリパス: ").strip()
        
        if dir_path:
            recursive_input = input("サブディレクトリも処理する? (y/n): ").strip().lower()
            recursive = recursive_input in ['y', 'yes', '']
            
            print("登録を開始します...")
            result = self.data_manager.register_directory(dir_path, recursive)
            
            print(f"\n処理結果:")
            print(f"  総ファイル数: {result['total_files']}")
            print(f"  成功: {result['successful']}件")
            print(f"  失敗: {result['failed']}件")
            
            if result['errors']:
                print(f"\nエラー (最初の3件):")
                for error in result['errors'][:3]:
                    print(f"  - {error}")
        else:
            print("ディレクトリパスが入力されませんでした。")
    
    def _register_dataset(self):
        """データセット登録の処理"""
        dir_path = input("データセットディレクトリパス: ").strip()
        
        if dir_path:
            # カスタム情報の入力
            custom_name = input("データセット名 (省略可、ディレクトリ名を使用): ").strip() or None
            custom_description = input("データセット説明 (省略可、LLMが自動生成): ").strip() or None
            
            print("データセットを分析・登録中...")
            print("※ LLMによるタグ付けと説明文生成を行います")
            
            result = self.data_manager.register_dataset(dir_path, custom_name, custom_description)
            
            if result['success']:
                print(f"✓ データセット登録完了")
                print(f"  データセット名: {result['name']}")
                print(f"  データセットID: {result['dataset_id']}")
                
                if result.get('analysis'):
                    analysis = result['analysis']
                    print(f"\n=== LLM分析結果 ===")
                    print(f"研究分野: {analysis.get('research_field', 'N/A')}")
                    print(f"データタイプ: {analysis.get('data_type', 'N/A')}")
                    print(f"説明: {analysis.get('description', 'N/A')[:200]}...")
                    
                    if analysis.get('tags'):
                        print(f"タグ: {', '.join(analysis['tags'][:5])}")
                    
                    if analysis.get('potential_use_cases'):
                        print(f"利用用途: {', '.join(analysis['potential_use_cases'][:3])}")
                        
                    print(f"品質スコア: {analysis.get('quality_score', 0):.2f}")
                    print(f"複雑度: {analysis.get('complexity', 'N/A')}")
            else:
                print(f"✗ データセット登録失敗: {result['error']}")
        else:
            print("ディレクトリパスが入力されませんでした。")
    
    def _handle_data_management(self):
        """データ管理機能の処理"""
        print("\n--- データ管理 ---")
        print("1. ファイルデータ一覧表示")
        print("2. ファイルデータの詳細表示")
        print("3. ファイルデータの更新")
        print("4. ファイルデータの削除")
        print("5. データのエクスポート")
        print("6. データセット一覧表示")
        print("7. データセット詳細表示")
        print("8. データセット検索")
        
        choice = input("選択 (1-8): ").strip()
        
        if choice == '1':
            self._list_all_data()
        elif choice == '2':
            self._show_data_details()
        elif choice == '3':
            self._update_data()
        elif choice == '4':
            self._delete_data()
        elif choice == '5':
            self._export_data()
        elif choice == '6':
            self._list_datasets()
        elif choice == '7':
            self._show_dataset_details()
        elif choice == '8':
            self._search_datasets()
        else:
            print("無効な選択です。")
    
    def _list_all_data(self):
        """データ一覧表示の処理"""
        print("\n--- データ一覧 ---")
        
        # ページサイズを設定
        page_size = 10
        offset = 0
        
        while True:
            # データを取得
            search_results = self.search_engine.search("", limit=page_size, offset=offset)
            
            if not search_results['results']:
                if offset == 0:
                    print("データが登録されていません。")
                else:
                    print("これ以上データがありません。")
                break
            
            print(f"\n=== ページ {offset//page_size + 1} ({offset + 1}-{offset + len(search_results['results'])}/{search_results.get('total_count', '?')}件) ===")
            
            for i, data in enumerate(search_results['results'], 1):
                print(f"{offset + i:2d}. {data.get('title', '無題')[:50]}")
                print(f"     ID: {data.get('data_id', 'N/A')[:12]}... | タイプ: {data.get('data_type', '不明')}")
                print(f"     分野: {data.get('research_field', '未分類')}")
                print()
            
            # ナビゲーション
            print("操作: [n]次のページ, [p]前のページ, [番号]詳細表示, [q]戻る")
            choice = input("選択: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == 'n' and len(search_results['results']) == page_size:
                offset += page_size
            elif choice == 'p' and offset > 0:
                offset -= page_size
            elif choice.isdigit():
                index = int(choice) - 1 - offset
                if 0 <= index < len(search_results['results']):
                    self._display_data_details(search_results['results'][index])
                    input("\nEnterキーを押して一覧に戻る...")
                else:
                    print("無効な番号です。")
            else:
                print("無効な選択です。")
    
    def _show_data_details(self):
        """データ詳細表示の処理"""
        search_term = input("データIDまたはタイトルを入力: ").strip()
        
        if search_term:
            # まずデータIDで検索
            data = self.data_manager.get_data_info(search_term)
            
            # データIDで見つからない場合はタイトルで検索
            if not data:
                search_results = self.search_engine.search(search_term, limit=10)
                if search_results['results']:
                    print(f"\n'{search_term}'で検索した結果:")
                    for i, result in enumerate(search_results['results'], 1):
                        print(f"{i}. {result.get('title', '無題')} (ID: {result.get('data_id', 'N/A')})")
                        print(f"   タイプ: {result.get('data_type', '不明')}")
                    
                    choice = input("\n詳細を見たい番号を選択 (1-{}) または Enter でキャンセル: ".format(len(search_results['results']))).strip()
                    if choice.isdigit():
                        index = int(choice) - 1
                        if 0 <= index < len(search_results['results']):
                            data = search_results['results'][index]
                        else:
                            print("無効な選択です。")
                            return
                    else:
                        print("キャンセルしました。")
                        return
                else:
                    print("データが見つかりません。")
                    return
            
            if data:
                self._display_data_details(data)
        else:
            print("データIDまたはタイトルが入力されませんでした。")
    
    def _get_data_id_interactive(self, prompt_text: str) -> str:
        """
        対話的にデータIDを取得（タイトル検索も対応）
        
        Args:
            prompt_text: プロンプトテキスト
        
        Returns:
            データID（見つからない場合は空文字列）
        """
        search_term = input(f"{prompt_text}: ").strip()
        
        if not search_term:
            print("入力されませんでした。")
            return ""
        
        # まずデータIDで検索
        data = self.data_manager.get_data_info(search_term)
        if data:
            return search_term
        
        # データIDで見つからない場合はタイトルで検索
        search_results = self.search_engine.search(search_term, limit=10)
        if search_results['results']:
            print(f"\n'{search_term}'で検索した結果:")
            for i, result in enumerate(search_results['results'], 1):
                print(f"{i}. {result.get('title', '無題')} (ID: {result.get('data_id', 'N/A')})")
                print(f"   タイプ: {result.get('data_type', '不明')}")
            
            choice = input(f"\n選択したい番号を入力 (1-{len(search_results['results'])}) または Enter でキャンセル: ").strip()
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(search_results['results']):
                    return search_results['results'][index].get('data_id', '')
                else:
                    print("無効な選択です。")
            else:
                print("キャンセルしました。")
        else:
            print("データが見つかりません。")
        
        return ""
    
    def _update_data(self):
        """データ更新の処理"""
        data_id = self._get_data_id_interactive("更新するデータIDまたはタイトルを入力")
        
        if data_id:
            # 現在のデータを表示
            data = self.data_manager.get_data_info(data_id)
            if not data:
                print("データが見つかりません。")
                return
            
            print(f"\n現在の情報:")
            print(f"タイトル: {data.get('title', '')}")
            print(f"概要: {data.get('summary', '')}")
            print(f"研究分野: {data.get('research_field', '')}")
            
            # 更新情報の入力
            updates = {}
            
            new_title = input("新しいタイトル (変更しない場合は Enter): ").strip()
            if new_title:
                updates['title'] = new_title
            
            new_summary = input("新しい概要 (変更しない場合は Enter): ").strip()
            if new_summary:
                updates['summary'] = new_summary
            
            new_field = input("新しい研究分野 (変更しない場合は Enter): ").strip()
            if new_field:
                updates['research_field'] = new_field
            
            if updates:
                result = self.data_manager.update_data(data_id, updates)
                if result['success']:
                    print(f"✓ 更新完了: {result['message']}")
                else:
                    print(f"✗ 更新失敗: {result['error']}")
            else:
                print("更新項目がありません。")
        else:
            print("データIDが入力されませんでした。")
    
    def _delete_data(self):
        """データ削除の処理"""
        data_id = self._get_data_id_interactive("削除するデータIDまたはタイトルを入力")
        
        if data_id:
            # 削除確認
            delete_file_input = input("実ファイルも削除しますか? (y/n): ").strip().lower()
            delete_file = delete_file_input in ['y', 'yes']
            
            confirm = input(f"本当に削除しますか? (ファイル削除: {'あり' if delete_file else 'なし'}) (y/n): ").strip().lower()
            
            if confirm in ['y', 'yes']:
                result = self.data_manager.delete_data(data_id, delete_file)
                if result['success']:
                    print(f"✓ 削除完了: {result['message']}")
                else:
                    print(f"✗ 削除失敗: {result['error']}")
            else:
                print("削除をキャンセルしました。")
        else:
            print("データIDが入力されませんでした。")
    
    def _export_data(self):
        """データエクスポートの処理"""
        print("エクスポート形式:")
        print("1. JSON")
        print("2. CSV")
        
        format_choice = input("選択 (1-2): ").strip()
        export_format = 'json' if format_choice == '1' else 'csv'
        
        # 範囲選択
        print("エクスポート範囲:")
        print("1. 全データ")
        print("2. 特定のデータID")
        
        range_choice = input("選択 (1-2): ").strip()
        
        data_ids = None
        if range_choice == '2':
            ids_input = input("データID (カンマ区切りで複数指定可): ").strip()
            if ids_input:
                data_ids = [id.strip() for id in ids_input.split(',')]
        
        result = self.data_manager.export_data(data_ids, export_format)
        
        if result['success']:
            print(f"✓ エクスポート完了: {result['export_path']}")
            print(f"  {result['message']}")
        else:
            print(f"✗ エクスポート失敗: {result['error']}")
    
    def _handle_consultation(self):
        """研究相談機能の処理"""
        print("\n--- 研究相談 ---")
        print("研究相談を行います")
        print("'quit'、'exit'、または空のメッセージでメインメニューに戻ります")
        
        print(f"\n💬 相談開始！何でもお聞きください。")
        
        message_count = 0
        while True:
            print("\n" + "-" * 50)
            
            # 相談内容の入力
            query = input("相談内容: ").strip()
            
            # 終了条件
            if not query or query.lower() in ['quit', 'exit', 'q']:
                print("研究相談を終了します。")
                break
            
            # 相談タイプの自動判定
            consultation_type = 'general'
            if any(keyword in query.lower() for keyword in ['データセット', 'dataset']):
                consultation_type = 'dataset'
            elif any(keyword in query.lower() for keyword in ['論文', 'paper', 'アイデア', 'idea']):
                consultation_type = 'idea'
            
            print("\n🤖 相談を処理中...")
            print("※ LLMが包括的に回答を生成しています...")
            
            try:
                result = self.advisor.consult(
                    query, 
                    consultation_type
                )
                
                print(f"\n【AI相談アドバイス】")
                print(result['advice'])
                
                # 簡潔な追加情報表示
                if result.get('search_suggestions'):
                    print(f"\n💡 検索のヒント: {', '.join(result['search_suggestions'][:3])}")
                
                if result.get('recommendations'):
                    print(f"\n📚 推薦データ ({len(result['recommendations'])}件):")
                    for i, rec in enumerate(result['recommendations'][:3], 1):
                        print(f"  {i}. {rec.get('title', '無題')} ({rec.get('type', 'N/A')})")
                
                if result.get('next_steps'):
                    print(f"\n📋 次のステップ:")
                    for i, step in enumerate(result['next_steps'][:2], 1):
                        print(f"  {i}. {step}")
                
                message_count += 1
                
                # 定期的な統計表示
                if message_count % 3 == 0:
                    print(f"\n📊 会話数: {result.get('conversation_length', 0)}メッセージ")
                
                # 継続を促すメッセージ
                if message_count == 1:
                    print(f"\n💬 他にも質問があれば、続けてお聞きください。")
                
            except Exception as e:
                print(f"\nエラーが発生しました: {e}")
                print("もう一度お試しください。")
        
        print(f"\n📊 相談統計:")
        print(f"   総やり取り数: {message_count}")
        print(f"   ありがとうございました！")
    
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
        
        if stats.get('recent_updates'):
            print(f"\n最近の更新:")
            for update in stats['recent_updates']:
                print(f"  {update['title']} ({update['updated_at'][:10]})")
        
        # トレンド情報の表示
        trending = self.search_engine.get_trending_topics()
        if trending:
            print(f"\nトレンドトピック:")
            for trend in trending[:3]:
                print(f"  {trend['topic']}: {trend['count']}件")
        
        # チャット統計の表示
        try:
            chat_stats = self.advisor.get_chat_statistics()
            print(f"\nチャット相談統計:")
            print(f"  アクティブセッション数: {chat_stats['active_sessions']}")
            print(f"  総メッセージ数: {chat_stats['total_messages']}")
            print(f"  今日のメッセージ数: {chat_stats['today_messages']}")
            print(f"\n詳細なチャット統計は「5. チャット履歴を管理する」→「4. チャット統計」で確認できます")
        except Exception as e:
            print(f"\nチャット統計取得エラー: {e}")
    
    # === データセット管理機能 ===
    
    def _list_datasets(self):
        """データセット一覧表示の処理"""
        print("\n--- データセット一覧 ---")
        
        datasets = self.data_manager.search_datasets(limit=50)
        
        if not datasets:
            print("データセットが登録されていません。")
            return
        
        print(f"\n総データセット数: {len(datasets)}件\n")
        
        for i, dataset in enumerate(datasets, 1):
            print(f"{i:2d}. {dataset['name']}")
            print(f"     ID: {dataset['dataset_id']}")
            print(f"     分野: {dataset.get('research_field', '不明')}")
            print(f"     タイプ: {dataset.get('data_type', '不明')}")
            print(f"     ファイル数: {dataset.get('file_count', 0)}件")
            
            if dataset.get('tags'):
                tags = dataset['tags'][:3]  # 最初の3つのタグ
                print(f"     タグ: {', '.join(tags)}")
            
            print(f"     説明: {dataset.get('description', '')[:100]}...")
            print()
    
    def _show_dataset_details(self):
        """データセット詳細表示の処理"""
        dataset_id = input("データセットIDまたは名前を入力: ").strip()
        
        if not dataset_id:
            print("入力されませんでした。")
            return
        
        # IDで検索
        dataset = self.data_manager.get_dataset_by_id(dataset_id)
        
        # IDで見つからない場合は名前で検索
        if not dataset:
            datasets = self.data_manager.search_datasets(dataset_id, limit=10)
            if datasets:
                print(f"\n'{dataset_id}'で検索した結果:")
                for i, ds in enumerate(datasets, 1):
                    print(f"{i}. {ds['name']} (ID: {ds['dataset_id']})")
                
                choice = input(f"\n詳細を見たい番号を選択 (1-{len(datasets)}) または Enter でキャンセル: ").strip()
                if choice.isdigit():
                    index = int(choice) - 1
                    if 0 <= index < len(datasets):
                        dataset = self.data_manager.get_dataset_by_id(datasets[index]['dataset_id'])
                else:
                    print("キャンセルしました。")
                    return
        
        if dataset:
            self._display_dataset_details(dataset)
        else:
            print("データセットが見つかりません。")
    
    def _display_dataset_details(self, dataset: Dict[str, Any]):
        """データセット詳細情報を表示"""
        print(f"\n=== データセット詳細 ===")
        print(f"ID: {dataset['dataset_id']}")
        print(f"名前: {dataset['name']}")
        print(f"ディレクトリ: {dataset['directory_path']}")
        print(f"研究分野: {dataset.get('research_field', '不明')}")
        print(f"データタイプ: {dataset.get('data_type', '不明')}")
        print(f"ファイル数: {dataset.get('file_count', 0)}件")
        print(f"総サイズ: {dataset.get('total_size', 0) / (1024*1024):.2f} MB")
        print(f"品質スコア: {dataset.get('quality_score', 0):.2f}")
        print(f"複雑度: {dataset.get('complexity_level', '不明')}")
        print(f"作成日: {dataset.get('created_at', '不明')}")
        print(f"更新日: {dataset.get('updated_at', '不明')}")
        
        if dataset.get('description'):
            print(f"\n説明:")
            print(f"{dataset['description']}")
        
        if dataset.get('llm_generated_summary'):
            print(f"\nLLM生成サマリー:")
            print(f"{dataset['llm_generated_summary']}")
        
        if dataset.get('tags'):
            print(f"\nタグ:")
            print(f"  {', '.join(dataset['tags'])}")
        
        if dataset.get('llm_generated_tags'):
            print(f"\nLLM推薦タグ:")
            print(f"  {', '.join(dataset['llm_generated_tags'])}")
        
        # ファイル詳細
        if dataset.get('files'):
            print(f"\n=== ファイル詳細 ({len(dataset['files'])}件) ===")
            for i, file_info in enumerate(dataset['files'][:10], 1):  # 最初の10件
                print(f"{i:2d}. {file_info['file_name']}")
                print(f"     パス: {file_info['file_path']}")
                print(f"     タイプ: {file_info.get('file_type', '不明')}")
                print(f"     役割: {file_info.get('role', '不明')}")
                print(f"     サイズ: {file_info.get('file_size', 0) / 1024:.1f} KB")
            
            if len(dataset['files']) > 10:
                print(f"... 他 {len(dataset['files']) - 10}件")
    
    def _search_datasets(self):
        """データセット検索の処理"""
        print("\n--- データセット検索 ---")
        
        query = input("検索キーワード (省略可): ").strip()
        research_field = input("研究分野 (省略可): ").strip()
        data_type = input("データタイプ (省略可): ").strip()
        tags_input = input("タグ (カンマ区切り、省略可): ").strip()
        
        # タグをリストに変換
        tags = []
        if tags_input:
            tags = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
        
        # 検索実行
        results = self.data_manager.search_datasets(
            query=query,
            research_field=research_field or None,
            data_type=data_type or None,
            tags=tags if tags else None,
            limit=20
        )
        
        if results:
            print(f"\n検索結果: {len(results)}件")
            print()
            
            for i, dataset in enumerate(results, 1):
                print(f"{i:2d}. {dataset['name']}")
                print(f"     ID: {dataset['dataset_id']}")
                print(f"     分野: {dataset.get('research_field', '不明')}")
                print(f"     説明: {dataset.get('description', '')[:80]}...")
                print()
            
            # 詳細表示の選択
            choice = input("\n詳細を見たいデータセットの番号を入力 (スキップは Enter): ").strip()
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(results):
                    dataset = self.data_manager.get_dataset_by_id(results[index]['dataset_id'])
                    if dataset:
                        self._display_dataset_details(dataset)
        else:
            print("該当するデータセットが見つかりませんでした。")
            
            # 利用可能なタグの表示
            all_tags = self.data_manager.get_all_dataset_tags()
            if all_tags:
                print(f"\n利用可能なタグ (一部):")
                print(f"  {', '.join(all_tags[:10])}")
                if len(all_tags) > 10:
                    print(f"  ... 他 {len(all_tags) - 10}個")