/**
 * AI 도구 등록 안내 — **토큰이 없어도 형식을 보여 주고, 있으면 채워 준다.**
 *
 * 무는 것 넷:
 *   토큰 전에도 명령이 보인다      「먼저 발급하세요」 만 띄우면 무엇을 받는지 모른다
 *   발급하면 그 값이 들어간다      평문은 다시 못 보므로 그 자리에서 완성돼야 한다
 *   도구마다 다른 것을 준다        Desktop 은 명령이 아니라 JSON 항목이다
 *   주소를 고칠 사람에게 말한다    421 은 토큰 문제처럼 보이지 않는다
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { McpSetup, TOKEN_PLACEHOLDER } from '@/shared/components/McpSetup'

describe('McpSetup', () => {
  it('토큰이 없으면 자리표시자를 넣은 형식을 보여 준다', () => {
    render(<McpSetup />)
    const command = screen.getByText(/claude mcp add/)
    expect(command.textContent).toContain(TOKEN_PLACEHOLDER)
    // 포트까지 보여야 한다 — 8022 는 백엔드가 아니라 MCP 서버다.
    expect(command.textContent).toContain(':8022/mcp')
  })

  it('발급된 토큰이 명령에 채워진다', () => {
    render(<McpSetup token="tsc_pat_abc123" />)
    const command = screen.getByText(/claude mcp add/)
    expect(command.textContent).toContain('Authorization: Bearer tsc_pat_abc123')
    expect(command.textContent).not.toContain(TOKEN_PLACEHOLDER)
  })

  it('Claude Desktop 은 명령이 아니라 설정 항목을 준다', async () => {
    render(<McpSetup token="tsc_pat_abc123" />)
    await userEvent.click(screen.getByRole('tab', { name: 'Claude Desktop' }))

    const entry = await screen.findByText(/"testscope"/)
    // stdio 만 받는 도구라 브리지를 거친다.
    expect(entry.textContent).toContain('mcp-remote')
    // **헤더 값은 env 로 넣는다** — 공백(`Bearer …`)이 args 에서 잘리는 것을 막는다.
    expect(entry.textContent).toContain('Authorization:${AUTH}')
    expect(entry.textContent).toContain('"AUTH": "Bearer tsc_pat_abc123"')
    // 바깥 래퍼까지 주면 이미 있는 설정을 덮어쓴다.
    expect(entry.textContent).not.toContain('"mcpServers"')
  })

  it('Codex 는 TOML 로 준다', async () => {
    render(<McpSetup token="tsc_pat_abc123" />)
    await userEvent.click(screen.getByRole('tab', { name: 'Codex CLI' }))

    const entry = await screen.findByText(/\[mcp_servers\.testscope\]/)
    expect(entry.textContent).toContain('AUTH = "Bearer tsc_pat_abc123"')
    // TOML 에서도 치환은 mcp-remote 가 한다 — `${AUTH}` 가 글자로 남아야 한다.
    expect(entry.textContent).toContain('Authorization:${AUTH}')
  })

  it('허용 Host 가 글자로 견준다는 것을 미리 말한다', () => {
    render(<McpSetup token="tsc_pat_abc123" />)
    // 주소를 고친 사람이 받는 421 은 토큰 문제처럼 보이지 않는다 — 그래서 여기 적는다.
    expect(screen.getByText(/MCP_ALLOWED_HOSTS/)).toBeInTheDocument()
    expect(screen.getByText(/421/)).toBeInTheDocument()
  })

  it('개발 서버 주소를 글자로 적지 않는다', () => {
    // **릴리스 포장이 번들에서 이 글자를 찾으면 떨어진다**(`scripts/ci/package_deploy.ps1`)
    // — 프론트가 API 절대주소를 굽지 않는다는 약속을 지키는 검사다. 설명하려고 예로 적은
    // 글자도 똑같이 걸린다.
    //
    // 그 검사는 **태그가 붙은 뒤**에 도는 포장 단계에 있다. 0.45.0 이 거기서 떨어져
    // 태그만 남고 배포판이 안 나왔다(2026-10-02). 그래서 여기로 당겨 온다 — 같은 고장을
    // `npm test` 에서 몇 초 만에 본다.
    const { container } = render(<McpSetup token="tsc_pat_abc123" />)
    expect(container.textContent ?? '').not.toContain('127.0.0.1:80')
  })
})
