import sys
from pathlib import Path

import pytest

import run_local
import web_security


@pytest.mark.parametrize(
    ("allow_protected", "expected_levels"),
    [
        (False, web_security.PUBLIC_LEVELS),
        (True, web_security.ALL_LEVELS),
    ],
)
def test_local_launcher_imports_casefile_and_binds_loopback(
    tmp_path, monkeypatch, capsys, allow_protected, expected_levels
):
    casefile = tmp_path / "casefile.json"
    casefile.write_text("{}", encoding="utf-8")
    database = tmp_path / "nested" / "case.sqlite"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_local.py",
            "--casefile",
            str(casefile),
            "--database",
            str(database),
            *(["--allow-protected"] if allow_protected else []),
        ],
    )
    monkeypatch.setattr(run_local, "available_port", lambda _port: 8123)
    imports = []
    monkeypatch.setattr(
        run_local, "import_case", lambda db, source: imports.append((db, source))
    )
    monkeypatch.setattr(
        run_local.SignalLedgerHandler, "visible_levels", web_security.PUBLIC_LEVELS
    )

    class FakeServer:
        def __init__(self, address, handler):
            self.address = address
            self.handler = handler

        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    servers = []

    def create_server(address, handler):
        instance = FakeServer(address, handler)
        servers.append(instance)
        return instance

    monkeypatch.setattr(run_local, "ThreadingHTTPServer", create_server)

    assert run_local.main() == 0
    assert imports == [(database, casefile)]
    assert servers[0].address == ("127.0.0.1", 8123)
    assert run_local.SignalLedgerHandler.visible_levels is expected_levels
    assert run_local.SignalLedgerHandler.port == 8123
    assert servers[0].handler.keywords["directory"] == str(run_local.PROJECT_ROOT)
    assert "127.0.0.1:8123" in capsys.readouterr().out


def test_local_launcher_reports_missing_casefile(tmp_path, monkeypatch):
    missing_casefile = tmp_path / "missing.json"
    monkeypatch.setattr(
        sys, "argv", ["run_local.py", "--casefile", str(missing_casefile)]
    )

    with pytest.raises(SystemExit) as error:
        run_local.main()

    assert error.value.code == 2
