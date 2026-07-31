"""
Pytest configuration shared by every test in this folder.

Pytest always loads conftest.py BEFORE it imports any test file. We use
that timing here: `app.config` checks required environment variables the
moment it's imported, and it would normally fail because we don't have
real Neon/Firebase/R2 accounts wired into `.env` yet. So before any test
file gets a chance to `import app`, we set safe, obviously-fake values
for those required keys.

Important: these values live only in memory for the life of this test
run. They are never written to any file, and they are never real
credentials - just placeholder text so the app's startup check passes
and we can test the parts of the app that don't need a real Neon/
Firebase/R2 connection yet.

os.environ.setdefault(...) only sets a value if one isn't already set,
so if you DO have real values in your shell environment, those win.
"""

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql://test:test@localhost/test?sslmode=require"
)
os.environ.setdefault("FIREBASE_SERVICE_ACCOUNT_JSON", '{"type": "service_account"}')
os.environ.setdefault("R2_ACCOUNT_ID", "test-account-id")
os.environ.setdefault("R2_ACCESS_KEY_ID", "test-access-key-id")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test-secret-access-key")
os.environ.setdefault("R2_BUCKET_NAME", "test-bucket")
os.environ.setdefault(
    "R2_ENDPOINT_URL", "https://test-account-id.r2.cloudflarestorage.com"
)
