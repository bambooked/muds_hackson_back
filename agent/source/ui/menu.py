from typing import Dict, Any, Callable, Optional
import os
import sys


class Menu:
    """コマンドラインメニューを管理するクラス"""
    
    def __init__(self, title: str = "メニュー"):
        self.title = title
        self.options = {}
        self.prompt = "\n選択してください: "
    
    def add_option(self, key: str, description: str, action: Callable):
        """メニューオプションを追加"""
        self.options[key] = {
            "description": description,
            "action": action
        }
    
    def display(self):
        """メニューを表示"""
        self._clear_screen()
        print("=" * 60)
        print(f"{self.title:^60}")
        print("=" * 60)
        print()
        
        for key, option in sorted(self.options.items()):
            print(f"  [{key}] {option['description']}")
        
        print(f"\n  [0] 終了")
        print("=" * 60)
    
    def run(self):
        """メニューを実行"""
        while True:
            self.display()
            choice = input(self.prompt).strip()
            
            if choice == "0":
                print("\n終了します...")
                break
            
            if choice in self.options:
                print()
                try:
                    self.options[choice]["action"]()
                except Exception as e:
                    print(f"\nエラーが発生しました: {e}")
                
                input("\n続行するにはEnterキーを押してください...")
            else:
                print("\n無効な選択です。もう一度お試しください。")
                input("続行するにはEnterキーを押してください...")
    
    def _clear_screen(self):
        """画面をクリア"""
        os.system('cls' if os.name == 'nt' else 'clear')


class InputHelper:
    """入力補助機能を提供するクラス"""
    
    @staticmethod
    def get_string(prompt: str, required: bool = True) -> Optional[str]:
        """文字列を取得"""
        while True:
            value = input(prompt).strip()
            if value or not required:
                return value
            print("値を入力してください。")
    
    @staticmethod
    def get_integer(prompt: str, min_val: int = None, max_val: int = None) -> int:
        """整数を取得"""
        while True:
            try:
                value = int(input(prompt).strip())
                if min_val is not None and value < min_val:
                    print(f"{min_val}以上の値を入力してください。")
                    continue
                if max_val is not None and value > max_val:
                    print(f"{max_val}以下の値を入力してください。")
                    continue
                return value
            except ValueError:
                print("有効な整数を入力してください。")
    
    @staticmethod
    def get_choice(prompt: str, options: list) -> str:
        """選択肢から選択"""
        print(prompt)
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")
        
        while True:
            try:
                choice = int(input("\n番号を選択: ").strip())
                if 1 <= choice <= len(options):
                    return options[choice - 1]
                print(f"1から{len(options)}の間で選択してください。")
            except ValueError:
                print("有効な番号を入力してください。")
    
    @staticmethod
    def get_yes_no(prompt: str) -> bool:
        """Yes/No選択"""
        while True:
            response = input(f"{prompt} (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            print("'y' または 'n' を入力してください。")
    
    @staticmethod
    def get_file_path(prompt: str, must_exist: bool = True) -> Optional[str]:
        """ファイルパスを取得"""
        while True:
            path = input(prompt).strip()
            if not path:
                return None
            
            # 引用符を除去
            if path.startswith('"') and path.endswith('"'):
                path = path[1:-1]
            elif path.startswith("'") and path.endswith("'"):
                path = path[1:-1]
            
            if must_exist:
                if os.path.exists(path):
                    return path
                else:
                    print(f"ファイルが存在しません: {path}")
                    if not InputHelper.get_yes_no("もう一度試しますか？"):
                        return None
            else:
                return path


class TableDisplay:
    """テーブル形式で表示するクラス"""
    
    @staticmethod
    def display_table(headers: list, rows: list, max_width: int = 30):
        """テーブルを表示"""
        # 各カラムの最大幅を計算
        col_widths = []
        for i, header in enumerate(headers):
            max_len = len(str(header))
            for row in rows:
                if i < len(row):
                    cell_len = len(str(row[i]))
                    max_len = max(max_len, cell_len)
            col_widths.append(min(max_len, max_width))
        
        # ヘッダーを表示
        TableDisplay._print_separator(col_widths)
        TableDisplay._print_row(headers, col_widths)
        TableDisplay._print_separator(col_widths)
        
        # データ行を表示
        for row in rows:
            TableDisplay._print_row(row, col_widths)
        
        TableDisplay._print_separator(col_widths)
    
    @staticmethod
    def _print_separator(col_widths: list):
        """区切り線を表示"""
        parts = ["-" * (width + 2) for width in col_widths]
        print("+" + "+".join(parts) + "+")
    
    @staticmethod
    def _print_row(row: list, col_widths: list):
        """行を表示"""
        parts = []
        for i, width in enumerate(col_widths):
            if i < len(row):
                cell = str(row[i])
                if len(cell) > width:
                    cell = cell[:width-3] + "..."
                parts.append(f" {cell:<{width}} ")
            else:
                parts.append(" " * (width + 2))
        print("|" + "|".join(parts) + "|")
    
    @staticmethod
    def display_list(items: list, title: str = None):
        """リスト形式で表示"""
        if title:
            print(f"\n{title}")
            print("-" * len(title))
        
        if not items:
            print("（データなし）")
            return
        
        for i, item in enumerate(items, 1):
            print(f"{i:3d}. {item}")
    
    @staticmethod
    def display_dict(data: Dict[str, Any], indent: int = 0):
        """辞書形式で表示"""
        indent_str = "  " * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{indent_str}{key}:")
                TableDisplay.display_dict(value, indent + 1)
            elif isinstance(value, list):
                print(f"{indent_str}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        TableDisplay.display_dict(item, indent + 1)
                        print()
                    else:
                        print(f"{indent_str}  - {item}")
            else:
                print(f"{indent_str}{key}: {value}")