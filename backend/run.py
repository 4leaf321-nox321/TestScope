"""개발 서버 기동.

**운영과 포트를 가른다**(8020 운영 / 8021 개발). 같은 포트를 쓰면 개발 백엔드를
내린 순간 프론트 프록시가 운영 설치본에 그대로 붙고, 화면은 그 사실을 아무 데도
말하지 않는다 — 서버가 죽은 것도 코드가 틀린 것도 아니어서 볼 곳이 없다.

**이미 누가 그 포트에 있으면 안 뜬다.** Windows 는 두 프로세스가 같은 포트를
LISTEN 하는 것을 막지 않는다. reload 로 띄운 서버를 부모만 죽이면 자식 워커가
소켓을 물고 남고, 그다음에 띄운 새 서버와 **옛 워커가 번갈아 응답한다** — 새로
만든 API 가 404 로 오는데 코드에는 분명히 있는 상태가 된다. 그 원인은 코드
어디에도 없어서, 겪으면 반나절이 간다.

**고아 워커는 스스로 치운다.** 포트를 쥔 PID 가 이미 죽은 프로세스면(부모만 죽은 것)
그 PID 를 부모로 둔 워커는 아무도 안 거두는 고아다 — 그것만 내리고 뜬다. 살아 있는
프로세스가 쥐고 있으면 전처럼 거절한다: 그건 남의 서버일 수 있다. 하루에 두 번 겪고
나서 넣었다(2026-09-19).
"""

from __future__ import annotations

import re
import socket
import subprocess
import sys
import time

import uvicorn

from app.config import get_settings


def _answering(host: str, port: int) -> bool:
    """그 포트에 이미 응답하는 것이 있나.

    바인딩을 시도해 보는 것으로는 못 잡는다 — Windows 에서는 그 바인딩이 성공한다.
    실제로 붙어 본다.
    """
    target = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex((target, port)) == 0


def _listener_pid(port: int) -> int | None:
    """그 포트를 LISTEN 으로 쥔 PID(netstat 기준). Windows 에서만 뜻이 있다."""
    if sys.platform != "win32":
        return None
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return None
    for line in out.splitlines():
        if "LISTENING" in line and re.search(rf":{port}\s", line):
            return int(line.split()[-1])
    return None


def _alive(pid: int) -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return str(pid) in out


def _reap_orphans(port: int) -> bool:
    """죽은 부모의 reload 워커가 포트를 물고 있으면 내리고 True.

    netstat 이 말하는 소유 PID 가 이미 없는 프로세스면, 그 PID 를 부모로 둔
    `multiprocessing.spawn` 워커가 소켓을 물려받아 살아 있는 것이다. 그것은 아무도 안
    거두는 고아라 내려도 된다. 소유 PID 가 살아 있으면 남의 서버일 수 있으니 손대지 않는다.
    """
    owner = _listener_pid(port)
    if owner is None or _alive(owner):
        return False
    found = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*parent_pid={owner},*' }} | "
            "ForEach-Object { $_.ProcessId }",
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()
    for pid in found:
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, check=False)
        # flush — 파일로 돌려 둔 stdout 은 버퍼에 남아, 서버가 도는 동안 이 줄이 안 보인다.
        print(
            f"죽은 부모({owner})의 워커 {pid} 가 {port} 포트를 물고 있어 내렸습니다.",
            flush=True,
        )
    # 소켓이 놓이는 데 한 박자 걸린다.
    for _ in range(20):
        if not _answering("127.0.0.1", port):
            return True
        time.sleep(0.25)
    return False


if __name__ == "__main__":
    settings = get_settings()
    development = settings.app_env == "development"
    port = settings.port + 1 if development else settings.port

    if _answering(settings.host, port) and not _reap_orphans(port):
        raise SystemExit(
            f"{port} 포트에 이미 응답하는 서버가 있습니다. 그대로 띄우면 둘이 번갈아\n"
            f"답해서, 새로 만든 API 가 404 로 오는데 코드에는 있는 상태가 됩니다.\n"
            f"\n"
            f"  Get-NetTCPConnection -LocalPort {port} -State Listen |\n"
            f"    Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique\n"
            f"\n"
            f"으로 잡고 있는 프로세스를 찾아 내린 뒤 다시 돌리세요. 죽은 PID 가\n"
            f"나오면 그 PID 를 부모로 둔 워커가 소켓을 물고 있는 것입니다."
        )

    uvicorn.run("app.main:app", host=settings.host, port=port, reload=development)
