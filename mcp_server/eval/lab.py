r"""실험실 — **진짜 AI 에게 물음 28개를 던지고 자취를 잰다.** API 키 없이, 이 PC 의 claude 로.

    ..\.venv\Scripts\python.exe eval\lab.py            # 전부
    ..\.venv\Scripts\python.exe eval\lab.py --only q01 q08
    ..\.venv\Scripts\python.exe eval\lab.py --baseline # 끝나고 기준선으로 굳힌다

무엇을 하나 — 순서대로:

1. 개발 DB 를 **복사**해 `testscope_eval` 을 만든다(pg_dump | psql). 측정 대상 AI 가 시험을
   등록하고 값을 만들기도 하므로 개발 DB 에 대고 돌리면 안 된다. 끝나면 지운다.
2. 그 DB 로 백엔드를 8023 에, MCP 서버를 8024 에 띄운다(자취 켜고, 세션 id 를 박아서).
3. 확인용 토큰을 만들어 MCP 설정(JSON)에 넣는다 — `claude` 가 그 헤더로 서버를 부른다.
4. 물음마다 자취에 표식을 적고 `claude -p "<물음>"` 을 **새 세션**으로 띄운다. 내장 도구는
   전부 끄고(`--tools ""`) MCP 도구만 준다 — 파일·셸을 건드릴 길이 없다. 앞 물음을 기억하지
   못하게 매번 새 세션이다: 한 대화에서 이어 물으면 도구를 덜 부르고, 그것은 실제와 다르다.
5. 답과 자취를 `runs/<시각>/` 에 남기고 `score.py` 로 채점한다.

측정 대상은 **이 PC 의 claude 기본 모델**이다(`--model` 로 바꿀 수 있다). 결과 파일에 모델을
적는다 — 모델이 다르면 점수를 견줄 수 없다.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

HERE = Path(__file__).parent
MCP_DIR = HERE.parent
REPO = MCP_DIR.parent
BACKEND = REPO / "backend"
BACKEND_PY = BACKEND / ".venv" / "Scripts" / "python.exe"
MCP_PY = MCP_DIR / ".venv" / "Scripts" / "python.exe"
PG_BIN = Path(r"C:\Program Files\PostgreSQL\17\bin")

EVAL_DB = "testscope_eval"
BACKEND_PORT = 8023
MCP_PORT = 8024
#: 물음 하나에 주는 시간. 넘으면 그 물음은 「호출 없음」 으로 남고 다음으로 간다.
QUESTION_TIMEOUT = 300

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(errors="replace")


def _database_url() -> str:
    for line in (BACKEND / ".env").read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("backend/.env 에 DATABASE_URL 이 없습니다.")


def _pg_env(url: str) -> tuple[dict[str, str], str]:
    """pg_dump·psql 이 읽는 환경변수와 원본 DB 이름."""
    parts = urlsplit(url.replace("postgresql+psycopg://", "postgresql://"))
    env = dict(os.environ)
    env.update(
        {
            "PGHOST": parts.hostname or "localhost",
            "PGPORT": str(parts.port or 5432),
            "PGUSER": parts.username or "postgres",
            "PGPASSWORD": parts.password or "",
        }
    )
    return env, parts.path.lstrip("/")


def _run(args: list[str], env: dict[str, str], **kw: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        **kw,
    )


def _copy_database(url: str) -> str:
    """개발 DB 를 testscope_eval 로 복사한다 — 붙어 있는 연결이 있어도 된다(dump | restore)."""
    env, source = _pg_env(url)
    _run([str(PG_BIN / "dropdb"), "--if-exists", EVAL_DB], env)
    made = _run([str(PG_BIN / "createdb"), EVAL_DB], env)
    if made.returncode != 0:
        raise SystemExit(f"DB 를 못 만들었습니다: {made.stderr.strip()}")
    dump = subprocess.Popen(
        [str(PG_BIN / "pg_dump"), "--no-owner", "--no-acl", source],
        env=env,
        stdout=subprocess.PIPE,
    )
    restore = subprocess.run(
        [str(PG_BIN / "psql"), "-q", "-v", "ON_ERROR_STOP=0", EVAL_DB],
        env=env,
        stdin=dump.stdout,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    dump.wait()
    if dump.returncode != 0:
        raise SystemExit("pg_dump 가 실패했습니다.")
    print(
        f"DB 복사: {source} -> {EVAL_DB}" + (" (경고 있음)" if restore.stderr.strip() else "")
    )
    return url.rsplit("/", 1)[0] + "/" + EVAL_DB


def _drop_database(url: str) -> None:
    env, _ = _pg_env(url)
    _run([str(PG_BIN / "dropdb"), "--if-exists", "--force", EVAL_DB], env)


def _wait_port(port: int, seconds: float) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        with socket.socket() as probe:
            probe.settimeout(0.3)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


def _wait_health(port: int, seconds: float) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=2
            ) as got:
                if got.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


def _stop(proc: subprocess.Popen[Any] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    # 자식까지 — uvicorn 이 reload 없이 떠도 taskkill /T 가 안전하다.
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False
    )


def _ask(
    question: dict[str, Any], mcp_config: Path, model: str | None, workdir: Path
) -> dict[str, Any]:
    """물음 하나 — 새 claude 세션. 내장 도구는 전부 끄고 MCP 도구만."""
    args = [
        "claude",
        "-p",
        question["text"],
        "--mcp-config",
        str(mcp_config),
        "--strict-mcp-config",
        "--tools",
        "",
        "--permission-mode",
        "bypassPermissions",
        "--no-session-persistence",
        "--output-format",
        "json",
        "--setting-sources",
        "",
    ]
    if model:
        args += ["--model", model]
    started = time.perf_counter()
    try:
        got = subprocess.run(
            args,
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=QUESTION_TIMEOUT,
            check=False,
            shell=True,
        )
    except subprocess.TimeoutExpired:
        return {
            "id": question["id"],
            "answer": None,
            "error": "시간 초과",
            "seconds": QUESTION_TIMEOUT,
        }
    seconds = round(time.perf_counter() - started, 1)
    if got.returncode != 0:
        return {
            "id": question["id"],
            "answer": None,
            "error": (got.stderr or got.stdout).strip()[-400:],
            "seconds": seconds,
        }
    try:
        body = json.loads(got.stdout)
    except json.JSONDecodeError:
        return {"id": question["id"], "answer": got.stdout.strip()[-1200:], "seconds": seconds}
    return {
        "id": question["id"],
        "answer": body.get("result"),
        "turns": body.get("num_turns"),
        "cost_usd": body.get("total_cost_usd"),
        # 어느 모델이 얼마나 — 보조 모델(요약 등)이 섞이므로 전부 적는다.
        "models": sorted((body.get("modelUsage") or {}).keys()),
        "seconds": seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP 자취 실험실")
    parser.add_argument("--only", nargs="*", default=None, help="물음 id 몇 개만")
    parser.add_argument("--model", default=None)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument(
        "--keep-db", action="store_true", help="끝나도 testscope_eval 을 남긴다"
    )
    args = parser.parse_args()

    if shutil.which("claude") is None:
        raise SystemExit("claude CLI 가 없습니다 — 이 PC 의 Claude Code 로 돌립니다.")
    for path in (BACKEND_PY, MCP_PY, PG_BIN / "pg_dump.exe"):
        if not path.exists():
            raise SystemExit(f"없습니다: {path}")

    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))["questions"]
    if args.only:
        questions = [one for one in questions if one["id"] in set(args.only)]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    run_dir = HERE / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    trace = run_dir / "calls.jsonl"
    print(f"실험 {stamp} — 물음 {len(questions)}개 · 기록 {run_dir}")

    dev_url = _database_url()
    eval_url = _copy_database(dev_url)
    backend: subprocess.Popen[Any] | None = None
    mcp: subprocess.Popen[Any] | None = None
    try:
        env = dict(
            os.environ, DATABASE_URL=eval_url, APP_ENV="development", PYTHONIOENCODING="utf-8"
        )
        backend = subprocess.Popen(
            [
                str(BACKEND_PY),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(BACKEND_PORT),
            ],
            cwd=BACKEND,
            env=env,
            stdout=(run_dir / "backend.log").open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )
        if not _wait_health(BACKEND_PORT, 90):
            raise SystemExit("백엔드가 90초 안에 안 떴습니다 — runs/…/backend.log")
        token = (
            _run([str(BACKEND_PY), "scripts/mcp_probe_account.py", "mint"], env, cwd=BACKEND)
            .stdout.strip()
            .splitlines()[-1]
        )
        print(f"백엔드 {BACKEND_PORT} · 토큰 준비")

        mcp_env = dict(
            os.environ,
            TESTSCOPE_API_BASE=f"http://127.0.0.1:{BACKEND_PORT}/api",
            TESTSCOPE_MCP_TRACE=str(trace),
            TESTSCOPE_MCP_SESSION=stamp,
            PYTHONIOENCODING="utf-8",
        )
        mcp = subprocess.Popen(
            [
                str(MCP_PY),
                "-c",
                "import server; server.mcp.run(transport='streamable-http',"
                f" host='127.0.0.1', port={MCP_PORT})",
            ],
            cwd=MCP_DIR,
            env=mcp_env,
            stdout=(run_dir / "mcp.log").open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )
        if not _wait_port(MCP_PORT, 60):
            raise SystemExit("MCP 서버가 60초 안에 안 떴습니다 — runs/…/mcp.log")
        print(f"MCP {MCP_PORT} · 자취 켜짐")

        config = run_dir / "mcp.json"
        config.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "testscope": {
                            "type": "http",
                            "url": f"http://127.0.0.1:{MCP_PORT}/mcp",
                            "headers": {"Authorization": f"Bearer {token}"},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        workdir = run_dir / "cwd"
        workdir.mkdir(exist_ok=True)

        answers: list[dict[str, Any]] = []
        for index, question in enumerate(questions, 1):
            with trace.open("a", encoding="utf-8") as out:
                out.write(
                    json.dumps(
                        {
                            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
                            "session": stamp,
                            "event": "question",
                            "id": question["id"],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            print(
                f"  [{index}/{len(questions)}] {question['id']} {question['text'][:40]}",
                end="",
                flush=True,
            )
            got = _ask(question, config, args.model, workdir)
            answers.append(got)
            print(
                f"  -> {got.get('seconds')}초"
                + (
                    f" · {got['error'][:60]}"
                    if got.get("error")
                    else f" · 턴 {got.get('turns')}"
                )
            )
            (run_dir / "answers.json").write_text(
                json.dumps(answers, ensure_ascii=False, indent=1), encoding="utf-8"
            )
    finally:
        _stop(mcp)
        _stop(backend)
        if not args.keep_db:
            _drop_database(dev_url)
        # 토큰이 든 설정 파일은 남기지 않는다.
        (run_dir / "mcp.json").unlink(missing_ok=True)

    # 채점 — score.py 를 그대로 부른다.
    models = sorted({name for one in answers for name in one.get("models", [])})
    scored = subprocess.run(
        [
            str(MCP_PY),
            str(HERE / "score.py"),
            "--log",
            str(trace),
            "--session",
            stamp,
            "--baseline" if args.baseline else "--save",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    print("\n" + scored.stdout.strip())
    (run_dir / "score.txt").write_text(scored.stdout, encoding="utf-8")
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "stamp": stamp,
                "models": models or [args.model],
                "questions": len(questions),
                "cost_usd": round(sum(one.get("cost_usd") or 0 for one in answers), 4),
                "seconds": round(sum(one.get("seconds") or 0 for one in answers), 1),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return scored.returncode


if __name__ == "__main__":
    sys.exit(main())
