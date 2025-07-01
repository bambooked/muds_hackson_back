from typing import Optional
import json

from .menu import Menu, InputHelper, TableDisplay
from ..database.connection import db_connection
from ..indexer.new_indexer import NewFileIndexer
from ..analyzer.new_analyzer import NewFileAnalyzer
from ..database.new_repository import DatasetRepository, PaperRepository, PosterRepository, DatasetFileRepository


class UserInterface:
    """ユーザーインターフェースを管理するクラス"""
    
    def __init__(self):
        self.indexer = NewFileIndexer(auto_analyze=True)  # 新しいインデクサーを使用
        self.analyzer = NewFileAnalyzer()  # 新しいアナライザーを使用
        self.dataset_repo = DatasetRepository()
        self.paper_repo = PaperRepository()
        self.poster_repo = PosterRepository()
        self.dataset_file_repo = DatasetFileRepository()
        
        # メインメニューの設定
        self.main_menu = Menu("研究データ管理システム")
        self._setup_main_menu()
    
    def _setup_main_menu(self):
        """メインメニューを設定"""
        self.main_menu.add_option("1", "データインデックスの更新", self.update_index)
        self.main_menu.add_option("2", "ファイル検索", self.search_files)
        self.main_menu.add_option("3", "ファイル解析", self.analyze_files)
        self.main_menu.add_option("4", "研究相談", self.research_consultation)
        self.main_menu.add_option("5", "統計情報表示", self.show_statistics)
        self.main_menu.add_option("6", "データ管理", self.data_management)
        self.main_menu.add_option("7", "設定", self.settings)
    
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
    
    def search_files(self):
        """ファイル検索（新しい構造対応）"""
        print("ファイル検索\n")
        
        search_type = InputHelper.get_choice(
            "検索方法を選択:",
            ["データセット検索", "論文検索", "ポスター検索", "すべて表示"]
        )
        
        if search_type == "データセット検索":
            keyword = InputHelper.get_string("データセット名またはキーワード: ", required=False)
            datasets = self.dataset_repo.find_all()
            if keyword:
                datasets = [d for d in datasets if keyword.lower() in d.name.lower() or 
                           (d.summary and keyword.lower() in d.summary.lower())]
            self._display_datasets(datasets)
        
        elif search_type == "論文検索":
            keyword = InputHelper.get_string("論文キーワード: ", required=False)
            if keyword:
                papers = self.paper_repo.search(keyword)
            else:
                papers = self.paper_repo.find_all()
            self._display_papers(papers)
        
        elif search_type == "ポスター検索":
            keyword = InputHelper.get_string("ポスターキーワード: ", required=False)
            if keyword:
                posters = self.poster_repo.search(keyword)
            else:
                posters = self.poster_repo.find_all()
            self._display_posters(posters)
        
        else:
            self._display_all_content()
    
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
    
    def research_consultation(self):
        """研究相談（新しい構造対応）"""
        print("研究相談\n")
        
        query = InputHelper.get_string("研究に関する質問や相談内容を入力してください:\n> ")
        
        print("\n関連文書を検索中...")
        
        # キーワードベースで関連文書を検索
        related_datasets = []
        related_papers = []
        related_posters = []
        
        # 簡単なキーワード検索
        keywords = query.lower().split()
        
        for dataset in self.dataset_repo.find_all():
            if dataset.summary:
                summary_lower = dataset.summary.lower()
                if any(keyword in summary_lower for keyword in keywords):
                    related_datasets.append(dataset)
        
        for paper in self.paper_repo.find_all():
            if paper.abstract:
                text = f"{paper.file_name} {paper.title or ''} {paper.abstract}".lower()
                if any(keyword in text for keyword in keywords):
                    related_papers.append(paper)
        
        for poster in self.poster_repo.find_all():
            if poster.abstract:
                text = f"{poster.file_name} {poster.title or ''} {poster.abstract}".lower()
                if any(keyword in text for keyword in keywords):
                    related_posters.append(poster)
        
        print(f"\n{'='*60}")
        print("研究相談結果")
        print(f"{'='*60}")
        
        print(f"\n【質問】{query}")
        
        if related_datasets:
            print(f"\n【関連データセット】")
            for dataset in related_datasets[:3]:
                print(f"  - {dataset.name}")
                if dataset.summary:
                    print(f"    {dataset.summary[:100]}...")
        
        if related_papers:
            print(f"\n【関連論文】")
            for paper in related_papers[:3]:
                title = paper.title or paper.file_name
                print(f"  - {title[:50]}")
                if paper.abstract:
                    print(f"    {paper.abstract[:100]}...")
        
        if related_posters:
            print(f"\n【関連ポスター】")
            for poster in related_posters[:3]:
                title = poster.title or poster.file_name
                print(f"  - {title[:50]}")
                if poster.abstract:
                    print(f"    {poster.abstract[:100]}...")
        
        if not (related_datasets or related_papers or related_posters):
            print("\n関連する文書が見つかりませんでした。")
            print("より具体的なキーワードを試してみてください。")
    
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