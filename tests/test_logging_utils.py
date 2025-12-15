from spotify2tidal.logging_utils import LogLevel, SyncLogger


def test_sync_logger_quiet_filters_non_errors(capsys):
    logger = SyncLogger(mode="cli", quiet=True, use_color=False)
    logger.info("hello")
    logger.error("boom")

    out = capsys.readouterr().out
    assert "hello" not in out
    assert "boom" in out


def test_sync_logger_verbose_includes_debug(capsys):
    logger = SyncLogger(mode="cli", verbose=True, use_color=False)
    logger.debug("dbg")

    out = capsys.readouterr().out
    assert "dbg" in out


def test_sync_logger_web_mode_stores_entries():
    session_state = {}
    logger = SyncLogger(mode="web", session_state=session_state)

    logger.success("done")
    entries = logger.get_web_entries()

    assert "sync_logs" in session_state
    assert len(entries) == 1
    assert entries[0].level == LogLevel.SUCCESS
    assert "done" in entries[0].message


def test_format_summary_counts():
    logger = SyncLogger(mode="cli", use_color=False)
    logger.success("a")
    logger.warning("b")
    logger.error("c")

    summary = logger.format_summary()
    assert "completed" in summary
    assert "warnings" in summary
    assert "errors" in summary
