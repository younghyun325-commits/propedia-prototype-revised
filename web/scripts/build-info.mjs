// 지도 빌드 결과(public/map)가 어떤 web/ 소스로 만들어졌는지 남긴다 (P20).
// public/map은 git에 커밋하므로(Vercel은 빌드 중에 만든 public/ 파일을 서빙하지 않음), web/를 고치고 빌드를 잊으면
// tests/test_public_map_fresh.py가 이 해시로 알려 준다. 같은 규칙을 Python 쪽에서도 쓴다 — 둘을 함께 고칠 것.
// 규칙: 아래 SOURCES의 파일을 web/ 기준 posix 경로로 정렬, 파일마다 "경로\n" + sha256(내용) + "\n"을 이어 sha256.
//       내용은 NUL 바이트가 없으면 텍스트로 보고 CRLF를 LF로 바꾼다 (Windows 체크아웃 줄끝과 무관하게).
//       *.test.ts는 빌드에 들어가지 않으므로 뺀다. 시각은 넣지 않는다 (같은 소스 → 같은 파일).
import { createHash } from 'node:crypto'
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const WEB = fileURLToPath(new URL('..', import.meta.url))
const OUT = join(WEB, '..', 'public', 'map', 'build-info.json')
const DIRS = ['src', 'public', 'scripts']
const FILES = ['index.html', 'package.json', 'package-lock.json', 'vite.config.ts', 'tsconfig.json', 'tsconfig.app.json', 'tsconfig.node.json']

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name)
    return statSync(p).isDirectory() ? walk(p) : [p]
  })
}

const sha = (b) => createHash('sha256').update(b).digest('hex')

function normalized(buf) {
  if (buf.includes(0)) return buf
  return Buffer.from(buf.toString('latin1').replace(/\r\n/g, '\n'), 'latin1')
}

const paths = [...DIRS.flatMap((d) => walk(join(WEB, d))), ...FILES.map((f) => join(WEB, f))]
  .map((p) => relative(WEB, p).split(sep).join('/'))
  .filter((p) => !p.endsWith('.test.ts'))
  .sort()
const h = createHash('sha256')
for (const p of paths) h.update(`${p}\n${sha(normalized(readFileSync(join(WEB, p))))}\n`)
const info = { source_sha256: h.digest('hex'), source_files: paths.length, rule: 'web/scripts/build-info.mjs' }
writeFileSync(OUT, JSON.stringify(info, null, 2) + '\n')
console.log(`build-info: ${paths.length}개 소스 → ${info.source_sha256.slice(0, 16)}`)
