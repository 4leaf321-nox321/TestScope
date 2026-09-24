/**
 * 카탈로그 원문 — **사양을 채우려면 먼저 읽을 수 있어야 한다.**
 *
 * 기종 891 중 224 에는 사양값이 하나도 없다. 그중 205 는 원문(`raw_specs`)은 들어와 있는데,
 * 정의가 없는 키라 사양표에 못 세운 것이다. 사람이 그 원문을 보고 한 칸씩 옮겨 적으면
 * 검색이 답할 수 있게 되는데, 원문이 `{"capabilities":[{"range_min":-70,…}]}` 한 줄로
 * 덤프돼 있으면 아무도 안 읽는다 — 그래서 아무도 안 채웠다.
 *
 * ## MaterialTwin 은 모양이 정해져 있다
 *
 * 113 종은 MaterialTwin 스냅샷에서 왔고 `capabilities`(물성마다 기법·범위·정확도·근거)를
 * 갖는다. 그 표가 **옮겨 적을 값이 실제로 있는 곳**이다: 39종에 범위 단위, 35종에 상한,
 * 32종에 하한이 적혀 있다. 표로 세워야 「−70 ~ 180 °C」 가 눈에 들어온다.
 *
 * ## 어디서 왔는지 같이 말한다
 *
 * 옮겨 적는 사람은 원본을 열어 확인한다. 문서 이름과 쪽(`doc_path` · `source_detail`)이
 * 없으면 그 확인이 불가능하고, 확인 없이 적은 수치는 나중에 되짚을 수 없다.
 */

/** 값 하나를 사람이 읽는 글자로. 객체·배열은 부른 쪽이 펼치므로 여기 안 온다. */
function shownValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? '예' : '아니오'
  return String(value)
}

/** MaterialTwin 능력 한 줄이 말하는 범위. **옮겨 적을 값이 여기 있다.** */
function capabilityRange(row: Record<string, unknown>): string | null {
  const min = row.range_min
  const max = row.range_max
  const unit = typeof row.range_unit === 'string' ? row.range_unit : ''
  if (min === undefined && max === undefined) return null
  // 한쪽만 있는 것을 0 으로 채우지 않는다 — 하한이 0 인 것과 구별되지 않는다.
  const low = min === undefined || min === null ? '제한 없음' : `${String(min)}`
  const high = max === undefined || max === null ? '제한 없음' : `${String(max)}`
  return `${low} ~ ${high}${unit ? ` ${unit}` : ''}`
}

const CAPABILITY_LABEL: Record<string, string> = {
  property_key: '물성',
  technique: '기법',
  specimen: '시편',
  accuracy: '정확도',
  resolution: '분해능',
  standard: '규격',
  notes: '비고',
  source_detail: '근거(쪽)',
  mapping_confidence: '연결 확신도',
}

const MT_LABEL: Record<string, string> = {
  technique: '기법',
  description: '설명',
  notes: '비고',
  category: '분야',
  source_title: '출처 문서',
  doc_path: '문서 경로',
  snapshot: '스냅샷',
  instrument_id: 'MaterialTwin id',
}

/** MaterialTwin 블록 하나 — 머리말 + 능력 표. */
function MaterialTwinBlock({ data }: { data: Record<string, unknown> }) {
  const capabilities = Array.isArray(data.capabilities)
    ? (data.capabilities.filter((one) => typeof one === 'object' && one !== null) as Record<
        string,
        unknown
      >[])
    : []
  const head = Object.keys(MT_LABEL).filter(
    (key) => data[key] !== undefined && data[key] !== '',
  )

  return (
    <div className="space-y-3">
      <dl className="space-y-1 text-sm">
        {head.map((key) => (
          <div key={key} className="flex flex-wrap items-baseline gap-2">
            <dt className="text-muted-foreground w-28 shrink-0">{MT_LABEL[key]}</dt>
            <dd className="min-w-0 break-words">{shownValue(data[key])}</dd>
          </div>
        ))}
      </dl>

      {capabilities.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="text-muted-foreground border-b text-left">
                <th className="py-1 pr-3">물성 · 기법</th>
                {/* **이 열이 옮겨 적을 값이다.** 나머지는 그것을 믿을지 판단하는 근거다. */}
                <th className="py-1 pr-3">범위</th>
                <th className="py-1 pr-3">정확도 · 분해능</th>
                <th className="py-1 pr-3">규격 · 시편</th>
                <th className="py-1">비고 · 근거</th>
              </tr>
            </thead>
            <tbody>
              {capabilities.map((row, index) => (
                <tr key={index} className="border-b align-top">
                  <td className="py-1 pr-3">
                    <div className="font-mono">{shownValue(row.property_key)}</div>
                    {row.technique ? (
                      <div className="text-muted-foreground">{shownValue(row.technique)}</div>
                    ) : null}
                  </td>
                  <td className="py-1 pr-3 font-medium">{capabilityRange(row) ?? '—'}</td>
                  <td className="text-muted-foreground py-1 pr-3">
                    {[row.accuracy, row.resolution]
                      .filter((one) => one !== undefined && one !== null && one !== '')
                      .map((one) => String(one))
                      .join(' · ') || '—'}
                  </td>
                  <td className="text-muted-foreground py-1 pr-3">
                    {[row.standard, row.specimen]
                      .filter((one) => one !== undefined && one !== null && one !== '')
                      .map((one) => String(one))
                      .join(' · ') || '—'}
                  </td>
                  <td className="text-muted-foreground py-1">
                    {[row.notes, row.source_detail]
                      .filter((one) => one !== undefined && one !== null && one !== '')
                      .map((one) => String(one))
                      .join(' — ') || '—'}
                    {row.mapping_confidence === 'low' && (
                      // 기계가 물성을 이은 확신이 낮다. 그 표시가 없으면 옮겨 적는 사람이
                      // 그 줄을 다른 줄과 같은 무게로 읽는다.
                      <span className="ml-1 text-amber-700">
                        ({CAPABILITY_LABEL.mapping_confidence} 낮음)
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/** 그 밖의 출처 — 키가 제각각이라 표로 못 세운다. **줄로 편다.** */
function PlainBlock({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="space-y-1 text-sm">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="flex flex-wrap items-baseline gap-2">
          <dt className="text-muted-foreground w-56 shrink-0 font-mono text-xs">{key}</dt>
          <dd className="min-w-0 break-words">
            {typeof value === 'object' && value !== null ? (
              // 「{min: 0, max: 600}」 같은 것 — 한 줄 JSON 으로 두면 못 읽는다.
              <span className="font-mono text-xs">
                {Object.entries(value as Record<string, unknown>)
                  .map(([inner, one]) => `${inner}: ${shownValue(one)}`)
                  .join(' · ')}
              </span>
            ) : (
              shownValue(value)
            )}
          </dd>
        </div>
      ))}
    </dl>
  )
}

export function RawSpecs({
  raw,
  /** 사양표가 비었나. 비었으면 **펼친 채로 연다** — 채울 사람이 볼 것이 이것뿐이다. */
  empty,
}: {
  raw: Record<string, unknown>
  empty: boolean
}) {
  // 원문은 두 모양으로 온다: MaterialTwin 은 한 덩이(`materialtwin`)로 들어오고, 제조사
  // 카탈로그에서 온 것은 **평평한 키-값**이다(`capacity_kN` · `note` …). 둘을 같은 규칙으로
  // 그리면 평평한 쪽의 키가 「출처 이름」 으로 읽힌다.
  const twin = raw.materialtwin
  const rest = Object.fromEntries(
    Object.entries(raw).filter(
      ([key, value]) => key !== 'materialtwin' && value !== null && value !== undefined,
    ),
  )
  const count = Object.keys(rest).length + (twin ? 1 : 0)
  if (count === 0) return null

  return (
    <details className="rounded-md border p-4" open={empty}>
      <summary className="cursor-pointer text-base font-semibold">
        카탈로그 원문
        <span className="text-muted-foreground ml-2 text-sm font-normal">
          {twin ? 'MaterialTwin 스냅샷' : `${Object.keys(rest).length}개 항목`}
        </span>
      </summary>
      <p className="text-muted-foreground mt-2 text-sm">
        {empty ? (
          <>
            <strong>이 기종에는 사양이 하나도 안 적혀 있습니다.</strong> 아래 원문을 보고 위
            사양표에 한 칸씩 옮겨 적으면, 검색이 이 기종을 「조건 미상」 이 아니라 되는지 안
            되는지로 답합니다. 수치를 옮길 때는 <strong>출처 문서와 쪽</strong>을 함께
            고르십시오.
          </>
        ) : (
          <>
            제조사 카탈로그에 적힌 그대로입니다. <strong>위 사양표는 정의가 있는 칸만</strong>{' '}
            담고, 여기에는 정의가 없는 것까지 전부 있습니다 — 원본에 950종 넘는 키가 있고
            대부분이 한 카탈로그에만 나옵니다. 정의로 세우면 목록이 못 쓰게 되고, 안 세우면
            사라지므로 둘 다 합니다.
          </>
        )}
      </p>
      <div className="mt-3 space-y-4">
        {twin !== null && typeof twin === 'object' ? (
          <MaterialTwinBlock data={twin as Record<string, unknown>} />
        ) : null}
        {Object.keys(rest).length > 0 && <PlainBlock data={rest} />}
      </div>
    </details>
  )
}
