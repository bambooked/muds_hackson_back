import pytest
import tempfile
import shutil
from pathlib import Path
import json

from agent.source.indexer.scanner import FileScanner
from agent.source.indexer.indexer import FileIndexer


class TestFileScanner:
    """ファイルスキャナーのテスト"""
    
    def setup_method(self):
        """テスト前の設定"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.scanner = FileScanner(self.temp_dir)
        
        # テスト用ファイルを作成
        self._create_test_files()
    
    def teardown_method(self):
        """テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir)
    
    def _create_test_files(self):
        """テスト用ファイルを作成"""
        # PDFファイル（ダミー）
        (self.temp_dir / "paper").mkdir(exist_ok=True)
        (self.temp_dir / "paper" / "test_paper.pdf").write_text("dummy pdf content")
        
        # CSVファイル
        (self.temp_dir / "datasets").mkdir(exist_ok=True)
        csv_content = "id,name,value\n1,test,100\n2,sample,200"
        (self.temp_dir / "datasets" / "test_data.csv").write_text(csv_content)
        
        # JSONファイル
        json_content = {"data": [{"id": 1, "name": "test"}]}
        (self.temp_dir / "datasets" / "test_data.json").write_text(
            json.dumps(json_content)
        )
        
        # サポートされていない拡張子のファイル
        (self.temp_dir / "test.txt").write_text("text file")
        
        # 隠しファイル
        (self.temp_dir / ".hidden").write_text("hidden file")
    
    def test_scan_directory(self):
        """ディレクトリスキャンのテスト"""
        files = self.scanner.scan_directory()
        
        # サポートされているファイルのみが検出されることを確認
        file_names = [f.file_name for f in files]
        
        assert "test_paper.pdf" in file_names
        assert "test_data.csv" in file_names
        assert "test_data.json" in file_names
        assert "test.txt" not in file_names  # サポート外
        assert ".hidden" not in file_names  # 隠しファイル
    
    def test_determine_category(self):
        """カテゴリー判定のテスト"""
        files = self.scanner.scan_directory()
        
        pdf_file = next(f for f in files if f.file_name == "test_paper.pdf")
        csv_file = next(f for f in files if f.file_name == "test_data.csv")
        
        assert pdf_file.category == "paper"
        assert csv_file.category == "datasets"
    
    def test_should_process_file(self):
        """ファイル処理判定のテスト"""
        # サポートされているファイル
        pdf_path = self.temp_dir / "test.pdf"
        pdf_path.write_text("dummy")
        assert self.scanner._should_process_file(pdf_path)
        
        # サポートされていないファイル
        txt_path = self.temp_dir / "test.txt"
        txt_path.write_text("dummy")
        assert not self.scanner._should_process_file(txt_path)
        
        # 隠しファイル
        hidden_path = self.temp_dir / ".hidden"
        hidden_path.write_text("dummy")
        assert not self.scanner._should_process_file(hidden_path)
    
    def test_calculate_file_hash(self):
        """ファイルハッシュ計算のテスト"""
        test_file = self.temp_dir / "test.pdf"
        test_file.write_text("test content")
        
        hash1 = self.scanner._calculate_file_hash(test_file)
        hash2 = self.scanner._calculate_file_hash(test_file)
        
        # 同じファイルは同じハッシュ
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256は64文字
        
        # 内容が変わるとハッシュも変わる
        test_file.write_text("different content")
        hash3 = self.scanner._calculate_file_hash(test_file)
        assert hash1 != hash3