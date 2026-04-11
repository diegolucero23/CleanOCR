"""
tests/conftest.py

Sets up a dummy GOOGLE_API_KEY before any app module is collected by pytest.
This prevents config.py from calling sys.exit() in environments where a real
.env file is not present (CI, fresh clones, etc.).

In local development, if a .env file exists with a real key,
load_dotenv(override=True) in config.py will replace this dummy value after
module load — so real credentials are never displaced when present.
"""
import os

os.environ.setdefault("GOOGLE_API_KEY", "test-key-for-ci")
