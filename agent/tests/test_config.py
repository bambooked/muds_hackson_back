import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import tools.config as config


class TestConfig:
    """設定のテスト"""
    
    def test_default_values(self):
        """デフォルト値のテスト"""
        assert config.GEMINI_MODEL == "gemini-1.5-pro"
        assert config.LOG_LEVEL == "INFO"
        assert config.MAX_FILE_SIZE_MB == 100
        assert config.MAX_FILE_SIZE_BYTES == 100 * 1024 * 1024
    
    def test_supported_extensions(self):
        """サポートされている拡張子のテスト"""
        expected_extensions = [".pdf", ".csv", ".json", ".jsonl"]
        assert config.SUPPORTED_EXTENSIONS == expected_extensions
    
    def test_category_mapping(self):
        """カテゴリーマッピングのテスト"""
        assert "paper" in config.CATEGORY_MAPPING
        assert "poster" in config.CATEGORY_MAPPING
        assert "datasets" in config.CATEGORY_MAPPING
        
        assert config.CATEGORY_MAPPING["paper"] == "論文"
        assert config.CATEGORY_MAPPING["poster"] == "ポスター"
        assert config.CATEGORY_MAPPING["datasets"] == "データセット"
    
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"})
    def test_validate_config_success(self):
        """設定検証成功のテスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(config, 'DATA_DIR', Path(temp_dir)):
                # データディレクトリを作成
                Path(temp_dir).mkdir(exist_ok=True)
                
                # 検証が成功することを確認
                config.validate_config()
    
    def test_validate_config_missing_api_key(self):
        """API キー不足時の設定検証テスト"""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(config, 'GEMINI_API_KEY', None):
                with pytest.raises(ValueError, match="設定エラーがあります"):
                    config.validate_config()
    
    def test_validate_config_missing_data_dir(self):
        """データディレクトリ不足時の設定検証テスト"""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            with patch.object(config, 'DATA_DIR', Path("/nonexistent/path")):
                with pytest.raises(ValueError, match="設定エラーがあります"):
                    config.validate_config()
    
    @patch.dict(os.environ, {
        "GEMINI_MODEL": "gemini-1.5-flash",
        "LOG_LEVEL": "DEBUG",
        "MAX_FILE_SIZE_MB": "50"
    })
    def test_environment_variable_override(self):
        """環境変数による設定上書きのテスト"""
        # モジュールを再読み込みして環境変数を反映
        import importlib
        importlib.reload(config)
        
        assert config.GEMINI_MODEL == "gemini-1.5-flash"
        assert config.LOG_LEVEL == "DEBUG"
        assert config.MAX_FILE_SIZE_MB == 50