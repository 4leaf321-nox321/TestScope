"""감사 기록을 남기는 **한 곳.**

오류 규약이 "오류 본문을 라우트에서 직접 만들지 않는다" 라고 정한 것과 같은
이유로 감사도 한 곳을 거친다. 라우트마다 손으로 만들면 어떤 곳은 사유를 빼먹고
어떤 곳은 대상 이름을 안 박고, 나중에 그 차이를 메울 방법이 없다.

## 무엇을 남기나

**되돌릴 수 없거나 권한이 실린 것**만이다. 값 하나 고친 것까지 남기면 그 안에서
정작 찾을 것을 못 찾는다.

## 커밋은 부르는 쪽이 한다

여기서 commit 하지 않는다. 감사 기록은 **그 변경과 같은 트랜잭션**에 있어야
한다 — 변경은 됐는데 기록이 없거나, 기록은 있는데 변경이 롤백되는 상태를 안
만든다.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from app.modules.audit.models import AuditEntry
from app.shared.request_context import get_actor_client, get_actor_token, get_request_id

#: 남기는 일. **과거형으로 적는다** — 일어난 일의 기록이지 명령이 아니다.
#:
#: 새 항목을 더할 때는 "이걸 반년 뒤에 누가 찾을까" 를 먼저 묻는다. 답이 없으면
#: 안 넣는 편이 낫다.
ACCOUNT_DECIDED = "account.decided"
ACCOUNT_SUSPENDED = "account.suspended"
ACCOUNT_ADMIN_CHANGED = "account.admin_changed"
ACCOUNT_HOME_CHANGED = "account.home_changed"
ACCOUNT_DELETED = "account.deleted"
LOGIN_THROTTLED = "auth.login_throttled"
"""같은 계정의 실패가 문턱을 넘어 응답을 늦추기 시작했다. 실패마다 남기면 넘치므로
문턱을 넘는 순간 한 번만."""
WORKSPACE_MERGED = "workspace.merged"
WORKSPACE_DELETED = "workspace.deleted"
VOCABULARY_RENAMED = "vocabulary.renamed"
VOCABULARY_MERGED = "vocabulary.merged"
VOCABULARY_REFERENCE_CHANGED = "vocabulary.reference_changed"
"""기준정보 화면에서 값의 쓰임 한 줄을 떼거나 옮겼다 — 계열의 시험 항목, 장비의 거점 같은
**도메인 행**이 바뀐 것이라 그 장비·계열 화면에서는 이유가 안 보인다. 여기 남는다."""
CONDITION_KEY_CHANGED = "condition_key.changed"
"""조건 정의가 바뀌면 **이미 적힌 시험 항목의 뜻이 바뀐다** — 단위를 kN 에서 N 으로
고치는 순간 저장된 숫자 전부가 다른 값이 된다. 되돌릴 수 없는 부류다."""
SPEC_DEFINITION_CHANGED = "spec_definition.changed"
"""사양 정의가 바뀌면 **이미 적힌 값의 뜻이 바뀐다.** 조건 정의와 같은 이유다.
검색축 연결(condition_key_id)도 여기 남는다 — 그것을 끊으면 그 사양으로 채운
모델들이 조용히 검색에서 빠지고, 그때 물을 자리가 여기밖에 없다."""
CATALOG_CREATED = "catalog.created"
"""계열·기종이 새로 생겼다. **전사 공용 데이터**라 누가 만들었는지가 남아야 한다.

특히 통로(actor_client)가 여기서 값을 갖는다 — 사람이 만든 계열과 AI 가 만든 계열은
나중에 다르게 다뤄야 할 수 있고, 그때 구별할 방법이 이것뿐이다."""
EQUIPMENT_IMPORTED = "equipment.imported"
"""**대장 반입 한 번.** 한 대씩이 아니라 한 번에 한 줄이다.

300대를 넣거나 30대를 갱신했는데 흔적이 없으면 「이 위치 누가 바꿨어」 에 답을 못 한다.
그렇다고 대마다 한 줄씩 남기면 반입 한 번에 감사 300줄이 생겨 정작 찾을 것을 가린다.
한 줄에 새로 넣은 자산번호·갱신한 자산번호와 그 전후를 담는다."""
EQUIPMENT_RETIRED = "equipment.retired"
EQUIPMENT_DELETED = "equipment.deleted"
METHOD_SUPERSEDED = "method.superseded"
METHOD_MERGED = "method.merged"
"""표기만 다른 규격 둘을 하나로 — 인용·요구 조건·장비 시험 항목이 남는 쪽으로 옮겨 가고 원래
줄은 지워진다. 어느 줄이 어디로 갔는지가 남아야 「내가 걸어 둔 규격이 사라졌다」 에 답한다."""
PROPERTY_LINKS_REVIEWED = "property_link.reviewed"
REVIEW_DECIDED = "review.decided"
REVIEW_REOPENED = "review.reopened"
"""정한 것을 다시 열었다 — 전의 결정과 누가 했는지를 담아, 두 결정이 모두 남게."""
"""검토함에서 하나를 정했다 — 어느 물음의 무엇을 무엇으로, 추천을 따랐는지. 도메인 전문가의
판단이라 「누가 왜」 를 반년 뒤에도 물을 수 있어야 한다."""
"""**물성↔시험 항목 제안을 묶어서 확인(또는 되돌림).** 한 번에 수십 줄이 바뀌는 일이라
줄마다 남기면 감사가 그것으로 덮인다 — 한 줄에 몇 건을 어느 쪽으로 옮겼는지 담는다.

이 확인은 검색이 물성으로 시험 항목을 펼칠 때 쓰는 근거이고, 내보내기가 카탈로그
정본(`property_links.json`)에 싣는 값이다. 누가 언제 무엇을 확인했는지는 남아야 한다."""
METHOD_REQUIREMENTS_IMPORTED = "method.requirements_imported"


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """바뀐 것만 남긴다.

    통째로 스냅샷하면 표가 커지고 **무엇이 바뀌었는지는 오히려 안 보인다.** 안
    바뀐 값 스무 개 사이에서 바뀐 하나를 찾게 된다.
    """
    return {
        key: {"before": before.get(key), "after": after[key]}
        for key in after
        if before.get(key) != after[key]
    }


def record(
    db: Session,
    *,
    action: str,
    actor: User | None,
    target_table: str,
    target_id: uuid.UUID | None,
    target_label: str,
    workspace_id: uuid.UUID | None = None,
    changes: dict[str, Any] | None = None,
    reason: str | None = None,
) -> AuditEntry:
    """감사 기록 하나. **부르는 쪽이 커밋한다.**

    actor 가 없을 수 있다(시스템이 한 일). 그때도 남긴다 — 안 남기면 "아무도 안
    했는데 바뀌었다" 가 되고, 그것이 가장 설명하기 어려운 상태다.
    """
    entry = AuditEntry(
        action=action,
        actor_id=actor.id if actor else None,
        # **그때의 이름을 박는다.** 계정이 지워지면 누가 했는지 모르게 되는데,
        # 그건 감사 로그가 존재하는 이유와 정면으로 어긋난다.
        actor_label=(actor.display_name or actor.email) if actor else "시스템",
        # **사람과 통로를 함께 남긴다.** 소유자만 남기면 사람이 넣은 것과 MCP 가
        # 넣은 것이 구별되지 않는다 — 그리고 그 구별이 필요해지는 날은 반드시 온다.
        actor_client=get_actor_client(),
        actor_token=get_actor_token(),
        target_table=target_table,
        target_id=target_id,
        target_label=target_label[:300],
        workspace_id=workspace_id,
        changes=changes or {},
        reason=reason,
        request_id=get_request_id(),
    )
    db.add(entry)
    return entry
