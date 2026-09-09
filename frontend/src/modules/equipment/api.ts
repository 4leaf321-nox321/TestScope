/** 장비·역량 API. */

import { api } from '@/shared/api/client'
import type { components } from '@/shared/api/schema'

export type Equipment = components['schemas']['EquipmentOut']
export type Calibration = components['schemas']['CalibrationOut']
export type Capability = components['schemas']['CapabilityOut']
export type CapabilityLimit = components['schemas']['LimitOut']
type EquipmentPage = components['schemas']['Page_EquipmentOut_']

export type EquipmentSeries = components['schemas']['EquipmentSeriesOut']
export type SeriesRelation = components['schemas']['SeriesRelationOut']
type SeriesPage = components['schemas']['Page_EquipmentSeriesOut_']
export type EquipmentModel = components['schemas']['EquipmentModelOut']
export type ModelCapability = components['schemas']['ModelCapabilityOut']
export type ModelLimit = components['schemas']['ModelLimitOut']
type ModelPage = components['schemas']['Page_EquipmentModelOut_']

export const equipmentApi = {
  list: (params: {
    q?: string
    status?: string
    workspace?: string
    /** 이 기종의 장비만. **서버가 거른다** — 화면이 전체를 받아 거르면 상한을
     *  넘는 순간 나머지가 조용히 안 보인다. */
    modelId?: string
    limit?: number
  }) => {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.status) search.set('status', params.status)
    if (params.workspace) search.set('workspace', params.workspace)
    if (params.modelId) search.set('model_id', params.modelId)
    if (params.limit) search.set('limit', String(params.limit))
    const query = search.toString()
    return api.get<EquipmentPage>(`/equipment${query ? `?${query}` : ''}`)
  },
  read: (id: string) => api.get<Equipment>(`/equipment/${id}`),
  create: (body: Record<string, unknown>) => api.post<Equipment>('/equipment', body),
  update: (id: string, body: Record<string, unknown>) =>
    api.patch<Equipment>(`/equipment/${id}`, body),
  remove: (id: string) => api.delete<void>(`/equipment/${id}`),

  calibrations: (id: string) => api.get<Calibration[]>(`/equipment/${id}/calibrations`),
  addCalibration: (id: string, body: Record<string, unknown>) =>
    api.post<Calibration>(`/equipment/${id}/calibrations`, body),
}

export const capabilityApi = {
  forEquipment: (equipmentId: string) =>
    api.get<Capability[]>(`/capabilities?equipment_id=${equipmentId}`),
  create: (body: Record<string, unknown>) => api.post<Capability>('/capabilities', body),
  update: (id: string, body: Record<string, unknown>) =>
    api.patch<Capability>(`/capabilities/${id}`, body),
  remove: (id: string) => api.delete<void>(`/capabilities/${id}`),
  /** 조건 한 칸은 **덮어쓰기다** — 같은 조건이 둘이면 어느 쪽이 맞는지 알 수 없다. */
  putLimit: (capabilityId: string, body: Record<string, unknown>) =>
    api.put<CapabilityLimit>(`/capabilities/${capabilityId}/limits`, body),
  removeLimit: (capabilityId: string, limitId: string) =>
    api.delete<void>(`/capabilities/${capabilityId}/limits/${limitId}`),
}

/**
 * 장비 계열 — **제조사가 파는 계열.**
 *
 * 무슨 시험이 되나(역량), 어느 부속이 붙나(관계), 누가 만들었나가 여기 붙는다.
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

  addCapability: (seriesId: string, body: Record<string, unknown>) =>
    api.post<ModelCapability>(`/equipment-series/${seriesId}/capabilities`, body),
  removeCapability: (seriesId: string, capabilityId: string) =>
    api.delete<void>(`/equipment-series/${seriesId}/capabilities/${capabilityId}`),
  /** 조건 한 칸은 **덮어쓰기다** — 같은 조건이 둘이면 어느 쪽이 맞는지 알 수 없다. */
  putLimit: (seriesId: string, capabilityId: string, body: Record<string, unknown>) =>
    api.put<ModelLimit>(
      `/equipment-series/${seriesId}/capabilities/${capabilityId}/limits`,
      body,
    ),
  removeLimit: (seriesId: string, capabilityId: string, limitId: string) =>
    api.delete<void>(
      `/equipment-series/${seriesId}/capabilities/${capabilityId}/limits/${limitId}`,
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
 * 장비를 등록할 때 기종을 고르면 **계열의 역량이 그 개체로 복사되고, 조건은 이
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
  }) => {
    const search = new URLSearchParams()
    if (params.q) search.set('q', params.q)
    if (params.seriesId) search.set('series_id', params.seriesId)
    if (params.owned) search.set('owned', 'true')
    if (params.issue) search.set('issue', params.issue)
    if (params.limit) search.set('limit', String(params.limit))
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
  /** 한 칸을 넣거나 덮어쓴다. 응답의 `reflected` 는 역량에 반영된 수다. */
  put: (modelId: string, body: Record<string, unknown>) =>
    api.put<SpecSaveResult>(`/equipment-models/${modelId}/specs`, body),
  remove: (modelId: string, definitionId: string) =>
    api.delete<void>(`/equipment-models/${modelId}/specs/${definitionId}`),
  /** 값이 어느 문서에서 나왔는지 대는 자리. 문서는 반입 스크립트가 등록한다. */
  sources: () => api.get<SpecSourcePage>('/spec-sources?limit=200'),
}
