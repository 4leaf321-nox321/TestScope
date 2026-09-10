/** 장비·시험 항목 API. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Equipment = components['schemas']['EquipmentOut']
export type Calibration = components['schemas']['CalibrationOut']
export type EquipmentFilterOptions = components['schemas']['EquipmentFilterOptionsOut']
export type EquipmentSpecSheet = components['schemas']['EquipmentSpecSheetOut']
export type EquipmentSpecItem = components['schemas']['EquipmentSpecItemOut']
type EquipmentSpecSaveResult = components['schemas']['EquipmentSpecSaveResult']
export type EquipmentTestItem = components['schemas']['EquipmentTestItemOut']
export type EquipmentTestCondition = components['schemas']['LimitOut']
type EquipmentPage = components['schemas']['Page_EquipmentOut_']

export type EquipmentSeries = components['schemas']['EquipmentSeriesOut']
export type SeriesRelation = components['schemas']['SeriesRelationOut']
type SeriesPage = components['schemas']['Page_EquipmentSeriesOut_']
export type EquipmentModel = components['schemas']['EquipmentModelOut']
export type SeriesTestItem = components['schemas']['SeriesTestItemOut']
export type ModelLimit = components['schemas']['ModelLimitOut']
export type ModelHeadlineSpec = components['schemas']['ModelHeadlineSpecOut']
type ModelPage = components['schemas']['Page_EquipmentModelOut_']

export const equipmentApi = {
  /**
   * 목록. **거르기는 전부 서버가 한다.**
   *
   * 화면이 한 쪽을 받아 놓고 거르면 상한을 넘는 순간 나머지가 조용히 빠지고, 그때
   * 목록은 「그 조건에 맞는 장비가 이것뿐」 이라고 거짓말한다.
   */
  list: (params: {
    q?: string
    /** 열마다 따로 거를 때. `q` 는 자산번호와 이름을 함께 보고, 이 둘은 **그 열만** 본다. */
    assetNo?: string
    name?: string
    status?: string
    workspace?: string
    /** 이 기종의 장비만. */
    modelId?: string
    categoryTermId?: string
    siteTermId?: string
    testItemTermId?: string
    /** `required` 대상 전부 · `exempt` 대상 아님 · `missing` 이력 없음 · `overdue` 기한 지남. */
    calibration?: string
    sharedUse?: boolean
    limit?: number
    offset?: number
  }) => {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.assetNo) search.set('asset_no', params.assetNo)
    if (params.name) search.set('name', params.name)
    if (params.status) search.set('status', params.status)
    if (params.workspace) search.set('workspace', params.workspace)
    if (params.modelId) search.set('model_id', params.modelId)
    if (params.categoryTermId) search.set('category_term_id', params.categoryTermId)
    if (params.siteTermId) search.set('site_term_id', params.siteTermId)
    if (params.testItemTermId) search.set('test_item_term_id', params.testItemTermId)
    if (params.calibration) search.set('calibration', params.calibration)
    if (params.sharedUse !== undefined) search.set('shared_use', String(params.sharedUse))
    if (params.limit) search.set('limit', String(params.limit))
    if (params.offset) search.set('offset', String(params.offset))
    const query = search.toString()
    return api.get<EquipmentPage>(`/equipment${query ? `?${query}` : ''}`)
  },
  /**
   * 열마다 고를 수 있는 값과 그 수.
   *
   * **기준정보 전체를 안 쓴다.** 분류 108종 중 100종이 골라도 0 건인 선택지가 되면
   * 사람은 거르기를 안 믿는다. 부서도 여기서 받는다 — `/workspaces` 는 내 소속만
   * 주는데, 목록에는 열린 부서의 장비가 함께 보인다.
   */
  filterOptions: () => api.get<EquipmentFilterOptions>('/equipment/filter-options'),
  read: (id: string) => api.get<Equipment>(`/equipment/${id}`),
  create: (body: Record<string, unknown>) => api.post<Equipment>('/equipment', body),
  update: (id: string, body: Record<string, unknown>) =>
    api.patch<Equipment>(`/equipment/${id}`, body),
  remove: (id: string) => api.delete<void>(`/equipment/${id}`),

  calibrations: (id: string) => api.get<Calibration[]>(`/equipment/${id}/calibrations`),
  addCalibration: (id: string, body: Record<string, unknown>) =>
    api.post<Calibration>(`/equipment/${id}/calibrations`, body),
}

/**
 * 개체 사양 — **카탈로그 값 위에 덮는 실측.**
 *
 * 기종 사양(`specApi`)과 헷갈리면 한 대의 실측이 그 기종 열 대의 기준이 된다.
 * 저기는 「제조사가 그렇게 적었다」 이고, 여기는 「우리가 이 대를 재 보니 그렇더라」 다.
 *
 * `sheet` 는 둘을 한 줄에 함께 준다 — 화면이 맞추게 두면 화면마다 이기는 쪽이 달라진다.
 */
export const equipmentSpecApi = {
  sheet: (equipmentId: string) =>
    api.get<EquipmentSpecSheet>(`/equipment/${equipmentId}/specs`),
  /** 한 칸을 넣거나 덮어쓴다. 응답의 `reflected` 는 시험 조건이 갱신됐는지다. */
  put: (equipmentId: string, body: Record<string, unknown>) =>
    api.put<EquipmentSpecSaveResult>(`/equipment/${equipmentId}/specs`, body),
  /** 실측을 지운다 — 그 칸은 다시 카탈로그 값으로 보인다. */
  remove: (equipmentId: string, definitionId: string) =>
    api.delete<void>(`/equipment/${equipmentId}/specs/${definitionId}`),
}

export const testItemApi = {
  forEquipment: (equipmentId: string) =>
    api.get<EquipmentTestItem[]>(`/equipment-test-items?equipment_id=${equipmentId}`),
  create: (body: Record<string, unknown>) =>
    api.post<EquipmentTestItem>('/equipment-test-items', body),
  update: (id: string, body: Record<string, unknown>) =>
    api.patch<EquipmentTestItem>(`/equipment-test-items/${id}`, body),
  remove: (id: string) => api.delete<void>(`/equipment-test-items/${id}`),
  /** 조건 한 칸은 **덮어쓰기다** — 같은 조건이 둘이면 어느 쪽이 맞는지 알 수 없다. */
  putLimit: (testItemId: string, body: Record<string, unknown>) =>
    api.put<EquipmentTestCondition>(`/equipment-test-items/${testItemId}/limits`, body),
  removeLimit: (testItemId: string, limitId: string) =>
    api.delete<void>(`/equipment-test-items/${testItemId}/limits/${limitId}`),
}

/**
 * 장비 계열 — **제조사가 파는 계열.**
 *
 * 무슨 시험이 되나(시험 항목), 어느 부속이 붙나(관계), 누가 만들었나가 여기 붙는다.
 * 수치는 기종이 갖는다 — 한 계열 안에서 하중이 중앙값 60배 갈리기 때문이다
 * (ADR 0006).
 */
export const seriesApi = {
  list: (params: {
    q?: string
    kind?: string
    /** 보유 장비가 가리키는 계열만. 홈의 「남은 일」 이 이걸로 링크한다. */
    owned?: boolean
    issue?: string
    limit?: number
  }) => {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.kind) search.set('kind', params.kind)
    if (params.owned) search.set('owned', 'true')
    if (params.issue) search.set('issue', params.issue)
    if (params.limit) search.set('limit', String(params.limit))
    const query = search.toString()
    return api.get<SeriesPage>(`/equipment-series${query ? `?${query}` : ''}`)
  },
  read: (id: string) => api.get<EquipmentSeries>(`/equipment-series/${id}`),
  create: (body: Record<string, unknown>) =>
    api.post<EquipmentSeries>('/equipment-series', body),
  update: (id: string, body: Record<string, unknown>) =>
    api.patch<EquipmentSeries>(`/equipment-series/${id}`, body),
  remove: (id: string) => api.delete<void>(`/equipment-series/${id}`),

  addTestItem: (seriesId: string, body: Record<string, unknown>) =>
    api.post<SeriesTestItem>(`/equipment-series/${seriesId}/test_items`, body),
  removeTestItem: (seriesId: string, testItemId: string) =>
    api.delete<void>(`/equipment-series/${seriesId}/test_items/${testItemId}`),
  /** 조건 한 칸은 **덮어쓰기다** — 같은 조건이 둘이면 어느 쪽이 맞는지 알 수 없다. */
  putLimit: (seriesId: string, testItemId: string, body: Record<string, unknown>) =>
    api.put<ModelLimit>(`/equipment-series/${seriesId}/test_items/${testItemId}/limits`, body),
  removeLimit: (seriesId: string, testItemId: string, limitId: string) =>
    api.delete<void>(
      `/equipment-series/${seriesId}/test_items/${testItemId}/limits/${limitId}`,
    ),

  addRelation: (seriesId: string, body: Record<string, unknown>) =>
    api.post<SeriesRelation>(`/equipment-series/${seriesId}/relations`, body),
  removeRelation: (seriesId: string, relationId: string) =>
    api.delete<void>(`/equipment-series/${seriesId}/relations/${relationId}`),
}

/**
 * 장비 기종 — **보유 장비가 가리키는 것.**
 *
 * 계열을 가리키게 두면 검색이 답할 수 없다: 「300 kN 됩니까」 에 계열은
 * 「0.5~300 kN 입니다」 라고밖에 못 하고, 그 대답은 우리가 가진 그 한 대에 대해
 * 아무것도 말하지 않는다(ADR 0006).
 *
 * 장비를 등록할 때 기종을 고르면 **계열의 시험 항목이 그 개체로 복사되고, 조건은 이
 * 기종의 사양에서 온다** — 상속이 아니라 복사라, 그 뒤로는 개체가 진실이다.
 */
export const catalogApi = {
  list: (params: {
    q?: string
    seriesId?: string
    /** 보유 장비가 가리키는 기종만. */
    owned?: boolean
    /** `specs` 사양이 빈 것 · `uncertain` 원본 확인이 필요한 것. */
    issue?: string
    limit?: number
    /** 몇 째부터. **714기종이라 한 쪽에 안 담긴다** — 안 넘기면 나머지가 조용히
     *  안 보이고, 못 찾은 사람은 없다고 결론 내리고 새로 만든다. */
    offset?: number
  }) => {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.seriesId) search.set('series_id', params.seriesId)
    if (params.owned) search.set('owned', 'true')
    if (params.issue) search.set('issue', params.issue)
    if (params.limit) search.set('limit', String(params.limit))
    if (params.offset) search.set('offset', String(params.offset))
    const query = search.toString()
    return api.get<ModelPage>(`/equipment-models${query ? `?${query}` : ''}`)
  },
  read: (id: string) => api.get<EquipmentModel>(`/equipment-models/${id}`),
  create: (body: Record<string, unknown>) =>
    api.post<EquipmentModel>('/equipment-models', body),
  update: (id: string, body: Record<string, unknown>) =>
    api.patch<EquipmentModel>(`/equipment-models/${id}`, body),
  remove: (id: string) => api.delete<void>(`/equipment-models/${id}`),
}

export type ModelSpecSheet = components['schemas']['ModelSpecSheetOut']
export type ModelSpecValue = components['schemas']['ModelSpecValueOut']
type SpecSaveResult = components['schemas']['ModelSpecSaveResult']
export type SpecSource = components['schemas']['SpecSourceOut']
type SpecSourcePage = components['schemas']['Page_SpecSourceOut_']

/**
 * 모델 사양 — **정의는 통제하고 값은 자유롭게**(ADR 0005).
 *
 * 화면은 둘을 겹쳐 그린다: 여기 `sheet` 가 **적힌 값**을, 기준정보 쪽
 * `vocabularyApi.specDefinitions` 가 **적을 수 있는 칸**을 준다. 빈 칸까지 사양표에
 * 실으면 한 모델을 열 때마다 수백 줄이 오간다.
 *
 * 정의가 저쪽에 있는 이유: 조건 정의와 같은 성격이라 고치는 화면도 같다.
 */
export const specApi = {
  sheet: (modelId: string) => api.get<ModelSpecSheet>(`/equipment-models/${modelId}/specs`),
  /** 한 칸을 넣거나 덮어쓴다. 응답의 `reflected` 는 시험 항목에 반영된 수다. */
  put: (modelId: string, body: Record<string, unknown>) =>
    api.put<SpecSaveResult>(`/equipment-models/${modelId}/specs`, body),
  remove: (modelId: string, definitionId: string) =>
    api.delete<void>(`/equipment-models/${modelId}/specs/${definitionId}`),
  /** 값이 어느 문서에서 나왔는지 대는 자리. 문서는 반입 스크립트가 등록한다. */
  sources: () => api.get<SpecSourcePage>('/spec-sources?limit=200'),
}
