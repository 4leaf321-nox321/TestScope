"""장비 API 의 요청·응답 형태."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.attributes.schemas import AttributeValueIn, AttributeValueOut


class CalibrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    calibrated_on: date
    next_due_on: date | None
    certificate_no: str | None
    provider: str | None
    """교정 기관 이름. 축의 값에서 온다."""
    provider_term_id: uuid.UUID | None
    note: str | None


class EquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_no: str
    name: str
    """현장 호칭. 카탈로그의 기종명(`model_name`)과 다른 칸이다."""
    dept_asset_no: str | None
    """부서관리번호. 부서 안에서만 유일하다."""

    model_id: uuid.UUID | None
    model_name: str | None
    """카탈로그의 기종명. **비어 있으면 카탈로그 미연결**이다 — 화면이 그것을
    표시한다. 빈 칸을 빈 칸으로 두면 아무도 안 채운다(ADR 0004)."""
    series_id: uuid.UUID | None
    series_name: str | None
    """그 기종이 속한 계열. 사람이 아는 이름은 대개 이쪽이다 — 「6800 시리즈」 는
    알아도 「68FM-300」 은 라벨을 봐야 안다(ADR 0006)."""
    category: str | None
    """장비유형. **기종이 있으면 그 계열의 분류**이고, 카탈로그 미연결이면 이 개체가
    직접 가리키는 분류다. 어느 쪽에서 왔든 화면이 같은 칸을 그린다."""
    category_group: str | None
    """장비군 — 그 유형의 최상위 조상(분류 축은 21군 / 87유형의 트리다).

    **칸으로 저장하지 않는다.** 저장하면 유형만 고친 날 군이 어긋나고, 그 어긋남은
    아무 화면에도 안 보인다."""
    manufacturer: str | None
    """**모델에서 끌어온다.** 개체는 이 둘을 갖지 않는다 — 같은 모델 열 대에 열 번
    적히면 열 번 다 같을 이유가 없다.

    카탈로그 미연결일 때만 개체의 표시용 칸(`maker_text`·`model_text`)에서 온다.
    그 값은 기준정보와 안 이어져 있어 **검색이 안 본다** — 화면이 그 사실을 말한다.

    이름으로 주는 이유: id 만 주면 목록 한 줄을 그리려고 화면이 카탈로그를 또
    조회해야 하고, 그 조회가 빠진 화면은 빈 칸을 보여 준다."""
    catalog_linked: bool
    """카탈로그의 기종에 이어져 있나. 아니면 제조사·모델명·분류가 **개체가 적은
    글자**라, 검색과 사양이 그것을 못 쓴다 — 목록이 그 사실을 표시한다."""

    serial_no: str | None
    workspace_slug: str | None
    workspace_name: str | None
    shared_use: bool
    """다른 부서도 쓸 수 있나. **가시성이 아니다** — 찾은 사람에게 「빌릴 수 있나」 를
    말해 준다."""
    site: str | None
    location: str | None
    status: str
    acquired_on: date | None
    manufactured_year: int | None
    retired_on: date | None
    """폐기일. 상태가 `retired` 일 때만 값이 있다."""
    contact_name: str | None
    note: str | None
    test_item_count: int
    """이 장비에 등록된 시험 항목 수. 0 이면 **검색에 절대 안 걸린다** — 목록에서
    그것이 보여야 채워 넣을 마음이 생긴다."""
    test_items: list[str]
    """이 장비가 하는 시험 항목. **목록 한 줄에서 바로 보인다** — 시험 항목을 열어 봐야
    아는 화면은 「우리가 무슨 시험을 할 수 있나」 에 답하지 못한다."""
    calibration_required: bool
    calibration_interval_months: int | None
    calibration_due_on: date | None
    """다음 교정 예정일. 지났으면 화면이 표를 단다.

    **성적서에 적힌 날이 언제나 이긴다** — 기관이 정한 날이 진실이다. 없으면 마지막
    교정일에 주기를 더해 계산하고, 그때는 `calibration_due_estimated` 가 참이다."""
    calibration_due_estimated: bool
    """위 날짜가 계산값인가. **계산값임을 말 안 하면 사람은 그것을 성적서로 읽는다.**"""
    calibration_missing: bool
    """교정 대상인데 이력이 한 건도 없나. **이력이 없다는 사실만으로는 못 가른다** —
    대상이 아닌 장비와 빠뜨린 장비가 같아 보이고, 그 둘은 할 일이 정반대다."""
    spec_override_count: int
    """카탈로그 위에 덮어 둔 실측 사양이 몇 칸인가. 0 이면 이 장비의 수치는 전부
    사양서에서 온 값이다."""
    attributes: list[AttributeValueOut]
    """부서가 붙인 속성 값(담당 구역·구매 연도 …) — 정식이 먼저, 초안이 뒤. 고정 칸이
    아닌 정보는 전부 이쪽이다(`modules/attributes`)."""
    created_at: datetime
    can_edit: bool
    """요청한 사람이 고칠 수 있는가. **서버가 판정한다** — 화면이 스스로 계산하면
    화면마다 답이 달라진다."""


class FilterOption(BaseModel):
    """거르기 한 칸이 고를 수 있는 값 하나. **수를 함께 준다.**

    「나노압입기」 를 고를 수 있는데 결과가 0 이면 사람은 거르기를 안 믿게 된다. 그래서
    **목록에 실제로 있는 값만** 내려보내고, 몇 대인지 함께 적는다.
    """

    model_config = ConfigDict(from_attributes=True)

    value: str
    label: str
    count: int
    detail: str | None = None
    """아래 줄에 흐리게 붙는 구별 — 분류라면 어느 군인지, 군이라면 「묶음 · N개 분류」."""


class EquipmentFilterOptionsOut(BaseModel):
    """보유 장비 목록의 열마다 고를 수 있는 값들.

    **보이는 장비만 센다**(`visible_equipment`) — 안 보이는 부서의 값을 골라 봐야
    결과가 비고, 그 빈 결과는 권한 때문인지 데이터 때문인지 구별되지 않는다.
    """

    model_config = ConfigDict(from_attributes=True)

    categories: list[FilterOption]
    workspaces: list[FilterOption]
    sites: list[FilterOption]
    statuses: list[FilterOption]
    test_items: list[FilterOption]


class CatalogFilterOptionsOut(BaseModel):
    """카탈로그 목록(계열·기종)의 열마다 고를 수 있는 값들.

    **목록에 실제로 있는 값만 준다.** 기준정보 전체를 펼치면 제조사 축 수백 종 중
    79종만 카탈로그에 쓰이고, 나머지는 골라도 0 건인 선택지가 된다 — 한 번 겪으면
    사람은 거르기를 안 믿는다.

    계열과 기종이 한 모양을 쓴다. 두 목록이 거르는 축(제조사·분류)이 같은 것이라,
    모양을 갈라 두면 한쪽만 고쳐지는 날이 온다.
    """

    model_config = ConfigDict(from_attributes=True)

    makers: list[FilterOption]
    categories: list[FilterOption]
    kinds: list[FilterOption]
    """계열의 종류(본체·부속·센서·소프트웨어). 기종 목록에서는 빈 목록이다 —
    기종은 종류를 갖지 않는다."""
    statuses: list[FilterOption]
    series: list[FilterOption]
    """기종 목록에서 계열로 좁힐 때. 계열 목록에서는 빈 목록이다."""


class EquipmentImportRequest(BaseModel):
    """엑셀에서 복사해 붙여넣은 대장.

    **파일이 아니다.** 문서 보안(DRM)이 걸린 환경에서는 파일을 올릴 수 없다 — 서식을
    내려받는 것은 되는데 그 파일을 다시 고르는 것이 막힌다. 붙여넣기는 DRM 이 막지
    못한다.

    엑셀이 클립보드에 넣는 것은 **탭으로 나뉜 글자**이고 우리 서식 파일은 쉼표다.
    서버가 첫 줄을 보고 정한다 — 사람이 어느 쪽을 들고 올지 우리가 정할 수 없다.

    **머리글 줄까지 함께** 붙여넣어야 한다. 없으면 어느 칸이 무엇인지 알 방법이 없다.
    """

    model_config = ConfigDict(from_attributes=True)

    text: str
    update_existing: bool = False
    """**이미 등록된 자산번호를 만나면 갱신한다.** 기본은 거절이다.

    부서는 엑셀 대장을 계속 굴린다. 300대 중 30대의 위치·상태가 바뀌었을 때 상세
    화면에서 30번 고치라는 것은 무리라, 같은 대장을 다시 붙여넣어 맞출 수 있어야 한다.

    ## 갱신이 건드리는 것과 안 건드리는 것

    **빈 칸은 「비운다」 가 아니라 「안 건드린다」 다.** 엑셀에 비고를 안 적었다고 기존
    비고가 지워지면 그것은 갱신이 아니라 사고다. 비우려면 상세 화면에서 한다.

    **부서와 기종은 안 바꾼다.** 이관은 양쪽 부서 관리자가 다 필요하고(반입한 사람은
    한쪽이다), 기종을 바꾸면 시험 항목이 다시 복사되지 않아 조건이 옛 기종의 것으로
    남는다. 둘 다 대장 갱신으로 조용히 일어나면 안 되는 일이라, 다르게 적혀 있으면
    그 줄을 막고 상세에서 하라고 말한다.

    시험 항목·교정 이력·실측 사양은 다른 표라 아예 안 닿는다."""


class ImportChange(BaseModel):
    """갱신에서 **바뀔 칸 하나.** 넣기 전에 무엇이 어떻게 바뀌는지 보여 주는 근거다.

    「30대를 갱신합니다」 만 말하면 사람은 누르고, 그 안에 잘못 붙은 열이 있었다는
    것을 나중에 안다. 칸마다 전후를 보이면 그 열은 누르기 전에 눈에 띈다.
    """

    model_config = ConfigDict(from_attributes=True)

    field: str
    before: str | None
    after: str | None


class ImportColumn(BaseModel):
    """반입 표의 열 하나.

    **화면이 자기 목록을 따로 들지 않게** 서버가 준다. 두 벌로 두면 열을 하나 더한
    날 한쪽만 고쳐지고, 그때 사람이 채운 칸이 조용히 버려진다.
    """

    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    required: bool
    """비우면 그 줄을 못 넣는 칸인가. 전부 「없으면 그 장비를 못 찾는」 것들이다."""
    aliases: list[str]
    """이 열로 받아 주는 머리글들(`label` 포함).

    **화면이 「머리글이 붙었나」 를 판정하는 근거다.** 사람이 머리글 없이 값만 복사하는
    일이 있고, 그때는 붙여넣기가 표 전체를 갈아 끼우면 안 되고 커서 자리부터 채워야
    한다. 그 판정을 화면이 자기 목록으로 하면 서버가 받아 주는 이름과 어긋나서,
    「보유 부서」 라고 적은 머리글이 값으로 읽힌다."""


class ImportProblem(BaseModel):
    """한 줄에서 걸린 것 하나. **어느 칸인지 함께 준다.**

    화면이 그 칸을 붉게 칠하려면 열을 알아야 한다. 글자에서 되짚어 찾게 하면
    (「거점:」 으로 시작하나 보고) 말을 조금만 다듬어도 색이 사라진다.
    """

    model_config = ConfigDict(from_attributes=True)

    field: str | None
    """열 키. **`None` 이면 줄 전체의 문제**다 — 자산번호가 다른 줄과 겹치는 것처럼
    한 칸에 못 붙이는 것이 있다."""
    message: str
    make_axis: str | None = None
    """**그 자리에서 만들 수 있는 기준정보 축**(열린 축일 때만). 없으면 `None`.

    거점 「3공장」 이 아직 축에 없다고 반입을 멈추면, 사람은 창을 닫고 기준정보로 가서
    만들고 돌아와 다시 붙여넣어야 한다 — 그 사이 표에서 고치던 것을 잃는다. 열린 축은
    원래 누구나 더하는 것이므로(`entry_policy=open`) 여기서 막을 이유가 없다.

    **반입이 스스로 만들지는 않는다.** 오타가 그대로 축이 되면 「본사」 와 「본사 」 가
    서로 다른 거점이 되고, 그 둘은 나중에 합칠 방법이 없다. 사람이 눌러서 만든다."""
    make_value: str | None = None
    """만들 값. 사람이 적은 그대로다."""


class EquipmentImportRow(BaseModel):
    """붙여넣은 한 줄이 어떻게 읽혔나.

    **줄 번호를 준다.** 「12번째 줄」 이라고 말해 줘야 사람이 엑셀에서 그 줄을 찾는다 —
    자산번호만 주면 아직 자산번호가 안 적힌 줄은 가리킬 방법이 없다.
    """

    model_config = ConfigDict(from_attributes=True)

    line: int
    """붙여넣은 것에서 몇 번째 줄인가. 머리글 다음이 2 다 — 엑셀이 보여 주는 번호와 같다."""
    cells: dict[str, str]
    """**서버가 읽은 그대로**의 칸 값(열 키 -> 글자).

    화면이 이것을 표로 그린다. 화면이 다시 파싱하게 두면 구분자 고르기·빈 줄
    건너뛰기·머리글 별칭이 두 벌이 되고, 두 벌은 반드시 어긋난다 — 그때 사람은
    자기가 붙여넣은 것과 다른 표를 본다."""
    asset_no: str | None
    name: str | None
    model_linked: bool
    """카탈로그의 기종에 이어졌나. **안 이어지면 시험 항목이 0 건**이고, 0 건이면
    그 장비는 검색에 절대 안 걸린다 — 넣기 전에 보여 줘야 하는 사실이다."""
    problems: list[ImportProblem]
    """빈 목록이면 넣을 수 있다. 첫 문제에서 멈추지 않고 **모아서** 준다 — 하나씩
    알려 주면 사람이 고치고 올리기를 문제 수만큼 되풀이한다."""
    imported: bool = False
    """**이 줄이 실제로 처리됐나** — 새로 들어갔거나 갱신됐거나. 미리보기면 언제나 `False`.

    화면이 그 줄을 표에서 지우는 근거다. 지우지 않으면 사람이 남은 것을 고쳐
    다시 넣을 때 이미 처리된 줄이 되돌아오고, 그때 무엇을 지워야 할지 모른다."""
    exists: bool = False
    """이 자산번호가 이미 등록돼 있나. `update_existing` 이면 새로 넣는 대신 갱신한다."""
    changes: list[ImportChange] = []
    """갱신이면 **바뀔 칸들.** 비어 있으면 대장과 시스템이 같다는 뜻이고, 그 줄은
    처리된 것으로 쳐서 표에서 사라진다."""


class EquipmentImportResult(BaseModel):
    """반입 한 번의 결과.

    `dry_run` 이면 `created` 는 0 이고 판정만 들어 있다.

    **넣을 수 있는 줄은 넣는다.** 문제가 있는 줄 때문에 멀쩡한 줄까지 막으면, 300줄
    중 12줄이 틀렸을 때 288줄을 다시 붙여넣어야 한다. 대신 화면이 들어간 줄을 표에서
    지워서(`EquipmentImportRow.imported`), 남은 것만 고쳐 다시 넣게 한다.

    **넣기로 한 것은 전부 되거나 전부 안 되거나다.** 문제 없는 줄들을 한 트랜잭션에
    담고, 그중 하나라도 막히면(그 사이 남이 같은 자산번호를 넣는 일이 있다) 통째로
    되돌린다 — 반쯤 들어간 채로 끝나지는 않는다.
    """

    model_config = ConfigDict(from_attributes=True)

    total: int
    ready: int
    problems: int
    created: int
    """실제로 새로 만들어진 장비 수. 미리보기면 0."""
    updated: int = 0
    """실제로 갱신된 장비 수. 미리보기면 0."""
    unchanged: int = 0
    """이미 있고 대장과 같은 줄 수. 손댈 것이 없어 처리된 것으로 친다."""
    rows: list[EquipmentImportRow]


class EquipmentCreateRequest(BaseModel):
    """보유 장비를 등록한다.

    **필수는 여덟이다** — 자산번호·장비명·보유 부서·거점·상세위치·공용여부·상태,
    그리고 장비유형(기종을 고르면 따라오므로 그때는 안 적는다).

    비울 수 없게 한 것들은 전부 「없으면 그 장비를 못 찾는」 칸이다. 나머지는 권장이나
    선택으로 둔다 — 다 적어야 저장되게 하면 사람은 등록을 미루고, 미룬 장비는 결국
    시스템 밖에 남는다.
    """

    asset_no: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    """현장 호칭. 「3동 만능기」 처럼 부르는 이름을 적는다 — 사람이 찾을 때 치는 말이다."""
    dept_asset_no: str | None = Field(default=None, max_length=50)
    """부서관리번호. 부서 안에서만 유일하면 된다."""
    workspace_slug: str
    """보유 부서. **비울 수 없다** — 장비에는 관리하는 부서가 반드시 있다.
    공용 장비도 마찬가지고, 공용인지는 `shared_use` 가 따로 말한다."""
    shared_use: bool = False
    """다른 부서도 쓸 수 있나."""

    model_id: uuid.UUID | None = None
    """카탈로그의 모델. **고르면 그 모델의 시험 항목이 이 장비로 복사된다** — 상속이
    아니라 복사다(ADR 0004). 그 뒤로는 이 장비가 진실이고, 챔버를 뗐다면 여기서
    고친다.

    비울 수 있다. 자작 장비나 아직 카탈로그에 없는 것이 실제로 있고, 그때 등록을
    막으면 사람은 시스템 밖에서 일한다."""

    serial_no: str | None = Field(default=None, max_length=100)

    category_term_id: uuid.UUID | None = None
    """장비유형. **기종을 고르면 안 적는다** — 분류는 그 기종의 계열이 갖는다
    (ADR 0006). 기종이 없으면 필수다: 무슨 종류인지 모르는 장비는 검색에서 통째로 빠진다."""
    maker_text: str | None = Field(default=None, max_length=200)
    model_text: str | None = Field(default=None, max_length=200)
    """카탈로그 미연결 장비의 제조사·모델명. **표시용이고 검색은 안 본다.**
    기종을 고르면 서버가 이 둘을 비운다 — 같은 사실이 두 곳에 남으면 안 된다."""

    site_term_id: uuid.UUID
    location: str = Field(min_length=1, max_length=200)
    """거점과 그 안의 자리. 둘 다 필수다 — 어디 있는지 모르는 장비는 찾아도 소용없다."""
    status: str = Field(default="operational")
    acquired_on: date | None = None
    manufactured_year: int | None = Field(default=None, ge=1900, le=2200)
    retired_on: date | None = None
    """폐기일. **상태가 `retired` 일 때만 받는다.**"""

    calibration_required: bool = False
    calibration_interval_months: int | None = Field(default=None, ge=1, le=600)
    """교정 대상이면 주기를 함께 적는다 — 없으면 차기일을 계산할 수 없고, 그러면
    「곧 만료」 목록이 이 장비를 영원히 안 부른다."""

    contact_user_id: uuid.UUID | None = None
    note: str | None = None
    attributes: list[AttributeValueIn] = Field(default_factory=list)
    """속성 값. `definition_id` 없이 `new_label` 이면 초안 속성이 생긴다."""


class EquipmentUpdateRequest(BaseModel):
    """**안 보낸 것과 비운 것을 구별한다.**

    부분 수정이라 None 은 "안 바꿈" 이다. 구별하지 않으면 상태 하나 바꿀 때마다
    담당자와 설치 위치가 지워지고, 그 손실은 저장한 사람 눈에 안 보인다.
    빈 문자열을 보내면 그것은 "비운다" 이다.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    dept_asset_no: str | None = None
    model_id: uuid.UUID | None = None
    """카탈로그 연결을 바꾼다. **시험 항목은 다시 복사되지 않는다** — 이미 이 장비의
    것이 된 값을 사양서로 덮으면, 손으로 고쳐 둔 실측이 조용히 사라진다.

    연결하면 개체가 적어 둔 분류·제조사·모델명은 서버가 비운다."""
    serial_no: str | None = None
    category_term_id: uuid.UUID | None = None
    maker_text: str | None = None
    model_text: str | None = None
    site_term_id: uuid.UUID | None = None
    location: str | None = None
    shared_use: bool | None = None
    status: str | None = None
    acquired_on: date | None = None
    manufactured_year: int | None = Field(default=None, ge=1900, le=2200)
    retired_on: date | None = None
    calibration_required: bool | None = None
    calibration_interval_months: int | None = Field(default=None, ge=1, le=600)
    contact_user_id: uuid.UUID | None = None
    note: str | None = None
    workspace_slug: str | None = None
    """다른 부서로 넘긴다. **넘기려면 양쪽 다 관리자여야 한다.**"""
    attributes: list[AttributeValueIn] | None = None
    """보내면 통째로 바뀐다 — 신뢰성 시험과 같은 규칙."""


class CalibrationCreateRequest(BaseModel):
    calibrated_on: date
    next_due_on: date | None = None
    certificate_no: str | None = Field(default=None, max_length=100)
    provider_term_id: uuid.UUID | None = None
    """교정 기관을 **축의 값 id 로** 준다. 같은 기관이 두 이름으로 갈리면
    「이 기관이 교정한 장비」 를 묻는 순간 절반만 답한다."""
    note: str | None = None


# --- 카탈로그 ----------------------------------------------------------------


class ModelLimitOut(BaseModel):
    """계열의 시험 항목의 조건 한 칸. 개체 쪽(LimitOut)과 같은 모양이다."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    condition_key_id: uuid.UUID
    condition_key: str
    condition_label: str
    si_unit: str
    display_unit: str
    min_value: float | None
    max_value: float | None
    text_value: str | None
    requires_accessory: bool
    """옵션 부속(챔버·노)이 있어야 나오는 범위. 검색이 「됨」 대신 「부속 있으면」 으로
    답한다."""
    note: str | None


class CitedMethodOut(BaseModel):
    """이 시험 항목이 인용하는 규격 하나. **표로 이어져 있다** — 비고의 글자가 아니다."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    edition: str | None
    title: str
    has_requirements: bool
    """그 규격의 요구 조건이 적혀 있나. **없으면 검색이 조건으로 좁히지 못한다** —
    화면이 그 사실을 말해야 채울 마음이 생긴다."""


class FreeSpecOut(BaseModel):
    """이 기종만의 사양 한 줄 — 정의 없이 기종에 직접 붙는 이름·값·단위."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    value_text: str
    unit: str | None
    note: str | None
    source_key: str | None
    """원본 키. 있으면 반입이 만든 줄이고, 「정의로 세우기」 가 같은 키의 다른 기종 줄을
    함께 옮길 수 있다."""
    origin: str
    source_id: uuid.UUID | None
    source_page: int | None
    same_key_models: int = 0
    """같은 원본 키를 가진 **다른** 기종 수. 0 이 아니면 정의로 세울 때가 된 것이다 —
    여러 기종이 공유하는 값은 비교할 수 있어야 한다."""


class FreeSpecUpsertRequest(BaseModel):
    label: str = Field(min_length=1, max_length=150)
    value_text: str = Field(min_length=1, max_length=4000)
    unit: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=2000)
    source_id: uuid.UUID | None = None
    source_page: int | None = Field(default=None, ge=1)


class FreeSpecPromoteRequest(BaseModel):
    """이 기종만의 사양을 **정의로 세운다.** 이름·단위·종류는 사람이 정한다 — 기계가 지어내면
    그것이 진실이 된다."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,59}$")
    label: str = Field(min_length=1, max_length=150)
    group_id: uuid.UUID
    kind: str = Field(pattern="^(number|range|text|boolean)$")
    unit: str = Field(default="", max_length=20)
    apply_same_key: bool = True
    """같은 원본 키를 가진 다른 기종의 줄도 함께 옮긴다. 한 기종만 옮기면 나머지는 「이
    기종만의 사양」 으로 남아 같은 값이 두 자리에 산다."""


class FreeSpecPromoteResult(BaseModel):
    definition_id: uuid.UUID
    moved: int
    """정의 값으로 옮긴 줄 수."""
    left: int
    """수치로 못 읽어 그대로 둔 줄 수 — 「약 300」 같은 것은 사람이 봐야 한다."""


class PendingMethodOut(BaseModel):
    """계열이 인용했는데 어느 시험 항목의 것인지 **아직 안 정해진** 규격 하나. 규격에
    시험 항목을 정하는 순간 그 시험 항목의 `methods` 로 옮겨 간다."""

    id: uuid.UUID
    code: str
    title: str


class SeriesTestItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_item_term_id: uuid.UUID
    test_item: str
    method_id: uuid.UUID | None
    method_code: str | None
    methods: list[CitedMethodOut]
    """카탈로그가 이 시험 항목에 인용한 규격들. **시험 항목을 규격마다 쪼개지 않는다** — 쪼개면
    검색이 같은 장비를 여덟 줄로 답한다."""
    note: str | None
    limits: list[ModelLimitOut]
    """**계열 전체가 만족하는 조건만** 여기 온다. 기종마다 갈리는 수치는 그 기종의
    사양에서 오고, 보유 장비를 만들 때 합쳐진다(ADR 0006)."""


class SeriesRelationOut(BaseModel):
    """계열에 붙은 관계 한 줄."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    relation: str
    other_series_id: uuid.UUID
    other_name: str
    other_maker: str | None
    other_kind: str
    note: str | None
    inbound: bool
    """이 계열이 관계의 **대상 쪽**인가. 챔버 화면에서 「이 챔버가 붙는 시험기들」 을
    보여 주려면 양방향이 다 필요하다 — 한쪽만 보여 주면 부속 화면이 늘 비어 있다."""


class EquipmentSeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    name_ko: str | None
    maker: str | None
    maker_term_id: uuid.UUID | None
    brand: str | None
    category: str | None
    category_term_id: uuid.UUID | None
    kind: str
    """본체(main)인가 부속(accessory·sensor·software)인가."""
    drive: str | None
    """구동 방식(기준정보 축). 이름으로 준다."""
    drive_term_id: uuid.UUID | None
    form_factor: str | None
    """기종 형태(기준정보 축). 이름으로 준다 — id 만 주면 목록 한 줄을 그리려고
    화면이 기준정보를 또 조회해야 한다."""
    form_factor_term_id: uuid.UUID | None
    status: str
    summary: str | None
    spec_note: str | None
    source_id: uuid.UUID | None
    source_path: str | None
    raw_limits: dict[str, Any]
    """계열 사양표 원문. 기종이 여럿이면 이 값은 **봉투**라 수치로 안 들이지만
    (ADR 0006), 사람이 읽을 값이라 원문을 남긴다."""

    model_count: int
    """이 계열에 든 기종 수. **0 이면 아무도 이 계열을 가리킬 수 없다** — 보유
    장비는 기종을 가리키기 때문이다."""
    unit_count: int
    operational_count: int
    """계열 전체의 보유 대수와 가동 대수. 기종별 수는 기종 목록이 갖는다."""

    test_items: list[SeriesTestItemOut]
    pending_methods: list[PendingMethodOut] = []
    """인용은 했는데 시험 항목 밑에 못 넣은 규격. 비어 있는 것이 정상이고, 남아 있으면
    그 규격의 시험 항목을 정하라는 뜻이다."""
    relations: list[SeriesRelationOut]
    attributes: list[AttributeValueOut] = []
    """관리자가 정의한 속성 값(「장비 계열 속성」). 고정 칸이 아닌 정보는 이쪽."""
    created_at: datetime
    can_edit: bool
    """카탈로그는 전사 공용이라 시스템 관리자만 고친다. **서버가 판정한다.**"""


class EquipmentSeriesCreateRequest(BaseModel):
    """계열을 만든다.

    **만들기 전에 `POST /api/resolve` 로 먼저 찾는다.** 같은 계열이 두 줄로 갈리면
    보유 장비가 어느 쪽을 가리켰는지에 따라 검색 결과가 나뉜다. 이미 있으면 409 가
    오고, `details.series_id` 에 그 id 가 실려 온다 — **409 는 실패가 아니라 답이다.**

    id 대신 이름을 줘도 된다(`maker` · `category`). 다만 그 이름이 기준정보에
    **하나로 정해질 때만** 받는다: 여럿이면 거절하고 후보를 돌려준다. 고르는 것은
    사람의 일이다.
    """

    name: str = Field(min_length=1, max_length=200)
    """계열 이름만 적는다. **제조사는 옆 칸이 갖는다** — 이름에 섞으면
    `Instron 6800` 과 `6800` 이 별개 계열로 갈린다."""
    name_ko: str | None = Field(default=None, max_length=200)
    maker_term_id: uuid.UUID | None = None
    maker: str | None = Field(default=None, max_length=200)
    """제조사를 **이름으로** 줄 때. id 가 있으면 id 가 이긴다.

    없는 제조사는 만들지 않는다 — 오타가 새 제조사가 되면 그 계열은 목록에서
    진짜 제조사들 사이에 혼자 선다."""
    brand: str | None = Field(default=None, max_length=100)
    category_term_id: uuid.UUID | None = None
    category: str | None = Field(default=None, max_length=200)
    """장비 분류를 **이름으로** 줄 때."""
    kind: str = Field(default="main", pattern="^(main|accessory|sensor|software)$")
    drive_term_id: uuid.UUID | None = None
    form_factor_term_id: uuid.UUID | None = None
    """기종 형태를 **축의 값 id 로** 준다. 자유 문자열이 아니다 — 원본 슬러그
    (`benchtop`)로 적어 오던 것을 그대로 두면 화면에 영어가 뜨고 거를 수도 없다."""
    summary: str | None = None
    spec_note: str | None = None
    source_id: uuid.UUID | None = None


class EquipmentSeriesUpdateRequest(BaseModel):
    """**안 보낸 것과 비운 것을 구별한다.** None 은 "안 바꿈" 이다."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    name_ko: str | None = Field(default=None, max_length=200)
    maker_term_id: uuid.UUID | None = None
    brand: str | None = Field(default=None, max_length=100)
    category_term_id: uuid.UUID | None = None
    kind: str | None = Field(default=None, pattern="^(main|accessory|sensor|software)$")
    drive_term_id: uuid.UUID | None = None
    form_factor_term_id: uuid.UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|discontinued)$")
    summary: str | None = None
    spec_note: str | None = None
    source_id: uuid.UUID | None = None
    attributes: list[AttributeValueIn] | None = None
    """보내면 통째로 바뀐다 — 신뢰성 시험과 같은 규칙."""


class SeriesRelationCreateRequest(BaseModel):
    part_series_id: uuid.UUID
    relation: str = Field(max_length=30)
    note: str | None = None
    """`-150 ~ +600 °C` 처럼 **무엇이 어떻게 바뀌는지**를 적는다."""


class ModelHeadlineSpecOut(BaseModel):
    """목록 한 줄이 그리는 **대표 사양** 한 칸.

    사양표(`ModelSpecValueOut`)와 값 칸의 이름을 맞춘다 — 화면이 값을 글자로 만드는
    함수를 하나만 두게 하려는 것이다. 모양을 달리 주면 목록과 상세가 같은 값을
    다르게 적는 날이 오고, 그때 어느 쪽이 맞는지는 아무도 모른다.
    """

    model_config = ConfigDict(from_attributes=True)

    definition_id: uuid.UUID
    key: str
    label: str
    kind: str
    si_unit: str
    display_unit: str
    num_value: float | None
    num_min: float | None
    num_max: float | None
    text_value: str | None
    bool_value: bool | None


class EquipmentModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    series_id: uuid.UUID
    series_name: str
    name: str
    name_ko: str | None
    maker: str | None
    maker_term_id: uuid.UUID | None
    category: str | None
    category_term_id: uuid.UUID | None
    """**계열에서 끌어온다.** 기종은 이 둘을 갖지 않는다 — 한 계열 열 기종에 열 번
    적히면 열 번 다 같을 이유가 없다.

    이름과 id 를 함께 주는 이유: 이름만으로는 사양 정의를 분류로 거를 수 없고,
    id 만으로는 목록 한 줄을 그리려고 화면이 기준정보를 또 조회해야 한다."""
    form_factor: str | None
    """기종 형태(기준정보 축). 이름으로 준다 — id 만 주면 목록 한 줄을 그리려고
    화면이 기준정보를 또 조회해야 한다."""
    form_factor_term_id: uuid.UUID | None
    status: str
    summary: str | None
    spec_note: str | None
    free_specs: list[FreeSpecOut] = []
    """정의 없이 이 기종에만 붙은 사양. 한 기종에만 나오는 값(803종)의 자리 — 정의 목록을
    안 부풀리면서 값은 들인다."""
    raw_specs: dict[str, Any]
    """제조사 카탈로그의 **사양 원문 그대로.**

    정의로 세운 칸은 위 사양표가 갖는다. 여기에는 정의가 없는 것까지 전부 있다 —
    원본에 950종 넘는 키가 있고 대부분이 한 카탈로그에만 나온다. 정의로 세우면
    관리 화면이 죽고, 안 세우면 사라진다. **그래서 둘 다 한다.**

    화면은 이것을 접어서 보여 준다: 「카탈로그 원문」."""

    unit_count: int
    """이 기종을 몇 대 가졌나. **카탈로그가 답해야 하는 첫 물음이다.**"""
    operational_count: int
    """그중 지금 쓸 수 있는 것. 다섯 대 중 한 대만 가동이면 그 사실이 목록에
    보여야 한다 — 대수만 보면 여유 있어 보인다."""

    test_items: list[SeriesTestItemOut]
    """**계열의 시험 항목이다.** 이 기종만의 것이 아니라 계열이 하는 시험 목록이고,
    조건은 이 기종의 사양이 좁힌다(ADR 0006)."""

    headline_specs: list[ModelHeadlineSpecOut]
    """이 기종을 목록 한 줄에서 **가르는** 사양 두어 칸.

    무엇이 대표인지는 **분류가 정한다**(온톨로지 `categories.json` 의
    `headline_specs`) — 만능시험기는 하중이고 챔버는 온도다. 안 정한 분류는 검색축에
    이어진 사양으로 대신한다: 이 시스템이 「판단에 쓰는 축」 이라고 이미 표시해 둔
    것들이라, 대표를 새로 정하는 것보다 정본이 하나 적다.

    **이름·계열·제조사만으로는 못 고른다.** 한 계열에 기종이 열일곱까지 있고, 그
    열일곱을 가르는 것은 이 수치다."""
    spec_count: int
    """적힌 사양이 몇 칸인가. 0 이면 이 기종으로 등록하는 장비가 **조건 없이**
    복사되고, 검색은 그것을 「모름」 으로 답한다."""
    created_at: datetime
    can_edit: bool


class EquipmentSeriesRow(BaseModel):
    """계열 **목록** 한 줄. 상세(`EquipmentSeriesOut`)와 일부러 다르다.

    ## 목록이 그리는 것만 싣는다

    상세를 목록에 실었더니 50줄짜리 한 쪽이 질의를 1,058회 했다. 그중 대부분은
    시험 항목마다 인용 규격과 조건 수치를 만드느라 든 것인데, **목록 화면이 그
    시험 항목으로 하는 일은 개수를 세는 것뿐**이었다. 46 KB 를 만들어 보내고
    `length` 를 읽은 셈이다.

    부속 관계(`relations`)와 사양 원문(`raw_limits`)은 목록이 아예 안 그린다.

    그래서 목록은 요약만 준다. 상세가 필요하면 상세를 부른다 — 목록에서 한 줄을
    누르면 어차피 그리로 간다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    name_ko: str | None
    maker: str | None
    brand: str | None
    category: str | None
    kind: str
    """본체(main)인가 부속(accessory·sensor·software)인가."""
    status: str

    model_count: int
    """이 계열에 든 기종 수. **0 이면 아무도 이 계열을 가리킬 수 없다** — 보유
    장비는 기종을 가리키기 때문이다."""
    unit_count: int
    operational_count: int
    test_item_count: int
    """무슨 시험이 되는지는 상세에서 본다. **0 이면 그 계열의 장비는 검색에 절대
    안 걸린다** — 목록이 그 사실만 말해 주면 된다."""


class EquipmentModelRow(BaseModel):
    """기종 **목록** 한 줄. 상세(`EquipmentModelOut`)와 일부러 다르다.

    시험 항목은 **이름만** 싣는다. 조건 수치와 인용 규격은 계열이 갖는 값이라
    형제 기종끼리 전부 같고, 목록은 그것을 그리지 않는다 — 50줄에 52 KB 였다.

    사양 원문(`raw_specs`)도 안 싣는다. 목록이 그리는 것은 분류가 정한 대표
    사양(`headline_specs`) 두어 칸이다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    series_id: uuid.UUID
    series_name: str
    name: str
    name_ko: str | None
    maker: str | None
    category: str | None
    form_factor: str | None
    status: str

    unit_count: int
    operational_count: int

    test_items: list[str]
    """**계열의 시험 항목 이름들.** 수가 아니라 이름을 준다 — 「2」 는 무슨 시험이
    되는지에 아무 답도 못 한다."""

    headline_specs: list[ModelHeadlineSpecOut]
    """이 기종을 목록 한 줄에서 **가르는** 사양 두어 칸."""
    spec_count: int
    """사양이 몇 칸 적혔나. **0 과 「대표만 없음」 은 다르다** — 앞엣것은 채워야 할
    구멍이고, 뒤엣것은 이 분류에 대표를 안 정해 둔 것뿐이다."""


class EquipmentModelCreateRequest(BaseModel):
    """기종을 만든다. **계열이 먼저 있어야 한다.**

    `series_id` 대신 `series`(계열 이름)를 줘도 된다. 제조사를 함께 주면 같은
    이름의 계열이 여럿일 때 하나로 좁혀진다.
    """

    series_id: uuid.UUID | None = None
    """**결국 비울 수 없다.** 단품이면 기종 하나짜리 계열을 먼저 만든다 — 예외를
    두면 화면이 매번 갈래를 타야 하고, 한 곳에서 빠뜨리면 그 기종이 목록에서
    사라진다. id 를 안 주면 `series` 이름으로 찾는다."""
    series: str | None = Field(default=None, max_length=200)
    """계열을 **이름으로** 줄 때. 하나로 정해지지 않으면 거절하고 후보를 준다."""
    maker: str | None = Field(default=None, max_length=200)
    """`series` 로 찾을 때 제조사까지 주면 후보가 줄어든다."""
    name: str = Field(min_length=1, max_length=150)
    name_ko: str | None = Field(default=None, max_length=150)
    form_factor_term_id: uuid.UUID | None = None
    """기종 형태를 **축의 값 id 로** 준다. 자유 문자열이 아니다 — 원본 슬러그
    (`benchtop`)로 적어 오던 것을 그대로 두면 화면에 영어가 뜨고 거를 수도 없다."""
    summary: str | None = None
    spec_note: str | None = None


class EquipmentModelUpdateRequest(BaseModel):
    """**안 보낸 것과 비운 것을 구별한다.** None 은 "안 바꿈" 이다."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    name_ko: str | None = Field(default=None, max_length=150)
    series_id: uuid.UUID | None = None
    """계열을 옮긴다. **시험 항목은 다시 복사되지 않는다** — 이미 등록된 장비의 값은
    그 장비가 갖는다."""
    form_factor_term_id: uuid.UUID | None = None
    status: str | None = Field(default=None, pattern="^(active|discontinued)$")
    summary: str | None = None
    spec_note: str | None = None


class SeriesTestItemCreateRequest(BaseModel):
    """이 계열이 무슨 시험을 하나.

    시험 항목은 **닫힌 축**이라 없는 이름은 안 받는다 — 오타가 값이 되면 그 계열의
    장비는 영영 검색에 안 걸린다.
    """

    test_item_term_id: uuid.UUID | None = None
    test_item: str | None = Field(default=None, max_length=200)
    """시험 항목을 **이름으로** 줄 때. 별칭도 본다 — 「UTM」 으로 물으면
    「만능재료시험기」 가 나온다."""
    method_id: uuid.UUID | None = None
    method_code: str | None = Field(default=None, max_length=100)
    """시험법을 **규격 번호로** 줄 때. `ASTM E8/E8M`."""
    note: str | None = None


class ModelLimitUpsertRequest(BaseModel):
    """조건 한 칸을 넣거나 덮어쓴다. 개체 쪽과 같은 규칙이다 —
    **비운 쪽은 "제한 없음"** 이고 0 이 아니다."""

    condition_key_id: uuid.UUID
    min_value: float | None = None
    max_value: float | None = None
    text_value: str | None = Field(default=None, max_length=200)
    note: str | None = None
    requires_accessory: bool = False


# --- 모델 사양 ---------------------------------------------------------------


class ModelSpecValueOut(BaseModel):
    """사양 한 칸의 값. **정의의 계약을 함께 실어 준다.**

    화면이 이 값을 그리려면 단위와 종류를 알아야 하고, 그것을 따로 조회하게 하면
    조회를 빠뜨린 화면이 단위 없는 숫자를 보여 준다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    definition_id: uuid.UUID
    key: str
    label: str
    kind: str
    si_unit: str
    display_unit: str
    choices: list[str]
    sort_order: int
    is_active: bool
    """정의가 꺼졌어도 이미 적힌 값은 보여 준다 — 안 보이면 지워진 줄 안다."""
    condition_key_id: uuid.UUID | None
    """채워져 있으면 이 값이 시험 조건으로 따라 들어간 사양이다."""
    axis_unit_mismatch: bool = False
    """검색축에 이었는데 **단위를 못 맞춘다**(쇼어 경도 ↔ kN). 참이면 이 값은 검색에 안 실린다.
    조용히 빠지면 「검색축인데 왜 모름이라 하지」 가 되므로 화면이 말한다."""
    applies: bool
    """이 모델의 분류에 붙는 사양인가. **false 라도 값은 준다** — 분류를 나중에
    고쳤다고 이미 적은 사양이 사라지면 안 된다(ADR 0005)."""

    num_value: float | None
    num_min: float | None
    num_max: float | None
    text_value: str | None
    bool_value: bool | None
    note: str | None
    requires_accessory: bool
    source_id: uuid.UUID | None
    source_path: str | None
    source_page: int | None
    updated_at: datetime


class ModelSpecGroupOut(BaseModel):
    group_id: uuid.UUID
    slug: str
    label: str
    description: str | None
    items: list[ModelSpecValueOut]


class ModelSpecSheetOut(BaseModel):
    """모델에 **적힌** 사양만 담는다.

    빈 칸 목록은 `/spec-definitions?category_term_id=…` 가 준다. 여기에 다 실으면
    한 모델을 열 때마다 수백 줄이 오가고, 그 대부분은 회색으로 그려진다.
    """

    model_id: uuid.UUID
    groups: list[ModelSpecGroupOut]


class ModelSpecValueUpsertRequest(BaseModel):
    """사양 한 칸을 넣거나 덮어쓴다.

    **종류에 맞는 칸만 채운다.** 나머지는 안 보내면 되고, 서버가 그것을 비운다 —
    남겨 두면 화면마다 어느 칸을 읽느냐에 따라 다른 값이 보인다.
    """

    definition_id: uuid.UUID
    num_value: float | None = None
    num_min: float | None = None
    num_max: float | None = None
    text_value: str | None = None
    bool_value: bool | None = None
    note: str | None = None
    requires_accessory: bool = False
    """본체가 아니라 옵션 부속(챔버·노)이 있어야 나오는 값이면 켠다."""
    """수치로 못 담는 단서. "챔버 장착 시" · "1상/3상에 따라 다름"."""
    source_id: uuid.UUID | None = None
    source_page: int | None = Field(default=None, ge=1)


class ModelSpecSaveResult(BaseModel):
    """저장 결과. **이 값이 검색에 쓰이는지, 이미 등록된 장비는 어떻게 되는지.**

    "저장했습니다" 만 말하면 둘 다 사람이 알 수 없다. 그리고 둘 다 모르면 사람은
    바뀌었다고 믿는데, 그 믿음은 검색 결과가 어긋난 날에야 깨진다.
    """

    value: ModelSpecValueOut
    search_axis: str | None
    """이어진 검색축의 이름. 채워져 있으면 **이 기종으로 앞으로 등록할 장비**의
    시험 조건이 된다. 비어 있으면 사양표에만 남는다 — 대부분이 그렇고 그래도 된다."""
    existing_units: int
    """이 기종으로 **이미 등록된** 보유 장비 수. 그들에게는 반영되지 않는다 —
    개체의 값은 개체가 갖는다(ADR 0004)."""


class SpecSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    path: str
    title: str | None
    maker: str | None
    pages: int | None
    published_on: date | None


class EquipmentSpecValueOut(BaseModel):
    """개체가 덮어 둔 실측값 한 칸. 사양표의 값(`ModelSpecValueOut`)과 값 칸을 맞춘다."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    num_value: float | None
    num_min: float | None
    num_max: float | None
    text_value: str | None
    bool_value: bool | None
    measured_on: date | None
    note: str | None
    source_id: uuid.UUID | None
    source_path: str | None
    source_page: int | None
    updated_at: datetime


class EquipmentSpecItemOut(BaseModel):
    """사양 한 칸 — **카탈로그 값과 실측을 함께 준다.**

    화면이 둘을 겹쳐 그린다: 「실측 300 kN (사양서 250 kN)」. 하나만 주면 사람은 그
    수치가 잰 값인지 사양서에서 온 값인지 알 수 없고, 그 둘은 믿는 정도가 다르다.
    """

    model_config = ConfigDict(from_attributes=True)

    definition_id: uuid.UUID
    key: str
    label: str
    kind: str
    si_unit: str
    display_unit: str
    choices: list[str]
    sort_order: int
    condition_key_id: uuid.UUID | None
    """채워져 있으면 이 칸을 덮을 때 **이 장비의 시험 조건도 함께 갱신된다.**"""

    catalog: ModelSpecValueOut | None
    """기종이 말하는 값. 카탈로그 미연결이거나 그 기종에 안 적힌 칸이면 비어 있다."""
    measured: EquipmentSpecValueOut | None
    """우리가 잰 값. **있으면 이쪽이 이긴다.**"""


class EquipmentSpecGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_id: uuid.UUID
    slug: str
    label: str
    description: str | None
    items: list[EquipmentSpecItemOut]


class EquipmentSpecSheetOut(BaseModel):
    """이 장비의 사양 — 기종 사양 위에 실측을 덮은 것.

    **복사가 아니라 겹쳐 보기다.** 개체는 다른 값만 갖고, 나머지는 기종 사양이 그대로
    보인다 — 전부 복사하면 카탈로그가 개정돼도 안 따라오고, 어느 값이 실측인지 구별이
    사라진다.
    """

    model_config = ConfigDict(from_attributes=True)

    equipment_id: uuid.UUID
    model_id: uuid.UUID | None
    model_name: str | None
    groups: list[EquipmentSpecGroupOut]
    override_count: int


class EquipmentSpecSaveRequest(BaseModel):
    """실측 한 칸을 넣거나 덮어쓴다. **종류에 맞는 칸만 채운다.**"""

    definition_id: uuid.UUID
    num_value: float | None = None
    num_min: float | None = None
    num_max: float | None = None
    text_value: str | None = None
    bool_value: bool | None = None
    measured_on: date | None = None
    note: str | None = None
    source_id: uuid.UUID | None = None
    source_page: int | None = None


class EquipmentSpecSaveResult(BaseModel):
    value: EquipmentSpecValueOut
    condition_label: str | None
    """검색축에 이어진 사양이면 그 축 이름. **이 숫자가 검색에 쓰인다**는 뜻이다."""
    reflected: bool
    """이 장비의 시험 조건이 실제로 갱신됐나. 손으로 고쳐 둔 조건은 안 덮는다."""
