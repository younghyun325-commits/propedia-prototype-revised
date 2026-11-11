#!/bin/sh
# 복제본(propedia-prototype-revised) 보호 훅 설치. clone 직후 한 번 실행한다 (Windows는 Git Bash).
#   sh scripts/install_hooks.sh
# .git/hooks/pre-push 를 만든다 (기존 파일은 pre-push.bak 으로 남긴다).
set -eu

top=$(git rev-parse --show-toplevel)
hooks_dir=$(git rev-parse --git-path hooks)
case "$hooks_dir" in
  /*|[A-Za-z]:*) ;;
  *) hooks_dir="$top/$hooks_dir" ;;
esac
mkdir -p "$hooks_dir"
target="$hooks_dir/pre-push"

if [ -f "$target" ] && ! grep -q "propedia-revised-guard" "$target"; then
  cp "$target" "$target.bak"
  echo "기존 pre-push 를 pre-push.bak 으로 옮겼습니다"
fi

cat > "$target" <<'HOOK'
#!/bin/sh
# propedia-revised-guard — scripts/install_hooks.sh 가 만든 훅. 직접 고치지 말고 그 스크립트를 고친다.
# 인자: $1 = 원격 이름(또는 URL), $2 = push URL. 표준입력: <local ref> <local sha> <remote ref> <remote sha>
remote_name="$1"
remote_url="$2"
ORIGINAL_REPO="propedia-prototype"
CLONE_REPO="propedia-prototype-revised"
ZERO=0000000000000000000000000000000000000000

fail() {
  echo "pre-push 거부: $1" >&2
  exit 1
}

# 1) upstream 원격으로는 push 하지 않는다 (원본 저장소, fetch 전용)
if [ "$remote_name" = "upstream" ]; then
  fail "upstream(원본 저장소)으로 push 금지"
fi

# 2) URL 에서 저장소 이름만 뽑아 '전체 일치'로 비교한다 (부분 문자열 검사 금지:
#    복제본 이름 안에 원본 이름이 들어 있다)
repo_name=${remote_url%/}
repo_name=${repo_name##*/}
repo_name=${repo_name##*:}
repo_name=${repo_name%.git}

if [ "$repo_name" = "$ORIGINAL_REPO" ]; then
  fail "원본 저장소로 push 금지 ($ORIGINAL_REPO)"
fi
if [ "$repo_name" != "$CLONE_REPO" ]; then
  fail "push 대상 저장소 이름이 $CLONE_REPO 가 아님 (받은 이름: $repo_name)"
fi

# 3) 커밋 작성자 이메일 검사 + 4) (이전 훅에서 이어 온 검사) main 브랜치 직접 push 금지
#    main 반영은 사람이 결정한다. 꼭 필요할 때만 PROPEDIA_ALLOW_MAIN_PUSH=1 로 이 검사만 건너뛴다.
bad=""
while read -r local_ref local_sha remote_ref remote_sha; do
  [ -z "${local_ref:-}" ] && continue
  [ "$local_sha" = "$ZERO" ] && continue
  if [ "$remote_ref" = "refs/heads/main" ] && [ "${PROPEDIA_ALLOW_MAIN_PUSH:-}" != "1" ]; then
    fail "main 브랜치 직접 push 금지 (사람이 결정한 뒤 PROPEDIA_ALLOW_MAIN_PUSH=1)"
  fi
  if [ "$remote_sha" = "$ZERO" ]; then
    range=$(git rev-list "$local_sha" --not --remotes="$remote_name" 2>/dev/null) || range=$(git rev-list "$local_sha" --not --remotes 2>/dev/null)
  else
    range=$(git rev-list "$remote_sha..$local_sha" 2>/dev/null) || range=$(git rev-list "$local_sha" --not --remotes 2>/dev/null)
  fi
  for c in $range; do
    email=$(git log -1 --format='%ae' "$c")
    case "$email" in
      *@users.noreply.github.com) ;;
      *) bad="$bad
$(git log -1 --format='%h %ae %s' "$c")" ;;
    esac
  done
done

if [ -n "$bad" ]; then
  echo "pre-push 거부: 작성자 이메일이 noreply 가 아닌 커밋이 있습니다:$bad" >&2
  echo "git config --local user.email 을 확인하고 커밋 작성자를 고친 뒤 다시 push 하세요" >&2
  exit 1
fi
exit 0
HOOK

chmod +x "$target"
echo "설치함: $target"
