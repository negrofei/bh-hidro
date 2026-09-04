from bh_hidro.cli import main


def test_help_exits_zero():
    assert main([]) == 0


def test_status_prints_without_db(capsys):
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "database:" in out
    assert "mysql:" in out


def test_untransferred_command_exits_two():
    assert main(["download"]) == 2
    assert main(["imerg"]) == 2
    assert main(["balance"]) == 2
    assert main(["output"]) == 2
    assert main(["run"]) == 2
