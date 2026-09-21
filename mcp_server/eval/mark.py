r"""물음의 경계를 자취에 적는다 — 사람이 손으로 물을 때.

    .\.venv\Scripts\python.exe eval\mark.py q07     # 이제부터의 호출은 q07 의 것

실행기(run.py)는 스스로 적으므로 이것이 필요 없다. Claude 같은 클라이언트에 MCP 를 붙여
직접 물을 때, 물음 하나 던지기 **전에** 이것을 돌리면 채점기가 자취를 물음별로 정확히
자른다. 안 적으면 시간 간격으로 자르는데, 그건 덜 정확하다.

서버와 같은 `TESTSCOPE_MCP_TRACE`·`TESTSCOPE_MCP_SESSION` 을 봐야 같은 파일·같은 세션에
적힌다 — 서버를 `run_mcp.ps1 -Trace` 로 띄웠으면 이것도 같은 창에서 돌린다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import calltrace


def main() -> int:
    if len(sys.argv) < 2:
        print("물음 id 를 주세요: eval\\mark.py q07")
        return 1
    if calltrace.trace_path() is None:
        print("자취가 꺼져 있습니다 — TESTSCOPE_MCP_TRACE=1 로 띄우고 같은 창에서 돌리세요")
        return 1
    calltrace.mark("question", id=sys.argv[1])
    print(f"표식: {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
