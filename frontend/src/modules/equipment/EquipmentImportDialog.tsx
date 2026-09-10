/**
 * 보유 장비 **일괄 반입** — 엑셀에서 복사해 붙여넣는다.
 *
 * 카탈로그는 198계열·714기종까지 찼는데 대장은 4대였다. 장비를 넣는 길이 한 대씩
 * 뿐이라 수백 대를 가진 부서는 시작조차 못 했고, 대장이 비어 있으면 이 시스템은
 * **어떤 질문에도 못 답한다.**
 *
 * ## 왜 파일이 아니라 붙여넣기인가
 *
 * 문서 보안(DRM)이 걸린 환경에서는 **파일을 올릴 수 없다.** 서식을 내려받는 것은
 * 되는데 그 파일을 다시 고르는 것이 막힌다 — 실제로 그랬다. 붙여넣기는 DRM 이 막지
 * 못한다.
 *
 * 서식 내려받기는 남긴다. 어느 열에 무엇을 적는지는 그것으로 안다.
 *
 * ## 넣기 전에 보여 준다
 *
 * 붙여넣으면 먼저 미리보기를 부른다(`dry_run`). 300줄 중 틀린 12줄을 **넣기 전에**
 * 알아야 하고, 몇 번째 줄인지 말해 줘야 사람이 엑셀에서 그 줄을 찾는다.
 *
 * ## 전부 되거나 전부 안 되거나
 *
 * 문제가 하나라도 있으면 넣는 단추를 안 준다. 되는 것만 넣으면 사람은 고쳐 다시
 * 붙여넣다가 이미 들어간 줄에서 「이미 등록된 자산번호」 를 만나고, 그때 무엇을
 * 지워야 할지 모른다.
 *
 * ## 진행률(N/M) 대신 「무엇을 하는 중인지」 를 보인다
 *
 * 「지금 1500대째」 를 보여 주려면 서버가 넣는 중에 중간 보고를 해야 하는데, 그러려면
 * 쪽을 나눠 커밋해야 한다 — 그리고 그것이 바로 **반쯤 들어간 대장**이다. 한 트랜잭션을
 * 지키는 한 그 숫자는 확정된 것이 아니고, 전부 되돌아가는 순간 **거짓말이 된다.**
 *
 * 그래서 보이는 것은 셋이다: 지금 무엇을 하는 중인가 · 몇 대를 넣는 중인가 ·
 * 얼마나 걸릴 것인가. 「읽는 중」 과 「넣는 중」 을 한 문구로 두면 안 된다 — 실제로
 * 그랬고, 넣는 10초 동안 화면은 계속 「읽는 중」 이라고 말하고 있었다.
 */

import { useEffect, useState } from 'react'
import { Download, Loader2, Upload } from 'lucide-react'

import { ApiError } from '@/shared/api/client'
import { ErrorNotice } from '@/shared/components/ErrorNotice'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { equipmentApi } from '@/modules/equipment/api'
import type { EquipmentImportResult } from '@/modules/equipment/api'

/** 문제 줄을 몇 개까지 펼쳐 보이나. 나머지는 수로 접는다 — 200줄이 틀렸을 때
 *  전부 그리면 사람이 첫 줄도 못 읽는다. */
const SHOWN = 30

/** 한 대를 넣는 데 드는 시간(ms). **실측이다** — 500대에 2.5초였다.
 *
 *  기종을 이은 줄은 계열의 시험 항목과 조건까지 복사하므로 더 든다. 넉넉히 잡는다:
 *  덜 걸리는 것은 반갑지만, 더 걸리면 사람은 멈춘 줄 안다. */
const MS_PER_UNIT = 6

/** 몇 초쯤 걸리는지. **짧으면 아예 말하지 않는다** — 「1초쯤 걸립니다」 는 아무
 *  도움이 안 되면서 읽을 것만 늘린다. */
function spent(count: number): string {
  const seconds = Math.round((count * MS_PER_UNIT) / 1000)
  return seconds >= 3 ? ` (${seconds}초쯤 걸립니다)` : ''
}

export function EquipmentImportDialog({
  open,
  onClose,
  onDone,
}: {
  open: boolean
  onClose: () => void
  onDone: () => void
}) {
  const [text, setText] = useState('')
  const [preview, setPreview] = useState<EquipmentImportResult | null>(null)
  /** 지금 무엇을 하는 중인가. **「읽는 중」 과 「넣는 중」 은 다른 말이다** —
   *  한 낱말로 뭉치면 넣는 10초 동안 화면이 「읽는 중」 이라고 거짓말한다. */
  const [phase, setPhase] = useState<'idle' | 'looking' | 'putting'>('idle')
  const busy = phase !== 'idle'
  const [error, setError] = useState<ApiError | null>(null)
  const [done, setDone] = useState<number | null>(null)

  // **붙여넣으면 알아서 확인한다.** 「확인」 단추를 따로 두면 그것을 안 누른 채
  // 「넣기」 를 찾는 사람이 생기고, 그때 화면은 아무 말도 안 하는 것처럼 보인다.
  // 글자마다 부르지 않는다 — 300줄을 붙여넣는 동안 조회가 줄줄이 나간다.
  useEffect(() => {
    const body = text.trim()
    if (!body) {
      setPreview(null)
      setError(null)
      setPhase('idle')
      return
    }
    setPhase('looking')
    const timer = setTimeout(() => {
      equipmentApi
        .importPaste(text, true)
        .then((result) => {
          setPreview(result)
          setError(null)
        })
        .catch((thrown: ApiError) => {
          setPreview(null)
          setError(thrown)
        })
        .finally(() => setPhase('idle'))
    }, 400)
    return () => clearTimeout(timer)
  }, [text])

  async function commit() {
    setPhase('putting')
    setError(null)
    try {
      // **같은 글자를 다시 보낸다.** 서버가 미리보기 결과를 들고 있지 않아서,
      // 그 사이 남이 같은 자산번호를 넣었어도 여기서 다시 걸린다.
      const result = await equipmentApi.importPaste(text, false)
      if (result.created > 0) {
        setDone(result.created)
        setText('')
        setPreview(null)
        onDone()
      } else {
        setPreview(result)
      }
    } catch (thrown) {
      setError(thrown as ApiError)
    } finally {
      setPhase('idle')
    }
  }

  const bad = (preview?.rows ?? []).filter((one) => one.problems.length > 0)
  const unlinked = (preview?.rows ?? []).filter(
    (one) => one.problems.length === 0 && !one.model_linked,
  ).length

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setText('')
          setPreview(null)
          setError(null)
          setDone(null)
          onClose()
        }
      }}
    >
      <DialogContent className="max-h-[85vh] max-w-3xl">
        <DialogHeader>
          <DialogTitle>장비 일괄 반입</DialogTitle>
          <DialogDescription>
            엑셀에서 <strong>머리글 줄까지 함께</strong> 복사해 아래에 붙여넣으세요. 넣기 전에
            줄마다 확인합니다.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => void equipmentApi.importTemplate()}
            >
              <Download className="size-4" />
              서식 내려받기
            </Button>
            <span className="text-muted-foreground text-xs">
              어느 열에 무엇을 적는지는 서식으로 봅니다. 채운 뒤 그 범위를 복사하세요.
            </span>
          </div>

          <textarea
            value={text}
            onChange={(event) => {
              setText(event.target.value)
              setDone(null)
            }}
            rows={8}
            spellCheck={false}
            placeholder={
              '자산번호\t장비명\t보유부서\t거점\t설치위치\t…\n' +
              'UTM-001\t3동 만능기\t재료시험팀\t본사\t3동 201호\t…'
            }
            className="border-input bg-background w-full rounded-md border p-2 font-mono text-xs"
          />

          <p className="text-muted-foreground text-xs">
            부서·거점·장비유형·기종은 <strong>이름으로</strong> 적습니다. 기준정보에 없는
            거점·분류는 여기서 만들어지지 않습니다 — 먼저 기준정보에 등록하세요.
          </p>

          <ErrorNotice error={error} />

          {done !== null && (
            <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm">
              <strong>{done}대</strong>를 등록했습니다.
            </div>
          )}

          {phase === 'looking' && <p className="text-muted-foreground text-sm">읽는 중…</p>}

          {phase === 'putting' && (
            // **몇 대를 넣는 중인지 말한다.** 「지금 1500대째」 는 못 말한다 —
            // 한 트랜잭션이라 그 수는 아직 확정된 것이 아니고, 전부 되돌아가는
            // 순간 거짓말이 된다.
            <div className="flex items-center gap-2 rounded-md border p-3 text-sm">
              <Loader2 className="size-4 animate-spin" />
              <span>
                <strong>{preview?.ready ?? 0}대</strong>를 넣는 중입니다
                {spent(preview?.ready ?? 0)}. <strong>창을 닫지 마세요</strong> — 도중에 끊기면
                아무것도 안 들어갑니다.
              </span>
            </div>
          )}

          {preview && (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-4 text-sm">
                <span>
                  모두 <strong>{preview.total}</strong>줄
                </span>
                <span className="text-emerald-700">
                  넣을 수 있음 <strong>{preview.ready}</strong>
                </span>
                {preview.problems > 0 && (
                  <span className="text-amber-700">
                    문제 <strong>{preview.problems}</strong>
                  </span>
                )}
              </div>

              {preview.problems > 0 ? (
                <>
                  {/* **전부 되거나 전부 안 되거나.** 그 사실을 단추가 없는 이유로
                      먼저 말해 준다 — 안 말하면 사람은 단추를 찾는다. */}
                  <p className="text-sm">
                    문제가 있는 줄이 있어 <strong>아무것도 넣지 않았습니다.</strong> 엑셀에서
                    아래 줄을 고쳐 다시 붙여넣으세요. 줄 번호는 엑셀에서 보이는 번호와
                    같습니다.
                  </p>
                  <ul className="space-y-2">
                    {bad.slice(0, SHOWN).map((row) => (
                      <li key={row.line} className="rounded-md border p-2 text-sm">
                        <span className="font-mono text-xs">{row.line}번째 줄</span>
                        {row.asset_no && (
                          <span className="ml-2 font-medium">{row.asset_no}</span>
                        )}
                        <ul className="text-amber-700 mt-1 list-disc pl-5 text-xs">
                          {row.problems.map((one) => (
                            <li key={one}>{one}</li>
                          ))}
                        </ul>
                      </li>
                    ))}
                  </ul>
                  {bad.length > SHOWN && (
                    <p className="text-muted-foreground text-xs">
                      외 {bad.length - SHOWN}줄이 더 있습니다.
                    </p>
                  )}
                </>
              ) : (
                <div className="bg-muted/50 space-y-1 rounded-md border p-3 text-sm">
                  <p>
                    <strong>{preview.ready}대</strong>를 넣을 수 있습니다
                    {spent(preview.ready)}.
                  </p>
                  {unlinked > 0 && (
                    // 막지 않는다 — 자작 장비나 카탈로그에 없는 것이 실제로 있다.
                    // 다만 그 장비들이 **검색에 안 걸린다**는 사실은 넣기 전에 안다.
                    <p className="text-amber-700">
                      그중 <strong>{unlinked}대</strong>는 기종이 안 이어졌습니다. 시험 항목이
                      0 건이 되고, <strong>0 건이면 검색에 걸리지 않습니다</strong> — 나중에
                      장비마다 시험 항목을 채워야 합니다.
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          {/* **넣는 중에는 못 닫는다.** 닫아도 요청은 계속 가는데 화면은 결과를
              못 보고, 그러면 사람은 들어갔는지 아닌지를 모르는 채 남는다. */}
          <Button variant="outline" onClick={onClose} disabled={phase === 'putting'}>
            닫기
          </Button>
          <Button
            onClick={() => void commit()}
            disabled={busy || !preview || preview.problems > 0 || preview.ready === 0}
          >
            {phase === 'putting' ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Upload className="size-4" />
            )}
            {phase === 'putting'
              ? '넣는 중…'
              : preview && preview.problems === 0
                ? `${preview.ready}대 넣기`
                : '넣기'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
