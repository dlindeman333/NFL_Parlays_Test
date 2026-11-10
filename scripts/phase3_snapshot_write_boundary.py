"""Fail-closed boundary for legacy snapshot writer (not an activation mechanism)."""
import os
from urllib.parse import urlsplit

TEST_REPO = 'dlindeman333/NFL_Parlays_Test'
TEST_PROJECT = 'luxezjthznupdghmexyh'


def require_snapshot_write_authorization(env=None):
    """Block legacy writes until a separately reviewed provenance-backed writer exists."""
    env = os.environ if env is None else env
    repo = env.get('GITHUB_REPOSITORY', '')
    url = env.get('SUPABASE_URL', '')
    parsed = urlsplit(url)
    if repo != TEST_REPO or parsed.scheme != 'https' or parsed.hostname != f'{TEST_PROJECT}.supabase.co' or parsed.port not in (None, 443) or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise PermissionError('Snapshot writer rejected: TEST environment boundary mismatch')
    raise PermissionError('Legacy snapshot writer disabled: verified source publication provenance and immutable capture audit are not implemented')
