/**
 * 카탈로그 원문 — **읽을 수 있어야 채운다.**
 *
 * 기종 891 중 224 에 사양값이 없고, 그중 205 는 원문은 들어와 있다. 그 원문이 한 줄 JSON
 * 덤프로 접혀 있으면 아무도 안 읽고, 그래서 아무도 안 채웠다.
 *
 * 여기서 지키는 것 — 사양이 비면 펼친 채로 열리고 채우라고 말한다 · MaterialTwin 능력은
 * 표로 서서 옮겨 적을 범위가 보인다 · 한쪽만 있는 범위를 0 으로 채우지 않는다.
 */

import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { RawSpecs } from '@/modules/equipment/RawSpecs'

const materialtwin = {
  materialtwin: {
    technique: '시차주사열량계(DSC)',
    description: '열유속형 DSC.',
    notes: '옵션 냉각기 기준.',
    source_title: 'Vendor Guide 2026',
    doc_path: 'metrology_catalogs/thermal/guide.pdf',
    capabilities: [
      {
        property_key: 'thermal.glass_transition',
        technique: 'DSC',
        range_min: -70,
        range_max: 180,
        range_unit: '°C',
        accuracy: '±0.1 °C',
        source_detail: 'p.12 Specifications',
        mapping_confidence: 'high',
      },
      {
        property_key: 'thermal.melting_point',
        range_max: 600,
        range_unit: '°C',
        mapping_confidence: 'low',
        notes: '상한만 인쇄됨',
      },
    ],
  },
}

describe('카탈로그 원문', () => {
  it('사양이 비면 펼친 채로 열리고, 채우라고 말한다', () => {
    const { container } = render(<RawSpecs raw={materialtwin} empty />)
    expect(container.querySelector('details')?.open).toBe(true)
    expect(screen.getByText(/사양이 하나도 안 적혀 있습니다/)).toBeTruthy()
  })

  it('사양이 있으면 접어 둔다 — 본문은 위 사양표다', () => {
    const { container } = render(<RawSpecs raw={materialtwin} empty={false} />)
    expect(container.querySelector('details')?.open).toBe(false)
  })

  it('MaterialTwin 능력이 표로 서고 범위가 보인다', () => {
    render(<RawSpecs raw={materialtwin} empty />)
    // **옮겨 적을 값**이 한 칸에 모여 있어야 눈에 들어온다.
    expect(screen.getByText('-70 ~ 180 °C')).toBeTruthy()
    // 한쪽만 있는 범위를 0 으로 채우지 않는다 — 하한이 0 인 것과 구별되지 않는다.
    expect(screen.getByText('제한 없음 ~ 600 °C')).toBeTruthy()
    // 원본을 열어 확인할 수 있게 문서와 쪽을 남긴다.
    expect(screen.getByText('metrology_catalogs/thermal/guide.pdf')).toBeTruthy()
    expect(screen.getByText(/p.12 Specifications/)).toBeTruthy()
    // 기계가 물성을 이은 확신이 낮으면 그 줄을 다른 줄과 같은 무게로 읽으면 안 된다.
    expect(screen.getByText(/연결 확신도 낮음/)).toBeTruthy()
  })

  it('MaterialTwin 이 아닌 원문은 키-값 줄로 편다', () => {
    render(
      <RawSpecs
        raw={{ capacity_kN: 600, stroke: { min: 0, max: 1200 }, note: '기본 그립 포함' }}
        empty
      />,
    )
    expect(screen.getByText('capacity_kN')).toBeTruthy()
    // 「{min:0,max:1200}」 한 줄 JSON 으로 두면 못 읽는다.
    expect(screen.getByText('min: 0 · max: 1200')).toBeTruthy()
  })

  it('원문이 없으면 아무것도 그리지 않는다', () => {
    const { container } = render(<RawSpecs raw={{}} empty />)
    expect(container.firstChild).toBeNull()
  })
})
