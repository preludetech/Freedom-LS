from freedom_ls.audit_log.config import config


def test_extra_actions_default_to_none():
    assert config.AUDIT_LOG_EXTRA_ACTIONS == {}
