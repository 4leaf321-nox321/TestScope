import path from 'node:path'
import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import pkg from './package.json' with { type: 'json' }

const root = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // **이 빌드가 몇 번인지 굽는다.** 서버가 다른 버전이면 화면이 그것을 말할 수
  // 있어야 한다 — 개발과 운영이 같은 포트를 쓰는 동안, 프론트가 옛 서버에 붙어
  // 있어도 아무 데도 티가 안 난다.
  define: { __APP_VERSION__: JSON.stringify(`v${pkg.version}`) },
  resolve: {
    alias: { '@': path.resolve(root, 'src') },
  },
  server: {
    port: 5200,
    strictPort: true,
    // 개발 중에만 필요하다. 배포에서는 백엔드 한 프로세스가 SPA 까지 서빙하므로
    // 프론트는 항상 같은 출처의 /api 를 부른다 — API 주소를 빌드에 굽지 않는다.
    proxy: {
      // localhost 가 아니라 127.0.0.1 — 백엔드는 0.0.0.0(IPv4)에 바인딩하는데
      // 윈도우의 localhost 는 ::1 로 먼저 풀려 연결이 거부된다.
      //
      // **8021 이다. 운영이 8020 을 쓴다.** 둘이 같으면 개발 백엔드를 내린 순간
      // 이 프록시가 운영 설치본에 그대로 붙고, 화면은 그 사실을 말하지 않는다.
      '/api': { target: 'http://127.0.0.1:8021', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 700,
  },
})
