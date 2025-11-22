import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv(Path(__file__).parent / ".env.test", override=True)


@pytest.fixture(scope="session")
def test_env_vars():
    """Validate test environment safety."""
    required = ["TELEGRAM_BOT_TOKEN", "REDIS_URL", "AUTH_TOKEN", "SERVER_URL"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        pytest.skip(f"Missing: {missing}")
    
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not any(x in token.lower() for x in ["test", "dummy", "fake", "mock"]):
        pytest.exit("DANGER: Production token detected!")
    
    return {k: os.getenv(k) for k in required}


@pytest.fixture(autouse=True)
def reset_settings(tmp_path, monkeypatch):
    """Reset singleton + isolate config file."""
    from src.config.settings import Settings
    
    monkeypatch.chdir(tmp_path)
    fake_config = tmp_path / ".dynamic_config.json"
    
    original_exists, original_open = os.path.exists, open
    
    def patched_exists(p):
        return fake_config.exists() if Path(p).name == ".dynamic_config.json" else original_exists(p)
    
    def patched_open(f, mode='r', *a, **kw):
        p = Path(f)
        return original_open(fake_config if p.name == ".dynamic_config.json" else f, mode, *a, **kw)
    
    monkeypatch.setattr("os.path.exists", patched_exists)
    monkeypatch.setattr("builtins.open", patched_open)
    
    Settings._instance = None
    Settings._last_reload = None
    yield
    Settings._instance = None


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Config file helper with write/read/exists/unlink."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / ".dynamic_config.json"
    
    class ConfigPath:
        def __init__(self, p): self._path = p
        def write(self, data): self._path.write_text(json.dumps(data)); return self._path
        def exists(self): return self._path.exists()
        def unlink(self): return self._path.unlink()
        def read_text(self): return self._path.read_text()
    
    return ConfigPath(path)


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    """Global Redis mock."""
    redis = MagicMock()
    for method in ['ping', 'get', 'set', 'setex', 'delete', 'incr', 'expire', 
                   'scan', 'aclose', 'hset', 'hget', 'hgetall', 'hdel', 'keys', 'exists', 'flushdb']:
        setattr(redis, method, AsyncMock(return_value=None if method == 'get' else True))
    redis.scan.return_value = (0, [])
    redis.hgetall.return_value = {}
    redis.keys.return_value = []
    redis.exists.return_value = 0
    
    monkeypatch.setattr("redis.asyncio.Redis", lambda *a, **kw: redis)
    yield redis


@pytest.fixture
def app_settings(test_env_vars):
    """Fresh Settings instance."""
    from src.config.settings import Settings
    return Settings.from_env()
