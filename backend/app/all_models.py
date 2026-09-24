"""모든 ORM 모델을 한 곳에서 import 한다.

Alembic autogenerate 는 Base.metadata 에 등록된 것만 본다. 모듈이 늘어날 때 여기에
한 줄을 더하지 않으면, 새 표가 안 보이는 정도가 아니라 **기존 표를 지우는
마이그레이션**이 생성된다. 그래서 모으는 지점을 하나로 고정한다.

DB 를 만지는 스크립트도 이 모듈을 import 한다 — 앱에서는 안 드러나고 배포 뒤
그 스크립트를 돌릴 때만 터진다.
"""

from __future__ import annotations

from app.database import Base
from app.jobs.models import Job
from app.modules.accounts.models import User
from app.modules.attachments.models import Attachment, StoredFile
from app.modules.attributes.models import AttributeDefinition, AttributeValue
from app.modules.audit.models import AccessLog, AuditEntry
from app.modules.auth.models import PersonalAccessToken, RefreshToken
from app.modules.documents.models import SpecDocument
from app.modules.equipment.models import (
    Equipment,
    EquipmentCalibration,
    EquipmentModel,
    EquipmentSeries,
    EquipmentSpecValue,
    ModelFreeSpec,
    ModelSpecValue,
    SeriesRelation,
    SpecSource,
)
from app.modules.methods.models import MethodRequirement, TestMethod, TestMethodItem
from app.modules.notices.models import Notice, NoticeRead
from app.modules.notifications.models import Notification
from app.modules.properties.models import TestItemProperty
from app.modules.reliability.models import ReliabilityTest, ReliabilityTestItem
from app.modules.review.models import ReviewProposal, ReviewVote
from app.modules.test_items.models import (
    EquipmentTestCondition,
    EquipmentTestItem,
    SeriesPendingMethod,
    SeriesTestCondition,
    SeriesTestItem,
    SeriesTestItemMethod,
    TestItemConditionKey,
)
from app.modules.vocabulary.models import (
    ConditionKey,
    Vocabulary,
    VocabularyAlias,
    VocabularyTerm,
)
from app.modules.vocabulary.specs import (
    SpecDefinition,
    SpecDefinitionCategory,
    SpecGroup,
)
from app.modules.workspaces.models import Workspace, WorkspaceMember

__all__ = [
    "AccessLog",
    "Attachment",
    "AttributeDefinition",
    "AttributeValue",
    "AuditEntry",
    "Base",
    "ConditionKey",
    "Equipment",
    "EquipmentCalibration",
    "EquipmentModel",
    "EquipmentSeries",
    "EquipmentSpecValue",
    "EquipmentTestCondition",
    "EquipmentTestItem",
    "Job",
    "MethodRequirement",
    "ModelFreeSpec",
    "ModelSpecValue",
    "Notice",
    "NoticeRead",
    "Notification",
    "PersonalAccessToken",
    "RefreshToken",
    "ReliabilityTest",
    "ReliabilityTestItem",
    "ReviewProposal",
    "ReviewVote",
    "SeriesPendingMethod",
    "SeriesRelation",
    "SeriesTestCondition",
    "SeriesTestItem",
    "SeriesTestItemMethod",
    "SpecDefinition",
    "SpecDefinitionCategory",
    "SpecDocument",
    "SpecGroup",
    "SpecSource",
    "StoredFile",
    "TestItemConditionKey",
    "TestItemProperty",
    "TestMethod",
    "TestMethodItem",
    "User",
    "Vocabulary",
    "VocabularyAlias",
    "VocabularyTerm",
    "Workspace",
    "WorkspaceMember",
]
