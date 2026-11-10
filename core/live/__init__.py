"""실시간 외부 조회 (feedback2.md §2). 시연 경로에서 네트워크를 쓰는 곳은 이 패키지뿐이다.

- juso.py: 도로명주소 검색 → PNU (실패하면 브이월드 검색으로 대체)
- vworld.py: 토지 정보(토지이용계획·토지특성·개별공시지가), 좌표(지오코더), 지도 클릭 필지(2D 데이터 연속지적도),
  참고 WMS 타일 프록시(브이월드 WMS에 CORS 헤더가 없음)
- 요청마다 타임아웃 4초, 재시도 1회. 실패해도 예외를 밖으로 던지지 않고 상태 값으로 알린다.
- 키는 환경변수에서만 읽는다(로컬은 .env). 키 값은 응답·로그·오류 문구에 넣지 않는다. LLM 호출 금지.
- 환경변수 PROPEDIA_LIVE=0이면 쓰지 않는다 (pytest·오프라인 평가).
"""
import os


class Live:
    """조회 로직에 넘기는 실시간 조회 묶음. fetch(url, params) -> dict 를 바꿔 끼우면 저장 응답으로 테스트할 수 있다."""

    def __init__(self, fetch=None):
        self.fetch = fetch

    def search(self, keyword: str) -> dict:
        from core.live import juso
        return juso.search(keyword, fetch=self.fetch)

    def get_land(self, pnu: str, jibun_address: str | None, location: dict | None = None) -> dict:
        from core.live import vworld
        return vworld.get_land(pnu, jibun_address, fetch=self.fetch, location=location)

    def parcel_at(self, lat: float, lon: float, allowed_bjd=None) -> dict:
        from core.live import vworld
        return vworld.parcel_at(lat, lon, fetch=self.fetch, allowed_bjd=allowed_bjd)

    def wms_tile(self, layer: str, z: int, x: int, y: int) -> dict:
        from core.live import vworld
        return vworld.wms_tile(layer, z, x, y)

    def parcel_by_pnu(self, pnu: str, allowed_bjd=None) -> dict:
        from core.live import vworld
        return vworld.parcel_by_pnu(pnu, fetch=self.fetch, allowed_bjd=allowed_bjd)


def enabled() -> bool:
    return os.environ.get("PROPEDIA_LIVE", "1") != "0"


def default() -> "Live | None":
    return Live() if enabled() else None
