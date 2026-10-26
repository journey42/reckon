import os
import sys

import pytest

# Make the repo root importable so `import rhiz...` resolves in tests.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _mail_credentials(monkeypatch):
    """Tests never send real mail, but they still need a credential to read.

    ``_email_client()`` refuses to build a client without
    AZURE_COMMUNICATION_CONNECTION_STRING, and the tests that exercise the
    senders patch ``EmailClient`` rather than the environment. MAIL_DRY_RUN is
    cleared so a developer's shell setting cannot silently bypass those patches.
    """
    from rhiz.utils.comms import CONNECTION_STRING_ENV

    monkeypatch.setenv(
        CONNECTION_STRING_ENV,
        "endpoint=https://acs.invalid/;accesskey=test-key-not-a-secret",
    )
    monkeypatch.delenv("MAIL_DRY_RUN", raising=False)

