from bh_hidro.cli import main


def test_help_exits_zero(capsys):
    assert main([]) == 0
    assert "bootstrap" in capsys.readouterr().out


def test_status_prints_without_db(capsys):
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "database:" in out
    assert "mysql:" in out


def test_download_dry_run(capsys):
    assert main(["download", "--dry-run", "--start-date", "20260820", "--end-date", "20260822"]) == 0
    out = capsys.readouterr().out
    assert "eraland:" in out
    assert "wrf:" in out


def test_imerg_dry_run(capsys):
    assert main(["imerg", "--dry-run", "--start-date", "20260820", "--end-date", "20260822"]) == 0
    out = capsys.readouterr().out
    assert "late:" in out
    assert "early:" in out
    assert "2026-08-20 dry-run" in out


def test_imerg_calib_dry_run(capsys):
    assert main(["imerg", "--calib", "--dry-run", "--start-date", "20260820", "--end-date", "20260822"]) == 0
    out = capsys.readouterr().out
    assert "calib:" in out
    assert "late:" not in out
    assert "2026-08-20 dry-run" in out


def test_balance_dry_run(capsys):
    assert main(["balance", "--dry-run", "--start-date", "20260820", "--end-date", "20260822"]) == 0
    out = capsys.readouterr().out
    assert "2026-08-20 dry-run" in out


def test_output_dry_run(capsys):
    assert main(["output", "--dry-run", "--start-date", "20260820", "--end-date", "20260822"]) == 0
    out = capsys.readouterr().out
    assert "2026-08-20 dry-run" in out
