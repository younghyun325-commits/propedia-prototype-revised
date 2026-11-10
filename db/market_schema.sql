-- db/market.db (docs/map/PLAN.md P17 4단계). 빌드: python -m pipeline.build_market_db. 화면은 읽기 전용(core/db.connect_market_ro).
-- 개인 정보 성격 필드(buyerGbn·slerGbn·estateAgentSggNm)는 저장하지 않는다.
PRAGMA foreign_keys = ON;

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- keys: schema_version, fetched_on(수집일), trade_from·trade_to(계약일 범위), source_note, area_bands(JSON),
--       raw_count(원자료 건수), raw_cancelled, list_total(단지 목록 수), m22·m23(JSON), basis_info_check

CREATE TABLE apt_complexes (
  id TEXT PRIMARY KEY,                 -- 'apt:11680-218' (= 지도 레이어 id)
  apt_seq TEXT,                        -- 실거래 단지 일련번호 (없으면 NULL, id는 'apt:pnu:{PNU}')
  name TEXT NOT NULL,                  -- 가장 최근 거래의 단지명
  aliases TEXT NOT NULL DEFAULT '[]',  -- JSON: 다른 이름들
  pnus TEXT NOT NULL DEFAULT '[]',     -- JSON: 실거래 신고 지번의 PNU
  bjd_code TEXT,
  lat REAL, lon REAL,                  -- 필지 경계 합집합의 대표점 (지오코더 아님). 못 찾으면 NULL
  build_year INTEGER,                  -- 실거래 신고 건축년도
  kapt_code TEXT, households INTEGER, buildings INTEGER, approval_date TEXT,   -- 기본 정보 (덧붙임)
  road_addr TEXT, jibun_addr TEXT,
  basis_info_status TEXT NOT NULL DEFAULT 'pending',   -- 'pending' | 'linked' | 'not_in_list'
  as_of TEXT                           -- 수집일
);

CREATE TABLE apt_trades (
  id INTEGER PRIMARY KEY,
  complex_id TEXT REFERENCES apt_complexes(id),        -- 못 이으면 NULL
  apt_seq TEXT, pnu TEXT, apt_name_raw TEXT, umd_name TEXT, jibun TEXT, apt_dong TEXT,
  exclusive_area_m2 REAL, area_band TEXT,
  contract_date TEXT NOT NULL, amount_10k_won INTEGER NOT NULL, floor INTEGER, build_year INTEGER,
  deal_type TEXT,                      -- dealingGbn (중개거래·직거래)
  land_leasehold TEXT,                 -- landLeaseholdGbn
  is_cancelled INTEGER NOT NULL DEFAULT 0,
  cancelled_date TEXT, registered_date TEXT,
  link_method TEXT,                    -- 'apt_seq' | 'pnu' | 'name' | NULL
  raw_hash TEXT NOT NULL UNIQUE
);
CREATE INDEX idx_trades_complex ON apt_trades(complex_id, contract_date);

CREATE TABLE apt_trade_monthly (       -- 해제 거래 제외
  complex_id TEXT NOT NULL, area_band TEXT NOT NULL, ym TEXT NOT NULL,
  median_amount REAL NOT NULL, count INTEGER NOT NULL,
  PRIMARY KEY (complex_id, area_band, ym)
);
