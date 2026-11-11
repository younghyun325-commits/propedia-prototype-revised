"""키 노출 점검 (P20). `.env` 값을 읽어 (값은 메모리에서만, 출력·저장하지 않음) 두 곳에서 변수 이름별 건수만 센다.

1. 지도 빌드 산출물 `public/map/**` — 브라우저에 그대로 내려가는 파일이며 P20부터 git에 커밋한다.
   배경지도 키도 빌드에 넣지 않고 실행 중 /api/v1/map/config로 받으므로 **모든 키가 0건**이어야 한다
   (P20 전에는 VITE_VWORLD_KEY만 허용했다).
2. git에 올라간 파일 전체(`git ls-files`) — 키 값은 0건이어야 한다.

변수 이름이 *_URL·*_DOMAIN인 값은 공개 주소라 비밀이 아니다(건수만 참고로 보여 주고 판정에서 뺀다).
같은 값을 가진 변수(예: VITE_VWORLD_KEY와 VWORLD_API_KEY)는 그 사실을 이름으로만 알린다.

사용: python -m pipeline.check_secrets   (실패하면 종료 코드 1)
"""
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "public" / "map"
MIN_LEN = 8          # 너무 짧은 값은 우연히 겹칠 수 있어 세지 않는다


def is_public(name: str) -> bool:
    return name.endswith("_URL") or name.endswith("_DOMAIN")


def count_in(files, values: dict[str, bytes]) -> dict[str, int]:
    out = {k: 0 for k in values}
    for f in files:
        try:
            b = f.read_bytes()
        except OSError:
            continue
        for k, v in values.items():
            out[k] += b.count(v)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    env = dotenv_values(ROOT / ".env")
    values = {k: v.encode("utf-8") for k, v in env.items() if v and len(v) >= MIN_LEN}
    empty = sorted(k for k, v in env.items() if not v)
    same = {}
    for k, v in values.items():
        same.setdefault(v, []).append(k)
    groups = [sorted(g) for g in same.values() if len(g) > 1]

    bundle = [p for p in BUNDLE.rglob("*") if p.is_file()]
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.split(b"\0")
    tracked = [ROOT / t.decode("utf-8") for t in tracked if t]
    in_bundle = count_in(bundle, values)
    in_git = count_in(tracked, values)

    ok = True
    print(f"점검: 빌드 산출물 {len(bundle)}개 파일, git 파일 {len(tracked)}개 (값은 출력하지 않음)")
    print("| 변수 이름 | 종류 | public/map 건수 | git 파일 건수 | 판정 |")
    print("|---|---|---:|---:|---|")
    for k in sorted(values):
        kind = "공개 주소" if is_public(k) else "키"
        if is_public(k):
            verdict = "참고"
        else:
            b_ok = in_bundle[k] == 0
            g_ok = in_git[k] == 0
            verdict = "통과" if b_ok and g_ok else "실패"
            ok &= b_ok and g_ok
        print(f"| {k} | {kind} | {in_bundle[k]} | {in_git[k]} | {verdict} |")
    for k in empty:
        print(f"| {k} | 값 없음 | - | - | - |")
    for g in groups:
        print(f"같은 값: {' = '.join(g)}")
    print("결과:", "통과" if ok else "실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
