PRAGMA foreign_keys = ON;

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
-- keys: build_at(ISO), as_of(가장 최근 문서 날짜), schema_version('1'), eval_report(JSON), coverage_note

CREATE TABLE sources (
  id TEXT PRIMARY KEY,                 -- 'gangnam-gubo' | 'seoul-urban-portal' | 'seoul-citybuild'
  name TEXT NOT NULL,
  layer TEXT NOT NULL,                 -- 'city' | 'gu'
  url TEXT
);

CREATE TABLE documents (
  id INTEGER PRIMARY KEY,
  doc_id TEXT NOT NULL UNIQUE,         -- 'D1'..'D4'
  source_id TEXT NOT NULL REFERENCES sources(id),
  title TEXT NOT NULL,
  short_title TEXT NOT NULL,
  doc_kind TEXT NOT NULL,              -- 'gongram' | 'plan'
  issuer TEXT,
  gosi_no TEXT,
  published_at TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  supersedes_id INTEGER REFERENCES documents(id),
  source_url TEXT,
  source_note TEXT,
  original_path TEXT NOT NULL,         -- '../data/...' 상대경로
  excerpt_path TEXT NOT NULL,          -- 'data_raw/D1.pdf'
  page_ranges TEXT NOT NULL,           -- '1-21' 또는 '12-14,29-31,113-151'
  content_hash TEXT NOT NULL,          -- 원본 파일 sha256
  excerpt_hash TEXT NOT NULL,          -- 발췌본 sha256
  ingest_step INTEGER NOT NULL,        -- 투입 순서 (D4=1, D3=2, D2=3, D1=4)
  text_status TEXT NOT NULL            -- 'ok' | 'partial' | 'failed'
);

CREATE TABLE pages (
  document_id INTEGER NOT NULL REFERENCES documents(id),
  pdf_page INTEGER NOT NULL,
  page_label TEXT,
  method TEXT NOT NULL,                -- 'text' | 'vision-claude' | 'image-only'
  text TEXT NOT NULL DEFAULT '',
  char_count INTEGER NOT NULL,
  image_url TEXT NOT NULL,             -- '/pages/D1/p001.jpg'
  selected INTEGER NOT NULL DEFAULT 1, -- 추출 대상이면 1 (D1 18~21, D2 미선택 쪽은 0)
  PRIMARY KEY (document_id, pdf_page)
);

CREATE TABLE extractions (
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES documents(id),
  extractor_version TEXT NOT NULL,     -- 'claude-code-v1'
  extracted_at TEXT NOT NULL,
  payload TEXT NOT NULL,               -- extractions/Dn.json 전체
  evidence_ok_count INTEGER NOT NULL,
  evidence_total INTEGER NOT NULL
);

CREATE TABLE extracted_fields (        -- D1의 필드 단위 추출값 (평가·문서 DB 화면용)
  document_id INTEGER NOT NULL REFERENCES documents(id),
  field TEXT NOT NULL,
  value TEXT,                          -- JSON 값 문자열
  evidence TEXT,
  pdf_page INTEGER,
  confidence REAL NOT NULL,
  evidence_ok INTEGER NOT NULL,
  PRIMARY KEY (document_id, field)
);

CREATE TABLE applicability_rules (     -- 4개 층에 나가는 '항목'
  id INTEGER PRIMARY KEY,
  item_key TEXT NOT NULL UNIQUE,       -- 'D3-07'
  document_id INTEGER NOT NULL REFERENCES documents(id),
  item_type TEXT NOT NULL,             -- 'policy' | 'plan' | 'notice' | 'stat'
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  scope_type TEXT NOT NULL,            -- 'SIDO' | 'SGG' | 'SAENGHWAL' | 'BJD' | 'PARCEL'
  scope_ref TEXT NOT NULL,             -- JSON 배열: '["11"]', '["11680"]', '["압구정·청담"]', '["1168011000"]'
  scope_note TEXT,
  pdf_page INTEGER NOT NULL,
  evidence TEXT NOT NULL,
  evidence_ok INTEGER NOT NULL,
  effective_from TEXT,
  confidence REAL NOT NULL,
  needs_review INTEGER NOT NULL
);

CREATE TABLE doc_locations (
  document_id INTEGER NOT NULL REFERENCES documents(id),
  pnu TEXT, bjd_code TEXT, sgg_code TEXT,
  method TEXT NOT NULL,                -- 'representative' | 'jibun_text' | 'manual'
  jibun_text TEXT, pdf_page INTEGER, evidence TEXT, confidence REAL
);

CREATE TABLE projects (
  id INTEGER PRIMARY KEY,
  project_key TEXT NOT NULL UNIQUE,    -- 'apgujeong-6-1-hanyang7'
  name TEXT NOT NULL,
  aliases TEXT NOT NULL DEFAULT '[]',
  project_type TEXT NOT NULL,          -- 'rebuild'
  track TEXT NOT NULL DEFAULT 'unknown', -- 'general' | 'shintong' | 'public' | 'unknown'
  sgg_code TEXT NOT NULL,
  bjd_code TEXT NOT NULL,
  sub_stage_code TEXT NOT NULL,        -- 'RB02'
  stage_as_of TEXT NOT NULL,           -- 단계 근거 문서 날짜
  stage_source_doc_id INTEGER REFERENCES documents(id),
  stage_rule TEXT,                     -- 적용된 stage_rules id
  area_m2 REAL,
  location_text TEXT,                  -- '강남구 압구정동 527번지 일대'
  land_use TEXT,                       -- 문서 기재 용도지역
  land_use_page INTEGER,
  lat REAL, lon REAL, coord_source TEXT
);

CREATE TABLE project_parcels (
  project_id INTEGER NOT NULL REFERENCES projects(id),
  pnu TEXT NOT NULL,
  basis TEXT NOT NULL,                 -- 'representative_only' | 'jibun_table' | 'manual_review'
  verified INTEGER NOT NULL DEFAULT 0,
  source_doc_id INTEGER REFERENCES documents(id),
  pdf_page INTEGER, evidence TEXT,
  PRIMARY KEY (project_id, pnu)
);

CREATE TABLE project_documents (
  project_id INTEGER NOT NULL, document_id INTEGER NOT NULL,
  role TEXT NOT NULL,                  -- 'stage_basis' | 'related'
  PRIMARY KEY (project_id, document_id)
);

CREATE TABLE project_stage_history (
  project_id INTEGER NOT NULL, sub_stage_code TEXT NOT NULL,
  entered_at TEXT, source_doc_id INTEGER, basis TEXT NOT NULL,   -- 'gosi'
  pdf_page INTEGER, evidence TEXT
);

CREATE TABLE related_history (          -- 사업 카드의 '관련 고시 이력' (단계가 아님)
  project_id INTEGER NOT NULL, label TEXT NOT NULL, date TEXT, gosi_no TEXT,
  source_doc_id INTEGER, pdf_page INTEGER, evidence TEXT
);

CREATE TABLE deadlines (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id),
  kind TEXT NOT NULL,                  -- 'public_review'
  title TEXT NOT NULL,                 -- '정비계획(안) 주민공람'
  starts_on TEXT, due_on TEXT NOT NULL,
  how_to_submit TEXT, places TEXT,     -- places: JSON 배열
  source_doc_id INTEGER, pdf_page INTEGER, evidence TEXT
);

CREATE TABLE stage_templates (
  project_type TEXT NOT NULL, seq INTEGER NOT NULL, sub_stage_code TEXT NOT NULL,
  common_stage TEXT, title TEXT NOT NULL, issuer TEXT,
  what_happens TEXT, owner_actions TEXT, legal_basis TEXT,
  source TEXT NOT NULL, reviewed_by TEXT, reviewed_at TEXT,
  PRIMARY KEY (project_type, seq)
);

CREATE TABLE change_events (
  id INTEGER PRIMARY KEY,
  step INTEGER NOT NULL,               -- 투입 순서 (1~4)
  project_id INTEGER,
  event_type TEXT NOT NULL,            -- 'new_project' | 'stage_change' | 'deadline_added' | 'doc_attached'
  before TEXT, after TEXT,             -- JSON
  source_doc_id INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE review_queue (
  id INTEGER PRIMARY KEY,
  item_type TEXT NOT NULL,             -- 'parcel_inclusion' | 'evidence_mismatch' | 'vision_item' | 'scope_uncertain' | 'field_low_confidence' | 'stage_uncertain'
  ref_table TEXT NOT NULL,             -- 'project_parcels' | 'applicability_rules' | 'extracted_fields' | 'projects'
  ref_key TEXT NOT NULL,               -- 예: '1:1168011000105270000', 'D2-05', 'D1:area_m2'
  title TEXT NOT NULL,                 -- 검수 목록에 보일 제목
  reason TEXT NOT NULL,
  proposed TEXT,                       -- JSON: 현재 값/제안 값
  document_id INTEGER, pdf_page INTEGER
);

CREATE TABLE demo_addresses (
  addr_id TEXT PRIMARY KEY,            -- 'A1'..'A10'
  label TEXT NOT NULL,                 -- 화면 칩에 보일 이름
  input_text TEXT NOT NULL,
  road_address TEXT, jibun_address TEXT,
  pnu TEXT, bjd_code TEXT, sgg_code TEXT, building_name TEXT,
  lat REAL, lon REAL, coord_source TEXT,
  aliases TEXT NOT NULL DEFAULT '[]',  -- 같은 곳을 가리키는 다른 입력들
  in_scope INTEGER NOT NULL
);

CREATE TABLE bjd_codes (
  bjd_code TEXT PRIMARY KEY, sgg_code TEXT NOT NULL, dong_name TEXT NOT NULL,
  saenghwal TEXT,                      -- 지역생활권 이름 ('압구정·청담')
  code_verified INTEGER NOT NULL,      -- 도로명주소 API admCd로 확인했으면 1
  saenghwal_verified INTEGER NOT NULL  -- D2로 확인했으면 1
);
