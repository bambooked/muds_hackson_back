from typing import Optional
import json

from .menu import Menu, InputHelper, TableDisplay
from ..database.connection import db_connection
from ..indexer.new_indexer import NewFileIndexer
from ..analyzer.new_analyzer import NewFileAnalyzer
from ..database.new_repository import DatasetRepository, PaperRepository, PosterRepository, DatasetFileRepository
from ..advisor.enhanced_research_advisor import EnhancedResearchAdvisor
from ..advisor.dataset_advisor import DatasetAdvisor
from ..advisor.research_visualizer import ResearchVisualizer


class UserInterface:
    """ユーザーインターフェースを管理するクラス"""
    
    def __init__(self):
        self.indexer = NewFileIndexer(auto_analyze=True)  # 新しいインデクサーを使用
        self.analyzer = NewFileAnalyzer()  # 新しいアナライザーを使用
        self.dataset_repo = DatasetRepository()
        self.paper_repo = PaperRepository()
        self.poster_repo = PosterRepository()
        self.dataset_file_repo = DatasetFileRepository()
        
        # 拡張研究相談機能
        self.enhanced_advisor = EnhancedResearchAdvisor()
        self.dataset_advisor = DatasetAdvisor()
        self.research_visualizer = ResearchVisualizer()
        
        # メインメニューの設定
        self.main_menu = Menu("研究データ管理システム")
        self._setup_main_menu()
    
    def _setup_main_menu(self):
        """メインメニューを設定"""
        self.main_menu.add_option("1", "データ更新", self.update_index)
        self.main_menu.add_option("2", "データベース検索・相談", self.database_search_consultation)
        self.main_menu.add_option("3", "研究計画・相談", self.research_planning_consultation)
        self.main_menu.add_option("4", "データ管理", self.data_management)
        self.main_menu.add_option("5", "統計情報", self.show_statistics)
        self.main_menu.add_option("0", "設定", self.settings)
    
    def run(self):
        """アプリケーションを実行"""
        # データベース初期化
        print("データベースを初期化中...")
        db_connection.initialize_database()
        
        # メインメニューを実行
        self.main_menu.run()
    
    def update_index(self):
        """データインデックスを更新"""
        print("データインデックスを更新します...\n")
        
        results = self.indexer.index_all_files()
        
        print("\n更新結果:")
        print(f"  データセット: {results['datasets']}件")
        print(f"  論文: {results['papers']}件") 
        print(f"  ポスター: {results['posters']}件")
        print(f"  データセットファイル: {results['dataset_files']}件")
        print(f"  エラー: {results['errors']}件")
        
        if results['details']:
            print("\n詳細:")
            for detail in results['details'][:10]:  # 最初の10件のみ表示
                if 'file' in detail:
                    print(f"  - {detail['action']}: {detail['file']}")
                elif 'name' in detail:
                    print(f"  - {detail['action']}: {detail['name']} ({detail.get('files', 0)}ファイル)")
                else:
                    print(f"  - {detail['action']}")
            
            if len(results['details']) > 10:
                print(f"  ... 他 {len(results['details']) - 10} 件")
        
        # データセット統計を表示
        status = self.indexer.get_index_status()
        if status['total_datasets'] > 0:
            print(f"\nデータセット統計:")
            print(f"  総データセット数: {status['total_datasets']}個")
            for dataset_info in status['datasets']:
                print(f"  - {dataset_info['name']}: {dataset_info['files']}ファイル ({dataset_info['size_mb']} MB)")
    
    def database_search_consultation(self):
        """データベース検索・相談"""
        self._start_database_chat()
    
    def research_planning_consultation(self):
        """研究計画・相談"""
        self._start_research_planning_chat()
    
    def search_files(self):
        """レガシー互換性のため"""
        self.database_search_consultation()
    
    
    def _display_datasets(self, datasets: list):
        """データセットリストを表示"""
        if not datasets:
            print("\nデータセットが見つかりませんでした。")
            return
        
        print(f"\n{len(datasets)}個のデータセットが見つかりました:\n")
        
        headers = ["ID", "データセット名", "ファイル数", "サイズ(MB)", "要約"]
        rows = []
        
        for dataset in datasets:
            summary_short = (dataset.summary[:50] + "...") if dataset.summary and len(dataset.summary) > 50 else (dataset.summary or "未解析")
            rows.append([
                dataset.id,
                dataset.name,
                dataset.file_count,
                f"{dataset.total_size / (1024*1024):.2f}",
                summary_short
            ])
        
        TableDisplay.display_table(headers, rows)
    
    def _display_papers(self, papers: list):
        """論文リストを表示"""
        if not papers:
            print("\n論文が見つかりませんでした。")
            return
        
        print(f"\n{len(papers)}件の論文が見つかりました:\n")
        
        headers = ["ID", "ファイル名", "タイトル", "著者"]
        rows = []
        
        for paper in papers:
            title = (paper.title[:30] + "...") if paper.title and len(paper.title) > 30 else (paper.title or paper.file_name)
            authors = (paper.authors[:20] + "...") if paper.authors and len(paper.authors) > 20 else (paper.authors or "不明")
            rows.append([
                paper.id,
                paper.file_name[:20],
                title,
                authors
            ])
        
        TableDisplay.display_table(headers, rows)
    
    def _display_posters(self, posters: list):
        """ポスターリストを表示"""
        if not posters:
            print("\nポスターが見つかりませんでした。")
            return
        
        print(f"\n{len(posters)}件のポスターが見つかりました:\n")
        
        headers = ["ID", "ファイル名", "タイトル", "著者"]
        rows = []
        
        for poster in posters:
            title = (poster.title[:30] + "...") if poster.title and len(poster.title) > 30 else (poster.title or poster.file_name)
            authors = (poster.authors[:20] + "...") if poster.authors and len(poster.authors) > 20 else (poster.authors or "不明")
            rows.append([
                poster.id,
                poster.file_name[:20],
                title,
                authors
            ])
        
        TableDisplay.display_table(headers, rows)
    
    def _display_all_content(self):
        """全コンテンツを表示"""
        print("\n=== 全コンテンツ ===")
        
        datasets = self.dataset_repo.find_all()
        papers = self.paper_repo.find_all()
        posters = self.poster_repo.find_all()
        
        print(f"\nデータセット: {len(datasets)}個")
        for dataset in datasets:
            summary = dataset.summary[:100] if dataset.summary else "未解析"
            print(f"  - {dataset.name}: {dataset.file_count}ファイル ({summary})")
        
        print(f"\n論文: {len(papers)}件")
        for paper in papers:
            title = paper.title or paper.file_name
            print(f"  - {title[:50]}")
        
        print(f"\nポスター: {len(posters)}件")
        for poster in posters:
            title = poster.title or poster.file_name
            print(f"  - {title[:50]}")
    
    
    def _show_file_details(self, file_id: int, file_type: str = "dataset"):
        """ファイルの詳細を表示（新しい構造対応）"""
        if file_type == "dataset":
            dataset = self.dataset_repo.find_by_id(file_id)
            if not dataset:
                print(f"\nID {file_id} のデータセットが見つかりません。")
                return
            
            print(f"\n{'='*60}")
            print(f"データセット詳細: {dataset.name}")
            print(f"{'='*60}")
            
            print(f"説明: {dataset.description or 'なし'}")
            print(f"ファイル数: {dataset.file_count}")
            print(f"総サイズ: {dataset.total_size / (1024*1024):.2f} MB")
            print(f"作成日: {dataset.created_at}")
            
            if dataset.summary:
                print(f"\n要約:")
                print(f"  {dataset.summary}")
            
            # データセット内のファイルを表示
            dataset_files = self.dataset_file_repo.find_by_dataset_id(file_id)
            if dataset_files:
                print(f"\nファイル一覧:")
                for df in dataset_files[:5]:
                    print(f"  - {df.file_name} ({df.file_type})")
                if len(dataset_files) > 5:
                    print(f"  ... 他 {len(dataset_files) - 5} 件")
        
        elif file_type == "paper":
            paper = self.paper_repo.find_by_id(file_id)
            if not paper:
                print(f"\nID {file_id} の論文が見つかりません。")
                return
            
            print(f"\n{'='*60}")
            print(f"論文詳細: {paper.file_name}")
            print(f"{'='*60}")
            
            print(f"パス: {paper.file_path}")
            print(f"タイトル: {paper.title or 'なし'}")
            print(f"著者: {paper.authors or 'なし'}")
            print(f"サイズ: {paper.file_size / (1024*1024):.2f} MB")
            print(f"登録日: {paper.indexed_at}")
            
            if paper.abstract:
                print(f"\n要約:")
                print(f"  {paper.abstract}")
            
            if paper.keywords:
                print(f"\nキーワード: {paper.keywords}")
        
        else:  # poster
            poster = self.poster_repo.find_by_id(file_id)
            if not poster:
                print(f"\nID {file_id} のポスターが見つかりません。")
                return
            
            print(f"\n{'='*60}")
            print(f"ポスター詳細: {poster.file_name}")
            print(f"{'='*60}")
            
            print(f"パス: {poster.file_path}")
            print(f"タイトル: {poster.title or 'なし'}")
            print(f"著者: {poster.authors or 'なし'}")
            print(f"サイズ: {poster.file_size / (1024*1024):.2f} MB")
            print(f"登録日: {poster.indexed_at}")
            
            if poster.abstract:
                print(f"\n要約:")
                print(f"  {poster.abstract}")
            
            if poster.keywords:
                print(f"\nキーワード: {poster.keywords}")
    
    def enhanced_research_consultation(self):
        """拡張研究相談機能"""
        print("拡張研究相談システム\n")
        print("研究アイディアの構造化、関連研究の分析、研究計画の立案を支援します。")
        print("継続的な対話で文脈を保持し、より詳細なアドバイスを提供します。\n")
        
        consultation_type = InputHelper.get_choice(
            "相談タイプを選択:",
            ["新しい研究相談を開始", "既存の研究相談を継続", "研究相談履歴を確認"]
        )
        
        if consultation_type == "新しい研究相談を開始":
            query = InputHelper.get_string("研究アイディアや課題を詳しく教えてください: ", required=True)
            
            print("\n研究相談を開始しています...")
            result = self.enhanced_advisor.start_research_chat(query)
            
            self._display_enhanced_consultation_result(result)
            
            # 継続的な対話
            while True:
                continue_chat = InputHelper.get_yes_no("\n研究相談を続けますか？")
                if not continue_chat:
                    break
                
                follow_up = InputHelper.get_string("追加の質問や詳細化したい点: ", required=True)
                result = self.enhanced_advisor.continue_research_chat(follow_up)
                self._display_enhanced_consultation_result(result)
        
        elif consultation_type == "既存の研究相談を継続":
            history = self.enhanced_advisor.get_conversation_history()
            if not history:
                print("\n過去の研究相談履歴がありません。新しい相談を開始してください。")
                return
            
            print(f"\n前回の相談履歴が見つかりました（{len(history)}件の対話）")
            follow_up = InputHelper.get_string("追加の質問や詳細化したい点: ", required=True)
            result = self.enhanced_advisor.continue_research_chat(follow_up)
            self._display_enhanced_consultation_result(result)
        
        else:  # 履歴確認
            history = self.enhanced_advisor.get_conversation_history()
            if not history:
                print("\n研究相談履歴がありません。")
                return
            
            print(f"\n研究相談履歴（{len(history)}件）:")
            for i, entry in enumerate(history, 1):
                print(f"\n{i}. {entry['timestamp'][:19]}")
                print(f"   質問: {entry['user_query'][:100]}...")
                if entry.get('similar_docs'):
                    print(f"   関連文書: {len(entry['similar_docs'])}件")
                if entry.get('relevant_datasets'):
                    print(f"   関連データセット: {len(entry['relevant_datasets'])}件")
            
            # レポート出力オプション
            export_report = InputHelper.get_yes_no("\n相談内容をレポート形式でエクスポートしますか？")
            if export_report:
                report = self.enhanced_advisor.export_consultation_report()
                print("\n=== 研究相談レポート ===")
                print(f"相談日時: {report['consultation_date'][:19]}")
                print(f"総対話数: {report['total_queries']}")
                print(f"研究フォーカス: {report['overall_research_focus']}")
                print(f"推奨リソース数: {len(report['recommended_resources'])}")
    
    def _display_enhanced_consultation_result(self, result: dict):
        """拡張研究相談結果を表示"""
        if "error" in result:
            print(f"\nエラー: {result['error']}")
            return
        
        print(f"\n{'='*60}")
        print("研究アドバイス")
        print(f"{'='*60}")
        print(result.get("advice", "アドバイスの生成に失敗しました"))
        
        # 独自性評価
        if "originality_assessment" in result:
            assessment = result["originality_assessment"]
            print(f"\n--- 研究の独自性評価 ---")
            print(f"独自性スコア: {assessment['originality_score']:.1f}/1.0")
            print(f"評価: {assessment['assessment']}")
            print(f"類似研究数: {assessment['similar_research_count']}件")
        
        # 研究計画
        if "research_plan" in result:
            plan = result["research_plan"]
            print(f"\n--- 推奨研究計画 ---")
            print(f"予想期間: {plan.get('estimated_duration', '未定義')}")
            for phase_key, phase_info in plan.items():
                if phase_key.startswith("phase"):
                    print(f"• {phase_info['title']} ({phase_info['duration']})")
        
        # 関連文書
        if result.get("related_documents"):
            print(f"\n--- 関連研究文書 ({len(result['related_documents'])}件) ---")
            for doc in result["related_documents"][:3]:
                if doc["type"] == "paper":
                    print(f"• 論文: {doc.get('title', doc['file_name'])}")
                elif doc["type"] == "poster":
                    print(f"• ポスター: {doc.get('title', doc['file_name'])}")
                else:
                    print(f"• データセット: {doc['name']}")
        
        # 関連データセット
        if result.get("relevant_datasets"):
            print(f"\n--- 関連データセット ({len(result['relevant_datasets'])}件) ---")
            for ds in result["relevant_datasets"][:3]:
                print(f"• {ds['name']} ({ds['file_count']}ファイル)")
        
        # 次のアクション
        if result.get("next_actions"):
            print(f"\n--- 推奨する次のアクション ---")
            for action in result["next_actions"][:5]:
                print(f"• {action}")
    
    def dataset_consultation(self):
        """データセット詳細解説機能"""
        print("データセット詳細解説システム\n")
        
        consultation_type = InputHelper.get_choice(
            "解説タイプを選択:",
            ["特定データセットの詳細解説", "データセット一覧表示", "キーワードでデータセット検索"]
        )
        
        if consultation_type == "特定データセットの詳細解説":
            datasets = self.dataset_repo.find_all()
            if not datasets:
                print("\nデータセットが見つかりません。")
                return
            
            print("\n利用可能なデータセット:")
            for i, dataset in enumerate(datasets, 1):
                print(f"{i}. {dataset.name} ({dataset.file_count}ファイル)")
            
            try:
                choice = int(InputHelper.get_string(f"\n解説するデータセット番号 (1-{len(datasets)}): "))
                if 1 <= choice <= len(datasets):
                    selected_dataset = datasets[choice - 1]
                    
                    # ユーザーの質問を取得
                    user_question = InputHelper.get_string(
                        f"\n'{selected_dataset.name}'について何を知りたいですか？\n"
                        "（例：分析手法、活用方法、データ構造など。空白でも基本情報を表示）: ",
                        required=False
                    )
                    
                    print(f"\n'{selected_dataset.name}'について解説を生成中...")
                    result = self.dataset_advisor.explain_dataset(selected_dataset.name, user_question)
                    
                    self._display_dataset_explanation(result)
                else:
                    print("無効な番号です。")
            except ValueError:
                print("数値を入力してください。")
        
        elif consultation_type == "データセット一覧表示":
            overview = self.dataset_advisor.get_all_datasets_overview()
            self._display_datasets_overview(overview)
        
        else:  # キーワード検索
            keyword = InputHelper.get_string("検索キーワード: ", required=True)
            results = self.dataset_advisor.search_datasets_by_keyword(keyword)
            
            if results:
                print(f"\n'{keyword}'に関連するデータセット ({len(results)}件):")
                for result in results:
                    print(f"\n• {result['name']}")
                    print(f"  ファイル数: {result['file_count']}")
                    print(f"  ファイル種類: {', '.join(result['file_types'])}")
                    if result['summary']:
                        print(f"  概要: {result['summary'][:100]}...")
            else:
                print(f"\n'{keyword}'に関連するデータセットが見つかりませんでした。")
    
    def _display_dataset_explanation(self, result: dict):
        """データセット解説結果を表示"""
        if "error" in result:
            print(f"\nエラー: {result['error']}")
            if "available_datasets" in result:
                print("利用可能なデータセット:", ", ".join(result["available_datasets"]))
            return
        
        basic_info = result["basic_info"]
        
        print(f"\n{'='*60}")
        print(f"データセット詳細解説: {result['dataset_name']}")
        print(f"{'='*60}")
        
        print(f"概要: {basic_info.get('summary', '情報なし')}")
        print(f"ファイル数: {basic_info['total_files']}")
        print(f"総サイズ: {basic_info['total_size_mb']} MB")
        print(f"ファイル種類: {', '.join(basic_info['file_types'].keys())}")
        
        # 詳細解説（Gemini API生成）
        if result.get("detailed_explanation"):
            print(f"\n--- 詳細解説 ---")
            print(result["detailed_explanation"])
        
        # 分析手法提案
        if result.get("analysis_suggestions"):
            print(f"\n--- 推奨分析手法 ---")
            for suggestion in result["analysis_suggestions"][:3]:
                print(f"• {suggestion['method']} ({suggestion['difficulty']})")
                print(f"  {suggestion['description']}")
                print(f"  推奨ツール: {', '.join(suggestion['tools'])}")
        
        # 活用事例
        if result.get("use_case_suggestions"):
            print(f"\n--- 活用事例 ---")
            for use_case in result["use_case_suggestions"][:3]:
                print(f"• {use_case['title']} ({use_case['complexity']})")
                print(f"  {use_case['description']}")
                print(f"  研究分野: {use_case['research_field']}")
    
    def _display_datasets_overview(self, overview: dict):
        """データセット概要を表示"""
        if "error" in overview:
            print(f"\nエラー: {overview['error']}")
            return
        
        print(f"\n{'='*60}")
        print("データセット全体概要")
        print(f"{'='*60}")
        print(f"総データセット数: {overview['total_datasets']}")
        print(f"総ファイル数: {overview['total_files']}")
        print(f"総サイズ: {overview['total_size_mb']:.2f} MB")
        
        print(f"\n--- データセット一覧 ---")
        for dataset in overview["datasets"]:
            print(f"\n• {dataset['name']}")
            print(f"  ファイル数: {dataset['file_count']}")
            print(f"  サイズ: {dataset['size_mb']} MB")
            print(f"  種類: {', '.join(dataset['file_types'].keys())}")
            print(f"  要約: {'あり' if dataset['has_summary'] else 'なし'}")
    
    def research_structuring(self):
        """研究テーマ構造化機能"""
        print("研究テーマ構造化システム\n")
        print("研究アイディアを構造化し、可視化データを生成します。\n")
        
        structuring_type = InputHelper.get_choice(
            "機能を選択:",
            ["新しい研究テーマを構造化", "既存の構造化データを確認", "視覚的サマリーを生成"]
        )
        
        if structuring_type == "新しい研究テーマを構造化":
            research_query = InputHelper.get_string("研究テーマまたはアイディア: ", required=True)
            
            print("\n研究テーマを構造化中...")
            structure = self.research_visualizer.structure_research_theme(research_query)
            
            if "error" in structure:
                print(f"\nエラー: {structure['error']}")
                return
            
            self._display_research_structure(structure)
            
            # エクスポートオプション
            export_choice = InputHelper.get_choice(
                "\n構造化データをエクスポートしますか？",
                ["しない", "JSON形式", "テキストサマリー形式"]
            )
            
            if export_choice != "しない":
                format_type = "json" if export_choice == "JSON形式" else "summary"
                exported_data = self.research_visualizer.export_structure(structure["theme_id"], format_type)
                
                if exported_data:
                    print(f"\n--- エクスポート結果 ({format_type}) ---")
                    print(exported_data[:1000])  # 最初の1000文字
                    if len(exported_data) > 1000:
                        print("... (以下省略)")
        
        elif structuring_type == "既存の構造化データを確認":
            structures = self.research_visualizer.get_all_structures()
            
            if not structures:
                print("\n構造化されたデータがありません。")
                return
            
            print(f"\n構造化済み研究テーマ ({len(structures)}件):")
            for i, structure in enumerate(structures, 1):
                print(f"\n{i}. {structure['original_query'][:50]}...")
                print(f"   ID: {structure['theme_id']}")
                print(f"   作成日: {structure['created_at'][:19]}")
                print(f"   領域: {structure['domain']}")
                print(f"   手法: {structure['methodology']}")
        
        else:  # 視覚的サマリー生成
            structures = self.research_visualizer.get_all_structures()
            
            if not structures:
                print("\n構造化されたデータがありません。")
                return
            
            print("\n視覚的サマリーを生成する研究テーマを選択:")
            for i, structure in enumerate(structures, 1):
                print(f"{i}. {structure['original_query'][:50]}...")
            
            try:
                choice = int(InputHelper.get_string(f"\n番号 (1-{len(structures)}): "))
                if 1 <= choice <= len(structures):
                    selected_structure = structures[choice - 1]
                    
                    print("\n視覚的サマリーを生成中...")
                    summary = self.research_visualizer.generate_visual_summary(selected_structure["theme_id"])
                    
                    self._display_visual_summary(summary)
                else:
                    print("無効な番号です。")
            except ValueError:
                print("数値を入力してください。")
    
    def _display_research_structure(self, structure: dict):
        """研究構造を表示"""
        print(f"\n{'='*60}")
        print(f"研究テーマ構造化結果")
        print(f"{'='*60}")
        print(f"テーマID: {structure['theme_id']}")
        print(f"元クエリ: {structure['original_query']}")
        
        struct = structure["structure"]
        
        print(f"\n--- 研究課題 ---")
        rq = struct["research_question"]
        print(f"主要課題: {rq['primary_question']}")
        print(f"課題タイプ: {rq['question_type']}")
        print(f"明確性レベル: {rq['clarity_level']}")
        
        print(f"\n--- 研究領域 ---")
        domain = struct["domain"]
        print(f"主要領域: {domain['primary']}")
        print(f"信頼度: {domain['confidence']:.2f}")
        
        print(f"\n--- 研究手法 ---")
        methodology = struct["methodology"]
        print(f"推奨アプローチ: {methodology['primary_approach']}")
        print(f"具体的手法: {', '.join(methodology['suggested_methods'][:3])}")
        
        print(f"\n--- 研究目的 ---")
        objectives = struct["objectives"]
        print(f"主目的: {objectives['primary']}")
        
        print(f"\n--- 変数 ---")
        variables = struct["variables"]
        print(f"結果変数: {', '.join(variables['dependent_variables'])}")
        print(f"説明変数: {', '.join(variables['independent_variables'])}")
        
        # 可視化データの概要
        viz_data = structure["visualization_data"]
        print(f"\n--- 可視化データ概要 ---")
        print(f"ノード数: {len(viz_data['graph']['nodes'])}")
        print(f"エッジ数: {len(viz_data['graph']['edges'])}")
        print(f"研究期間: {viz_data['timeline'][-1]['end_date']} まで")
    
    def _display_visual_summary(self, summary: dict):
        """視覚的サマリーを表示"""
        if "error" in summary:
            print(f"\nエラー: {summary['error']}")
            return
        
        print(f"\n{'='*60}")
        print("視覚的サマリー")
        print(f"{'='*60}")
        
        overview = summary["components"]["overview"]
        print(f"研究タイトル: {overview['title']}")
        print(f"研究領域: {overview['domain']}")
        print(f"手法: {overview['methodology']}")
        print(f"複雑性: {overview['complexity']}")
        
        timeline = summary["components"]["timeline_summary"]
        print(f"\n期間: {timeline['total_duration']}")
        print(f"重要フェーズ: {', '.join(timeline['critical_phases'])}")
        
        viz_elements = summary["components"]["visualization_elements"]
        print(f"\n可視化要素:")
        print(f"  主要ノード: {viz_elements['primary_nodes']}")
        print(f"  総接続数: {viz_elements['total_connections']}")
        print(f"  階層レベル: {viz_elements['hierarchy_levels']}")
        
        relationships = summary["components"]["key_relationships"]
        print(f"\n重要な関係性:")
        for strength, relations in relationships.items():
            print(f"  {strength}: {', '.join(relations)}")
    
    def research_consultation(self):
        """レガシー互換性のため"""
        self.research_planning_consultation()
    
    def _start_database_chat(self):
        """データベース検索・相談チャット"""
        print("=" * 60)
        print("データベース検索・相談")
        print("=" * 60)
        print("登録済みのデータセット・論文・ポスターを検索し、活用方法をアドバイスします！")
        print("• データセット検索と詳細解説")
        print("• 論文・ポスター検索")
        print("• 既存研究の分析と活用提案")
        print("• データ活用手法の相談")
        print("• 関連研究の発見")
        print("\n'exit' または 'quit' で終了します。")
        print("例：「ESGデータを探している」「機械学習の論文はある？」「バイアス研究に使えるデータは？」\n")
        
        # チャット形式での継続対話
        while True:
            try:
                # ユーザー入力
                user_input = input("検索・相談: ").strip()
                
                if not user_input:
                    continue
                
                # 終了コマンド
                if user_input.lower() in ['exit', 'quit', '終了', 'やめる']:
                    print("\nデータベース検索アシスタント: ご利用ありがとうございました！有効活用できることをお祈りしています。\n")
                    break
                
                # AI応答の生成
                print("\nデータベース検索アシスタント: 検索中...")
                response = self._generate_database_response(user_input)
                
                print(f"\nデータベース検索アシスタント: {response}\n")
                print("-" * 60)
                
            except KeyboardInterrupt:
                print("\n\nデータベース検索アシスタント: 検索を終了します。\n")
                break
            except Exception as e:
                print(f"\nエラーが発生しました: {e}")
                print("もう一度お試しください。\n")
    
    def _start_research_planning_chat(self):
        """研究計画・相談チャット"""
        print("=" * 60)
        print("研究計画・相談")
        print("=" * 60)
        print("研究テーマの構造化から計画立案まで、研究活動全般をサポートします！")
        print("• 研究テーマの構造化・可視化")
        print("• 研究計画の立案支援")
        print("• 分析手法の提案")
        print("• 研究の独創性評価")
        print("• 論文執筆計画の支援")
        print("\n'exit' または 'quit' で終了します。")
        print("例：「医療AIの研究テーマを整理したい」「ESG研究の計画を立てたい」「どんな分析手法がいい？」\n")
        
        # チャット形式での継続対話
        while True:
            try:
                # ユーザー入力
                user_input = input("研究相談: ").strip()
                
                if not user_input:
                    continue
                
                # 終了コマンド
                if user_input.lower() in ['exit', 'quit', '終了', 'やめる']:
                    print("\n研究計画アシスタント: ご利用ありがとうございました！研究が成功することをお祈りしています。\n")
                    break
                
                # AI応答の生成
                print("\n研究計画アシスタント: 計画を検討中...")
                response = self._generate_research_planning_response(user_input)
                
                print(f"\n研究計画アシスタント: {response}\n")
                print("-" * 60)
                
            except KeyboardInterrupt:
                print("\n\n研究計画アシスタント: 相談を終了します。\n")
                break
            except Exception as e:
                print(f"\nエラーが発生しました: {e}")
                print("もう一度お試しください。\n")
    
    def _generate_database_response(self, user_input: str) -> str:
        """データベース検索・相談応答を生成"""
        try:
            # 関連研究とデータセットを検索
            similar_docs = self.enhanced_advisor._find_similar_documents_enhanced(user_input)
            relevant_datasets = self.enhanced_advisor._find_relevant_datasets(user_input)
            
            # データベース特化プロンプト
            response = self._generate_database_llm_response(user_input, similar_docs, relevant_datasets)
            
            return response or "申し訳ございません。システムエラーが発生しました。もう一度お試しください。"
            
        except Exception as e:
            logger.error(f"データベース検索応答生成エラー: {e}")
            return "申し訳ございません。システムエラーが発生しました。もう一度お試しください。"
    
    def _generate_research_planning_response(self, user_input: str) -> str:
        """研究計画・相談応答を生成"""
        try:
            # 研究テーマ構造化と計画立案
            research_structure = self.research_visualizer.structure_research_theme(user_input)
            
            # 関連研究も参考として検索
            similar_docs = self.enhanced_advisor._find_similar_documents_enhanced(user_input)
            relevant_datasets = self.enhanced_advisor._find_relevant_datasets(user_input)
            
            # 研究計画特化プロンプト
            response = self._generate_research_planning_llm_response(
                user_input, research_structure, similar_docs, relevant_datasets
            )
            
            return response or "申し訳ございません。システムエラーが発生しました。もう一度お試しください。"
            
        except Exception as e:
            logger.error(f"研究計画応答生成エラー: {e}")
            return "申し訳ございません。システムエラーが発生しました。もう一度お試しください。"
    
    def _generate_integrated_response(self, user_input: str) -> str:
        """レガシー互換性のため"""
        return self._generate_database_response(user_input)
    
    def _generate_database_llm_response(self, user_input: str, similar_docs: list, relevant_datasets: list) -> str:
        """データベース検索特化LLM応答生成"""
        # データベース情報を整理
        datasets_info = self._prepare_datasets_context(relevant_datasets)
        documents_info = self._prepare_documents_context(similar_docs)
        
        # データベース検索特化プロンプト
        prompt = f"""あなたはデータベース検索の専門アシスタントです。
登録済みのデータセット・論文・ポスターの検索と活用支援に特化して対応します。

【ユーザーの検索要求】
{user_input}

【検索結果 - データセット】
{datasets_info}

【検索結果 - 研究文書】
{documents_info}

【あなたの専門分野】
- データベース内のリソース検索と特定
- 見つかったデータセットの詳細解説
- 論文・ポスターの内容紹介
- データ活用手法の具体的提案
- 関連研究間の関係性分析
- 実践的な分析アプローチの提案

【応答のフォーカス】
1. 検索結果の詳細紹介（ファイル数、内容、特徴など）
2. 具体的な活用方法とデータ分析手法
3. 関連するリソース間の関係性
4. 追加で探すべきデータや関連研究の提案

【応答要件】
- 見つかったリソースの具体的な情報を詳しく紹介
- データの特徴や分析可能性を具体的に説明
- 実際の研究での活用例を提示
- 400-600字程度で詳細かつ実用的に

データベースの豊富なリソースを最大限活用できるよう支援してください。"""

        try:
            response = self.enhanced_advisor.gemini_client.generate_research_advice_enhanced(prompt)
            return response
        except Exception as e:
            logger.error(f"データベース検索LLM応答生成エラー: {e}")
            return None
    
    def _generate_research_planning_llm_response(self, user_input: str, research_structure: dict, similar_docs: list, relevant_datasets: list) -> str:
        """研究計画特化LLM応答生成"""
        # 構造化された研究テーマ情報を準備
        structure_info = self._prepare_research_structure_context(research_structure)
        datasets_info = self._prepare_datasets_context(relevant_datasets)
        documents_info = self._prepare_documents_context(similar_docs)
        
        # 研究計画特化プロンプト
        prompt = f"""あなたは研究計画・方法論の専門アドバイザーです。
研究テーマの構造化、計画立案、方法論の提案に特化して支援します。

【ユーザーの研究相談】
{user_input}

【構造化された研究テーマ分析】
{structure_info}

【参考リソース - データセット】
{datasets_info}

【参考リソース - 関連研究】
{documents_info}

【あなたの専門分野】
- 研究テーマの構造化と明確化
- 研究計画の立案と段階的アプローチ
- 研究方法論の選択と提案
- 理論的枠組みの構築支援
- 研究の独創性と意義の評価
- 論文執筆計画の策定

【応答のフォーカス】
1. 研究テーマの構造化と問題設定の明確化
2. 適切な研究方法論とアプローチの提案
3. 段階的な研究計画とタイムライン
4. 理論的背景と先行研究の位置づけ
5. 研究の独創性と学術的貢献の可能性

【応答要件】
- 研究の方向性を明確に示す
- 具体的で実行可能な計画を提示
- 学術的価値と独創性を重視
- 段階的なアプローチを提案
- 500-700字程度で包括的に

質の高い研究計画の策定を全面的に支援してください。"""

        try:
            response = self.enhanced_advisor.gemini_client.generate_research_advice_enhanced(prompt)
            return response
        except Exception as e:
            logger.error(f"研究計画LLM応答生成エラー: {e}")
            return None
    
    def _prepare_research_structure_context(self, research_structure: dict) -> str:
        """研究構造情報をLLM用に準備"""
        if not research_structure or 'structure' not in research_structure:
            return "研究テーマの構造化情報なし"
        
        structure = research_structure['structure']
        context_parts = []
        
        if 'research_question' in structure:
            rq = structure['research_question']
            context_parts.append(f"研究課題: {rq.get('primary_question', '')}")
            context_parts.append(f"課題タイプ: {rq.get('question_type', '')}")
        
        if 'domain' in structure:
            domain = structure['domain']
            context_parts.append(f"研究領域: {domain.get('primary', '')} (信頼度: {domain.get('confidence', 0):.2f})")
        
        if 'methodology' in structure:
            method = structure['methodology']
            context_parts.append(f"推奨手法: {method.get('primary_approach', '')}")
            context_parts.append(f"具体的手法: {', '.join(method.get('suggested_methods', []))}")
        
        if 'objectives' in structure:
            obj = structure['objectives']
            context_parts.append(f"主要目的: {obj.get('primary', '')}")
        
        return "\n".join(context_parts) if context_parts else "研究構造情報なし"
    
    def _generate_unified_llm_response(self, user_input: str, similar_docs: list, relevant_datasets: list) -> str:
        """レガシー互換性のため"""
        return self._generate_database_llm_response(user_input, similar_docs, relevant_datasets)
    
    def _generate_llm_response(self, user_input: str, similar_docs: list, relevant_datasets: list) -> str:
        """レガシー互換性のため"""
        return self._generate_unified_llm_response(user_input, similar_docs, relevant_datasets)
    
    def _prepare_datasets_context(self, datasets: list) -> str:
        """データセット情報をLLM用に準備"""
        if not datasets:
            return "利用可能なデータセットはありません。"
        
        context_parts = ["利用可能なデータセット:"]
        for ds in datasets[:5]:  # 上位5つ
            context_parts.append(f"- {ds.get('name', 'Unknown')}")
            if ds.get('summary'):
                context_parts.append(f"  概要: {ds['summary'][:200]}")
            if ds.get('file_count'):
                context_parts.append(f"  ファイル数: {ds['file_count']}")
            if ds.get('description'):
                context_parts.append(f"  説明: {ds['description'][:150]}")
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def _prepare_documents_context(self, documents: list) -> str:
        """研究文書情報をLLM用に準備"""
        if not documents:
            return "関連する研究文書はありません。"
        
        context_parts = ["関連する研究文書:"]
        for doc in documents[:5]:  # 上位5つ
            if doc["type"] == "paper":
                title = doc.get('title', doc['file_name'])
                context_parts.append(f"- 論文: {title}")
                if doc.get('authors'):
                    context_parts.append(f"  著者: {doc['authors']}")
                if doc.get('abstract'):
                    context_parts.append(f"  要約: {doc['abstract'][:200]}")
            elif doc["type"] == "poster":
                title = doc.get('title', doc['file_name'])
                context_parts.append(f"- ポスター: {title}")
                if doc.get('authors'):
                    context_parts.append(f"  著者: {doc['authors']}")
                if doc.get('abstract'):
                    context_parts.append(f"  要約: {doc['abstract'][:200]}")
            else:
                context_parts.append(f"- データセット: {doc['name']}")
                if doc.get('summary'):
                    context_parts.append(f"  要約: {doc['summary'][:200]}")
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def _handle_dataset_query(self, query: str):
        """データセット関連の質問処理"""
        # データセット名が含まれているかチェック
        datasets = self.dataset_repo.find_all()
        mentioned_dataset = None
        
        for dataset in datasets:
            if dataset.name.lower() in query.lower():
                mentioned_dataset = dataset
                break
        
        if mentioned_dataset:
            print(f"\n'{mentioned_dataset.name}'に関する質問として処理します...")
            result = self.dataset_advisor.explain_dataset(mentioned_dataset.name, query)
            self._display_dataset_explanation(result)
        else:
            # データセット一覧を表示して選択を促す
            print("\n利用可能なデータセット:")
            for i, dataset in enumerate(datasets, 1):
                print(f"{i}. {dataset.name} ({dataset.file_count}ファイル)")
            
            try:
                choice = int(InputHelper.get_string(f"\n関連するデータセット番号 (1-{len(datasets)}): "))
                if 1 <= choice <= len(datasets):
                    selected_dataset = datasets[choice - 1]
                    result = self.dataset_advisor.explain_dataset(selected_dataset.name, query)
                    self._display_dataset_explanation(result)
                else:
                    print("無効な番号です。一般的な研究相談として処理します...")
                    self._handle_general_consultation(query)
            except ValueError:
                print("一般的な研究相談として処理します...")
                self._handle_general_consultation(query)
    
    def _handle_structuring_query(self, query: str):
        """研究構造化関連の質問処理"""
        print(f"\n研究テーマを構造化して分析します...")
        structure = self.research_visualizer.structure_research_theme(query)
        
        if "error" in structure:
            print(f"\nエラー: {structure['error']}")
            return
        
        self._display_research_structure(structure)
        
        # 追加で拡張研究相談も実行
        print("\n\n関連する研究アドバイスも生成します...")
        consultation_result = self.enhanced_advisor.start_research_chat(query)
        self._display_enhanced_consultation_result(consultation_result)
    
    def _handle_general_consultation(self, query: str):
        """一般的な研究相談処理"""
        print(f"\n包括的な研究アドバイスを生成します...")
        result = self.enhanced_advisor.start_research_chat(query)
        self._display_enhanced_consultation_result(result)
        
        # 継続対話の提案
        while True:
            continue_chat = InputHelper.get_yes_no("\n追加の質問や詳細化したい点はありますか？")
            if not continue_chat:
                break
            
            follow_up = InputHelper.get_string("追加の質問: ", required=True)
            follow_result = self.enhanced_advisor.continue_research_chat(follow_up)
            self._display_enhanced_consultation_result(follow_result)
    
    def analyze_files(self):
        """ファイル解析（新しい構造対応）"""
        print("ファイル解析\n")
        
        analyze_type = InputHelper.get_choice(
            "解析対象を選択:",
            ["データセット解析", "論文解析", "ポスター解析", "全て解析"]
        )
        
        if analyze_type == "データセット解析":
            datasets = self.dataset_repo.find_all()
            if not datasets:
                print("\nデータセットが見つかりません。")
                return
            
            print("\n利用可能なデータセット:")
            for i, dataset in enumerate(datasets, 1):
                status = "解析済み" if dataset.summary else "未解析"
                print(f"  {i}. {dataset.name} ({status})")
            
            choice = InputHelper.get_integer("解析するデータセットの番号: ") - 1
            if 0 <= choice < len(datasets):
                print("\n解析中...")
                result = self.analyzer.analyze_dataset(datasets[choice].id)
                if result:
                    print("\n解析結果:")
                    print(f"要約: {result.get('summary', 'なし')}")
                    print(f"主な目的: {result.get('main_purpose', 'なし')}")
                else:
                    print("\n解析に失敗しました。")
        
        elif analyze_type == "論文解析":
            papers = self.paper_repo.find_all()
            if not papers:
                print("\n論文が見つかりません。")
                return
            
            print("\n利用可能な論文:")
            for i, paper in enumerate(papers[:10], 1):  # 最初の10件
                status = "解析済み" if paper.abstract else "未解析"
                print(f"  {i}. {paper.file_name[:50]} ({status})")
            
            choice = InputHelper.get_integer("解析する論文の番号: ") - 1
            if 0 <= choice < len(papers):
                print("\n解析中...")
                result = self.analyzer.analyze_paper(papers[choice].id)
                if result:
                    print("\n解析完了")
                else:
                    print("\n解析に失敗しました。")
        
        elif analyze_type == "ポスター解析":
            posters = self.poster_repo.find_all()
            if not posters:
                print("\nポスターが見つかりません。")
                return
            
            print("\n利用可能なポスター:")
            for i, poster in enumerate(posters[:10], 1):  # 最初の10件
                status = "解析済み" if poster.abstract else "未解析"
                print(f"  {i}. {poster.file_name[:50]} ({status})")
            
            choice = InputHelper.get_integer("解析するポスターの番号: ") - 1
            if 0 <= choice < len(posters):
                print("\n解析中...")
                result = self.analyzer.analyze_poster(posters[choice].id)
                if result:
                    print("\n解析完了")
                else:
                    print("\n解析に失敗しました。")
        
        else:  # 全て解析
            print("\n全体解析を開始します...")
            
            # データセット解析
            datasets = [d for d in self.dataset_repo.find_all() if not d.summary]
            for dataset in datasets:
                print(f"データセット解析中: {dataset.name}")
                self.analyzer.analyze_dataset(dataset.id)
            
            # 論文解析
            papers = [p for p in self.paper_repo.find_all() if not p.abstract]
            for paper in papers:
                print(f"論文解析中: {paper.file_name}")
                self.analyzer.analyze_paper(paper.id)
            
            # ポスター解析
            posters = [p for p in self.poster_repo.find_all() if not p.abstract]
            for poster in posters:
                print(f"ポスター解析中: {poster.file_name}")
                self.analyzer.analyze_poster(poster.id)
            
            print(f"\n解析完了: データセット{len(datasets)}件、論文{len(papers)}件、ポスター{len(posters)}件")
    
    
    def show_statistics(self):
        """統計情報表示（新しい構造対応）"""
        print("統計情報\n")
        
        stat_type = InputHelper.get_choice(
            "表示する統計を選択:",
            ["全体統計", "データセット統計", "論文統計", "ポスター統計", "解析統計"]
        )
        
        if stat_type == "全体統計":
            datasets = self.dataset_repo.find_all()
            papers = self.paper_repo.find_all()
            posters = self.poster_repo.find_all()
            
            total_dataset_size = sum(d.total_size for d in datasets)
            total_dataset_files = sum(d.file_count for d in datasets)
            
            stats = {
                "データセット数": len(datasets),
                "論文数": len(papers),
                "ポスター数": len(posters),
                "総ファイル数（データセット内）": total_dataset_files,
                "総データサイズ(MB)": f"{total_dataset_size / (1024*1024):.2f}"
            }
            
            print("\n全体統計:")
            TableDisplay.display_dict(stats)
        
        elif stat_type == "データセット統計":
            datasets = self.dataset_repo.find_all()
            analyzed_count = sum(1 for d in datasets if d.summary)
            
            print(f"\nデータセット統計:")
            print(f"  総数: {len(datasets)}個")
            print(f"  解析済み: {analyzed_count}個")
            print(f"  解析率: {analyzed_count/len(datasets)*100:.1f}%" if datasets else "0%")
            
            if datasets:
                print("\n各データセット:")
                for dataset in datasets:
                    size_mb = dataset.total_size / (1024*1024)
                    status = "✓" if dataset.summary else "×"
                    print(f"  {status} {dataset.name}: {dataset.file_count}ファイル ({size_mb:.2f}MB)")
        
        elif stat_type == "論文統計":
            papers = self.paper_repo.find_all()
            analyzed_count = sum(1 for p in papers if p.abstract)
            
            print(f"\n論文統計:")
            print(f"  総数: {len(papers)}件")
            print(f"  解析済み: {analyzed_count}件")
            print(f"  解析率: {analyzed_count/len(papers)*100:.1f}%" if papers else "0%")
        
        elif stat_type == "ポスター統計":
            posters = self.poster_repo.find_all()
            analyzed_count = sum(1 for p in posters if p.abstract)
            
            print(f"\nポスター統計:")
            print(f"  総数: {len(posters)}件")
            print(f"  解析済み: {analyzed_count}件")
            print(f"  解析率: {analyzed_count/len(posters)*100:.1f}%" if posters else "0%")
        
        else:  # 解析統計
            analysis_summary = self.analyzer.get_analysis_summary()
            print("\n解析統計:")
            TableDisplay.display_dict(analysis_summary)
    
    def data_management(self):
        """データ管理"""
        submenu = Menu("データ管理")
        submenu.add_option("1", "新規ファイル登録", self._register_new_file)
        submenu.add_option("2", "ファイル削除", self._delete_file)
        submenu.add_option("3", "ファイル移動", self._move_file)
        submenu.add_option("4", "メタデータ更新", self._update_metadata)
        submenu.add_option("5", "エクスポート", self._export_data)
        
        submenu.display()
        choice = input("\n選択してください: ").strip()
        
        if choice in submenu.options:
            submenu.options[choice]["action"]()
    
    def _register_new_file(self):
        """新規ファイル登録（新しい構造対応）"""
        print("新規ファイル登録\n")
        print("注意: 新しいファイルはデータインデックスの更新で自動登録されます。")
        print("手動登録は特別な場合のみ使用してください。\n")
        
        if not InputHelper.get_yes_no("手動登録を続行しますか？"):
            return
        
        print("データインデックスの更新を実行してください。")
    
    def _delete_file(self):
        """ファイル削除（新しい構造対応）"""
        print("ファイル削除\n")
        
        delete_type = InputHelper.get_choice(
            "削除対象を選択:",
            ["データセット", "論文", "ポスター"]
        )
        
        if delete_type == "データセット":
            datasets = self.dataset_repo.find_all()
            if not datasets:
                print("データセットがありません。")
                return
            
            for i, dataset in enumerate(datasets, 1):
                print(f"  {i}. {dataset.name} ({dataset.file_count}ファイル)")
            
            choice = InputHelper.get_integer("削除するデータセットの番号: ") - 1
            if 0 <= choice < len(datasets):
                dataset = datasets[choice]
                if InputHelper.get_yes_no(f"データセット '{dataset.name}' を削除しますか？"):
                    # データセットファイルを削除
                    self.dataset_file_repo.delete_by_dataset_id(dataset.id)
                    # データセットを削除
                    if self.dataset_repo.delete(dataset.id):
                        print(f"\nデータセット '{dataset.name}' を削除しました。")
                    else:
                        print("\n削除に失敗しました。")
        
        elif delete_type == "論文":
            papers = self.paper_repo.find_all()
            if not papers:
                print("論文がありません。")
                return
                
            for i, paper in enumerate(papers[:10], 1):
                print(f"  {i}. {paper.file_name[:50]}")
            
            choice = InputHelper.get_integer("削除する論文の番号: ") - 1
            if 0 <= choice < len(papers):
                paper = papers[choice]
                if InputHelper.get_yes_no(f"論文 '{paper.file_name}' を削除しますか？"):
                    print(f"\n論文 '{paper.file_name}' を削除しました。")
        
        else:  # ポスター
            posters = self.poster_repo.find_all()
            if not posters:
                print("ポスターがありません。")
                return
                
            for i, poster in enumerate(posters[:10], 1):
                print(f"  {i}. {poster.file_name[:50]}")
            
            choice = InputHelper.get_integer("削除するポスターの番号: ") - 1
            if 0 <= choice < len(posters):
                poster = posters[choice]
                if InputHelper.get_yes_no(f"ポスター '{poster.file_name}' を削除しますか？"):
                    print(f"\nポスター '{poster.file_name}' を削除しました。")
    
    def _move_file(self):
        """ファイル移動（新しい構造対応）"""
        print("ファイル移動\n")
        print("注意: ファイル移動は物理ファイルシステムで行ってください。")
        print("移動後にデータインデックスを更新してください。")
    
    def _update_metadata(self):
        """メタデータ更新（新しい構造対応）"""
        print("メタデータ更新\n")
        
        update_type = InputHelper.get_choice(
            "更新対象を選択:",
            ["データセット情報", "論文情報", "ポスター情報"]
        )
        
        if update_type == "データセット情報":
            datasets = self.dataset_repo.find_all()
            if not datasets:
                print("データセットがありません。")
                return
            
            for i, dataset in enumerate(datasets, 1):
                print(f"  {i}. {dataset.name}")
            
            choice = InputHelper.get_integer("更新するデータセットの番号: ") - 1
            if 0 <= choice < len(datasets):
                dataset = datasets[choice]
                new_description = InputHelper.get_string(f"新しい説明 ({dataset.description or 'なし'}): ", required=False)
                if new_description:
                    dataset.description = new_description
                    if self.dataset_repo.update(dataset):
                        print("\nデータセット情報を更新しました。")
        
        elif update_type == "論文情報":
            papers = self.paper_repo.find_all()
            if not papers:
                print("論文がありません。")
                return
            
            for i, paper in enumerate(papers[:10], 1):
                print(f"  {i}. {paper.file_name[:50]}")
            
            choice = InputHelper.get_integer("更新する論文の番号: ") - 1
            if 0 <= choice < len(papers):
                paper = papers[choice]
                new_title = InputHelper.get_string(f"新しいタイトル ({paper.title or 'なし'}): ", required=False)
                new_authors = InputHelper.get_string(f"新しい著者 ({paper.authors or 'なし'}): ", required=False)
                
                if new_title:
                    paper.title = new_title
                if new_authors:
                    paper.authors = new_authors
                
                if new_title or new_authors:
                    if self.paper_repo.update(paper):
                        print("\n論文情報を更新しました。")
        
        else:  # ポスター情報
            posters = self.poster_repo.find_all()
            if not posters:
                print("ポスターがありません。")
                return
            
            for i, poster in enumerate(posters[:10], 1):
                print(f"  {i}. {poster.file_name[:50]}")
            
            choice = InputHelper.get_integer("更新するポスターの番号: ") - 1
            if 0 <= choice < len(posters):
                poster = posters[choice]
                new_title = InputHelper.get_string(f"新しいタイトル ({poster.title or 'なし'}): ", required=False)
                new_authors = InputHelper.get_string(f"新しい著者 ({poster.authors or 'なし'}): ", required=False)
                
                if new_title:
                    poster.title = new_title
                if new_authors:
                    poster.authors = new_authors
                
                if new_title or new_authors:
                    print("\nポスター情報を更新しました。")
    
    def _export_data(self):
        """データエクスポート（新しい構造対応）"""
        print("データエクスポート\n")
        
        export_type = InputHelper.get_choice(
            "エクスポート対象を選択:",
            ["データセット一覧", "論文一覧", "ポスター一覧", "全データ"]
        )
        
        format_type = InputHelper.get_choice("形式:", ["JSON", "CSV"])
        filename = InputHelper.get_string("保存ファイル名: ", required=False)
        
        if not filename:
            prefix = export_type.replace("一覧", "").replace("全", "all_")
            filename = f"{prefix}_export.{'json' if format_type == 'JSON' else 'csv'}"
        
        # データを収集
        if export_type == "データセット一覧":
            datasets = self.dataset_repo.find_all()
            data = [{
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "file_count": d.file_count,
                "total_size_mb": f"{d.total_size / (1024*1024):.2f}",
                "summary": d.summary,
                "created_at": d.created_at
            } for d in datasets]
        
        elif export_type == "論文一覧":
            papers = self.paper_repo.find_all()
            data = [{
                "id": p.id,
                "file_name": p.file_name,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "keywords": p.keywords,
                "indexed_at": p.indexed_at
            } for p in papers]
        
        elif export_type == "ポスター一覧":
            posters = self.poster_repo.find_all()
            data = [{
                "id": p.id,
                "file_name": p.file_name,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "keywords": p.keywords,
                "indexed_at": p.indexed_at
            } for p in posters]
        
        else:  # 全データ
            datasets = self.dataset_repo.find_all()
            papers = self.paper_repo.find_all()
            posters = self.poster_repo.find_all()
            data = {
                "datasets": [d.__dict__ for d in datasets],
                "papers": [p.__dict__ for p in papers],
                "posters": [p.__dict__ for p in posters]
            }
        
        # ファイルに書き込み
        if format_type == "JSON":
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:  # CSV
            if export_type == "全データ":
                print("\nCSV形式では全データエクスポートはサポートされていません。")
                return
            
            import csv
            with open(filename, 'w', encoding='utf-8', newline='') as f:
                if data:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
        
        print(f"\nデータを {filename} にエクスポートしました。")
    
    def settings(self):
        """設定"""
        print("設定\n")
        
        print("現在の設定:")
        print(f"  データディレクトリ: data/")
        print(f"  データベース: agent/database/research_data.db")
        print(f"  Geminiモデル: gemini-1.5-pro")
        print(f"  最大ファイルサイズ: 100 MB")
        print(f"\n設定の変更は .env ファイルを編集してください。")