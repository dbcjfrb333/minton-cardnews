#!/usr/bin/env python3
"""카드뉴스 폴더 -> 인스타 캐러셀 게시 (Instagram Graph API, LLM 토큰 사용 없음).

사용법:
  python3 post_instagram.py queue/2026-10-31 --dry-run     # 확인만 (게시 안 함)
  python3 post_instagram.py queue/2026-10-31               # 실제 게시

폴더 안에 *.png (파일명 순서대로 슬라이드)와 *_caption.txt 가 있어야 해요.

환경변수 (GitHub Secrets / 로컬 환경변수로 설정, 코드나 채팅에 적지 않기):
  IG_USER_ID       인스타 프로페셔널 계정의 IG user id
  IG_ACCESS_TOKEN  장기 액세스 토큰
  IMAGE_BASE_URL   이미지가 올라간 공개 주소의 폴더까지 (끝에 / 없이)
                   예) https://raw.githubusercontent.com/<계정>/<저장소>/main
  IG_API_HOST      (선택) 기본 graph.facebook.com (EAA...로 시작하는 토큰)
                   IGAA...로 시작하는 토큰이면 graph.instagram.com
  IG_API_VERSION   (선택) 기본 v26.0 — Meta 문서의 현재 버전으로 맞춰 주세요
"""
import os, sys, time, glob, json, urllib.parse, urllib.request, urllib.error

HOST = os.environ.get("IG_API_HOST", "graph.facebook.com")
VER = os.environ.get("IG_API_VERSION", "v26.0")


def call(method, path, params):
    url = f"https://{HOST}/{VER}/{path}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url if method == "POST" else url + "?" + data.decode(),
                                 data=data if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"API 오류 {e.code}: {e.read().decode('utf-8', 'replace')}")


def wait_ready(container_id, token, tries=30):
    for _ in range(tries):
        st = call("GET", container_id, {"fields": "status_code", "access_token": token})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            sys.exit(f"컨테이너 {container_id} 처리 실패: {code}")
        time.sleep(3)
    sys.exit(f"컨테이너 {container_id} 처리 시간 초과")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) != 1:
        sys.exit(__doc__)
    folder = args[0].rstrip("/")
    pngs = sorted(glob.glob(os.path.join(folder, "*.png")))
    caps = glob.glob(os.path.join(folder, "*_caption.txt"))
    if not (2 <= len(pngs) <= 10):
        sys.exit(f"이미지는 2~10장이어야 해요 (지금 {len(pngs)}장)")
    if not caps:
        sys.exit("캡션 txt가 없어요")
    caption = open(caps[0], encoding="utf-8").read().strip()
    if len(caption) > 2200:
        sys.exit(f"캡션이 너무 길어요 ({len(caption)}자, 최대 2200자)")

    base = os.environ.get("IMAGE_BASE_URL", "https://example.com").rstrip("/")
    urls = [f"{base}/{folder}/{os.path.basename(p)}" for p in pngs]
    print(f"{len(urls)}장, 캡션 {len(caption)}자")
    for u in urls:
        print(" ", u)
    if dry:
        print("\n[dry-run] 게시하지 않았어요.\n--- 캡션 ---\n" + caption)
        return

    uid, token = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]
    # 이미지 주소가 실제로 열리는지 먼저 확인
    for u in urls:
        try:
            urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=30)
        except Exception as e:
            sys.exit(f"이미지 주소가 열리지 않아요: {u} ({e})")

    children = []
    for u in urls:
        r = call("POST", f"{uid}/media", {"image_url": u, "is_carousel_item": "true", "access_token": token})
        children.append(r["id"])
    for c in children:
        wait_ready(c, token)
    car = call("POST", f"{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(children),
                                         "caption": caption, "access_token": token})
    wait_ready(car["id"], token)
    pub = call("POST", f"{uid}/media_publish", {"creation_id": car["id"], "access_token": token})
    print("게시 완료! media id:", pub.get("id"))


if __name__ == "__main__":
    main()
