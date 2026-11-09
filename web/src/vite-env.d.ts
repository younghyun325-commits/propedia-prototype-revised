/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 브라우저 배경지도(브이월드 WMTS) 키. 루트 .env에서 읽는다 (vite.config.ts envDir). 값을 로그에 남기지 않는다 */
  readonly VITE_VWORLD_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
