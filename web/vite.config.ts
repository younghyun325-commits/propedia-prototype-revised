/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// docs/map/PLAN.md '기술 스택·구조' 설정. 개발 서버 포트만 3000으로 고정한다:
// 브이월드 개발 키의 서비스 URL이 localhost:3000이라 다른 포트로 넘어가면 안 된다 (strictPort).
export default defineConfig({
  base: '/map/',
  // 루트 .env를 읽는다. 브라우저에는 VITE_ 접두어 변수(VITE_VWORLD_KEY)만 들어간다
  envDir: '..',
  plugins: [react(), tailwindcss()],
  build: { outDir: '../public/map', emptyOutDir: true },
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/pages': 'http://127.0.0.1:8000',
      '/data': 'http://127.0.0.1:8000',
    },
  },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
