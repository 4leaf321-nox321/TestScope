"""FastAPI 앱 — API 와 SPA 를 한 프로세스가 서빙한다.

배포 산출물이 하나면 롤백도 하나다. 프론트를 따로 띄우는 구성은 개발에서는 편하지만
출하 형태가 성립하지 않는다 — "어느 쪽이 옛 버전인가" 를 물을 자리가 생긴다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import version
from app.config import Settings, get_settings
from app.database import SessionLocal, engine
from app.logging_setup import setup_logging
from app.modules.accounts import routes as accounts_routes
from app.modules.audit import routes as audit_routes
from app.modules.auth import routes as auth_routes
from app.modules.equipment import routes as equipment_routes
from app.modules.methods import routes as methods_routes
from app.modules.notices import routes as notices_routes
from app.modules.notifications import routes as notifications_routes
from app.modules.resolve import routes as resolve_routes
from app.modules.search import routes as search_routes
from app.modules.server import routes as server_routes
from app.modules.test_items import routes as capabilities_routes
from app.modules.vocabulary import routes as vocabulary_routes
from app.modules.workspaces import routes as workspaces_routes
from app.schema_version import warn_if_behind
from app.shared.access_log import AccessLogMiddleware
from app.shared.errors import NotFound, register_error_handlers
from app.shared.request_context import RequestIdMiddleware

logger = logging.getLogger(__name__)

API_PREFIX = "/api"


def _api_router() -> APIRouter:
    router = APIRouter(prefix=API_PREFIX)

    @router.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        # **버전을 함께 준다.** 원격에서 "지금 서버에 뭐가 깔렸나" 를 물을 수 있는
        # 유일한 자리다. 배포 뒤 확인도, 나중의 점검 스크립트도 여기를 본다.
        return {"status": "ok", "version": version.current()}

    # 모듈 라우터는 **여기서만** 모은다. 모듈이 서로를 import 하지 않게 하려면
    # 조립 지점이 하나여야 한다.
    router.include_router(auth_routes.router)
    router.include_router(accounts_routes.router)
    router.include_router(workspaces_routes.router)
    router.include_router(resolve_routes.router)
    router.include_router(vocabulary_routes.router)
    router.include_router(vocabulary_routes.conditions_router)
    router.include_router(vocabulary_routes.spec_groups_router)
    router.include_router(vocabulary_routes.spec_definitions_router)
    router.include_router(equipment_routes.router)
    router.include_router(equipment_routes.series_router)
    router.include_router(equipment_routes.catalog_router)
    router.include_router(equipment_routes.sources_router)
    router.include_router(methods_routes.router)
    router.include_router(capabilities_routes.router)
    router.include_router(search_routes.router)
    router.include_router(notices_routes.router)
    router.include_router(notifications_routes.router)
    router.include_router(audit_routes.router)
    router.include_router(server_routes.router)

    return router


def _mount_spa(app: FastAPI, settings: Settings) -> None:
    dist = settings.frontend_dist
    index = dist / "index.html"
    if not index.exists():
        logger.info("frontend dist 없음 (%s) — API만 서빙합니다.", dist)
        return

    # 해시가 붙은 자산은 오래 캐시해도 안전하다.
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    # response_model=None — 이 경로는 스키마에 나오지 않으므로 응답 모델이 필요
    # 없다. 반환 애노테이션에 Union 을 쓰면 FastAPI 가 모델을 만들려다 기동에
    # 실패하므로, 여기는 앞으로도 단일 Response 타입으로 둔다.
    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    def spa(full_path: str) -> FileResponse:
        # /api 아래는 위에서 이미 매칭됐어야 한다. 여기 닿았다면 없는 엔드포인트다.
        # index.html 을 돌려주면 프론트가 200 HTML 을 JSON 으로 파싱하려다 실패해
        # 원인이 흐려지므로, 명시적으로 404 를 준다. 응답 본문은 직접 만들지 않고
        # 오류 핸들러에 맡긴다 — 그래야 request_id 와 로그가 함께 남는다.
        if full_path.startswith("api/"):
            raise NotFound(
                "TSC-COMMON-0404",
                "존재하지 않는 엔드포인트입니다.",
                details={"path": f"/{full_path}"},
            )
        # index.html 은 캐시하지 않는다. 배포 후 사용자가 옛 index 를 들고 있으면
        # 사라진 청크를 요청하게 된다.
        return FileResponse(index, headers={"Cache-Control": "no-store"})

    logger.info("SPA 서빙: %s", dist)


def _guard_production_secrets(settings: Settings) -> None:
    """운영에서 기본 비밀키로 뜨는 것을 막는다.

    기본값이 그대로 배포되면 누구나 access 토큰을 위조할 수 있다. **경고 로그는
    아무도 읽지 않으므로 기동 자체를 거부한다.**
    """
    if settings.app_env != "production":
        return
    if settings.jwt_secret == Settings.model_fields["jwt_secret"].default:
        raise RuntimeError(
            "JWT_SECRET 이 기본값입니다. .env 에 난수 값을 넣고 다시 시작하세요."
        )


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)
    _guard_production_secrets(settings)

    app = FastAPI(
        title="TestScope API",
        version=version.current(),
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    # 순서가 중요하다. add_middleware 는 **나중에 더한 것이 바깥**이므로 아래 두
    # 줄은 RequestId(바깥) -> AccessLog(안쪽) 이 된다. 접근 로그가 요청 id 를
    # 읽으려면 그 id 가 먼저 설정돼 있어야 한다.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # 요청 처리 밖에서 DB 를 쓰는 곳(접근 로그)이 참조한다. 테스트는 이 값을 자기
    # DB 로 바꿔 끼운다.
    app.state.session_factory = SessionLocal
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_error_handlers(app)
    app.include_router(_api_router())

    # SPA catch-all 은 반드시 API 라우터 뒤에 등록한다.
    _mount_spa(app, settings)

    # **DB 가 코드보다 뒤처져 있으면 여기서 말한다.** 안 그러면 사람은 화면의 500
    # 으로 먼저 만나는데, 거기엔 원인이 안 적힌다.
    warn_if_behind(engine)

    logger.info("TestScope 기동 (env=%s)", settings.app_env)
    return app


app = create_app()
