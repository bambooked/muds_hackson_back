"""
Instance E 基本検証テスト

簡単なテストで統合テストの基本構造が動作することを確認します。
"""

import pytest
from unittest.mock import MagicMock, patch

def test_data_models_import():
    """データモデルのインポートテスト"""
    try:
        from agent.source.interfaces.data_models import (
            SearchRequest,
            SearchResultCollection,
            DocumentIngestionRequest,
            DocumentIngestionResult,
            SystemStatistics,
            HealthStatus,
            PaaSConfig,
            SearchMode
        )
        
        # 基本的なインスタンス作成
        search_request = SearchRequest(query="test")
        assert search_request.query == "test"
        assert search_request.mode == SearchMode.HYBRID
        
        print("✅ データモデルインポート成功")
        
    except ImportError as e:
        pytest.fail(f"データモデルインポート失敗: {e}")

def test_config_manager_import():
    """設定管理のインポートテスト"""
    try:
        from agent.source.interfaces.config_manager import PaaSConfigManager
        
        # 設定マネージャーの基本動作確認
        config_manager = PaaSConfigManager()
        assert config_manager is not None
        
        print("✅ 設定管理インポート成功")
        
    except ImportError as e:
        pytest.fail(f"設定管理インポート失敗: {e}")

def test_unified_interface_import():
    """UnifiedPaaSInterfaceのインポートテスト"""
    try:
        from agent.source.interfaces.unified_paas_impl import UnifiedPaaSImpl
        
        # インターフェースクラスの存在確認
        assert UnifiedPaaSImpl is not None
        
        print("✅ UnifiedPaaSInterfaceインポート成功")
        
    except ImportError as e:
        pytest.fail(f"UnifiedPaaSInterfaceインポート失敗: {e}")

@pytest.mark.asyncio
async def test_basic_unified_interface_creation():
    """UnifiedPaaSInterfaceの基本作成テスト"""
    try:
        from agent.source.interfaces.unified_paas_impl import UnifiedPaaSImpl
        from agent.source.interfaces.config_manager import PaaSConfigManager
        from agent.source.interfaces.data_models import PaaSConfig
        
        # 設定マネージャーモック
        config_manager = PaaSConfigManager()
        
        # 最小限の設定
        minimal_config = PaaSConfig(
            environment='test',
            enable_google_drive=False,
            enable_vector_search=False,
            enable_authentication=False,
            enable_monitoring=False
        )
        
        # UnifiedPaaSInterfaceの作成
        with patch('agent.source.interfaces.unified_paas_impl.get_config_manager', return_value=config_manager), \
             patch.object(config_manager, 'load_config', return_value=minimal_config):
            unified_interface = UnifiedPaaSImpl(auto_initialize=False)
            assert unified_interface is not None
        
        print("✅ UnifiedPaaSInterface基本作成成功")
        
    except Exception as e:
        pytest.fail(f"UnifiedPaaSInterface作成失敗: {e}")

def test_instance_e_test_preparation():
    """Instance E テスト準備確認"""
    
    # 必須ファイルの存在確認
    test_files = [
        'agent/tests/test_instance_e_unified_integration.py',
        'agent/tests/test_instance_e_ports_integration.py', 
        'agent/tests/test_instance_e_end_to_end.py',
        'agent/tests/test_instance_e_fallback_and_config.py'
    ]
    
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent
    
    for test_file in test_files:
        file_path = project_root / test_file
        assert file_path.exists(), f"テストファイルが見つかりません: {test_file}"
    
    print("✅ Instance E テストファイル準備確認成功")


if __name__ == "__main__":
    import subprocess
    import sys
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            __file__, 
            '-v',
            '-s'
        ], capture_output=False)
        
        if result.returncode == 0:
            print("\n🎉 Instance E 基本検証テスト成功!")
            print("📋 統合テストの実行準備が整いました")
        else:
            print("\n⚠️ Instance E 基本検証テストで問題が発見されました")
            
    except Exception as e:
        print(f"\n💥 テスト実行エラー: {e}")