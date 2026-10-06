from pathlib import Path

from bh_hidro.log import setup_logging, setup_process_logging


def test_setup_logging_writes_step_file(tmp_path: Path):
    logger = setup_logging(tmp_path, logbasename="descarga", level="info")
    files = list(tmp_path.glob("descarga_*.log"))
    assert len(files) == 1
    logger.info("hello-download")
    for handler in logger.handlers:
        handler.flush()
    assert "hello-download" in files[0].read_text()
    assert "logging to" in files[0].read_text()


def test_setup_process_logging_writes_worker_file(tmp_path: Path):
    logger = setup_process_logging(tmp_path, "debug", "balance_cult1_prov22")
    files = list(tmp_path.glob("process_balance_cult1_prov22_*.log"))
    assert len(files) == 1
    logger.info("worker-hello")
    for handler in logger.handlers:
        handler.flush()
    root = __import__("logging").getLogger()
    for handler in root.handlers:
        handler.flush()
    assert "worker-hello" in files[0].read_text() or "process logging to" in files[0].read_text()
