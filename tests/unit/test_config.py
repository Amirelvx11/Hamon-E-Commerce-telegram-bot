import os
from src.config.settings import Settings
from src.config.enums import WorkflowSteps, ComplaintType, DeviceStatus, UserState


def test_env_load_and_values(app_settings, test_env_vars):
    """Test environment variable loading"""
    assert app_settings.telegram_token == test_env_vars["TELEGRAM_BOT_TOKEN"]
    assert app_settings.redis_url == test_env_vars["REDIS_URL"]
    assert app_settings.auth_token == test_env_vars["AUTH_TOKEN"]


def test_singleton_behavior():
    """Test singleton returns same instance without force_reload"""
    s1 = Settings.get_instance()
    s2 = Settings.get_instance()
    assert s1 is s2


def test_force_reload_creates_new_instance():
    """Test force_reload creates fresh instance"""
    s1 = Settings.get_instance()
    s2 = Settings.get_instance(force_reload=True)
    assert s1 is not s2
    
    # Verify new instance is now the singleton
    s3 = Settings.get_instance()
    assert s3 is s2


def test_dynamic_config_update(app_settings, mock_dynamic_config_file):
    """Test runtime configuration updates"""
    updates = {
        "maintenance_mode": True,
        "cache_ttl_seconds": 200,
        "session_timeout_minutes": 120
    }
    
    app_settings.update_from_dict(updates, persist=True)
    
    assert app_settings.maintenance_mode is True
    assert app_settings.cache_ttl_seconds == 200
    assert app_settings.session_timeout_minutes == 120
    assert mock_dynamic_config_file.exists()


def test_dynamic_config_type_coercion(app_settings):
    """Test automatic type conversion for config values"""
    updates = {
        "maintenance_mode": "true",  # string -> bool
        "cache_ttl_seconds": "500",  # string -> int
    }
    
    app_settings.update_from_dict(updates, persist=False)
    
    assert app_settings.maintenance_mode is True
    assert app_settings.cache_ttl_seconds == 500


def test_get_endpoint(app_settings):
    """Test endpoint URL retrieval"""
    base_url = app_settings.get_endpoint("base")
    assert base_url is not None
    assert base_url == os.getenv("SERVER_URL")


def test_workflow_step_info():
    """Test workflow step metadata"""
    info = WorkflowSteps.get_step_info(3)
    assert "display" in info
    assert info["display"].startswith("🔧")


def test_complaint_type_mapping():
    """Test complaint type ID to code mapping"""
    c = ComplaintType.from_id(1)
    assert c.code == "device_issue"
    
    mapping = ComplaintType.map_to_server(1)
    assert "subject_guid" in mapping


def test_device_status_display():
    """Test device status display formatting"""
    assert "ثبت" in DeviceStatus(0).display_name
    assert "🔧" in DeviceStatus.get_display(3)
    assert "❓" in DeviceStatus.get_display(999)


def test_user_state_helpers():
    """Test user state classification methods"""
    waiting_state = UserState.WAITING_NATIONAL_ID
    assert waiting_state.is_waiting() is True
    assert waiting_state.is_authenticated() is False
    
    auth_state = UserState.AUTHENTICATED
    assert auth_state.is_authenticated() is True
