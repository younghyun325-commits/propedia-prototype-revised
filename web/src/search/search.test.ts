import { describe, expect, it } from 'vitest'
import type { MapProject } from '../api/map'
import { addressQuery, normQuery, pushRecent, searchProjects } from './search'

const base = {
  feature_id: '', aliases: [], project_type_label: '', position_label: '', stage_seq: 1, stage_total: 13,
  stage_title: '', status_badge: '', deadline: null, representative_pnu: null, bbox: null,
  parcels: { included: 0, possible: 1, likely: 0 }, parcels_unverified: 1, unverified: true, hover_line: '',
}
const P: MapProject[] = [
  { ...base, id: 1, name: '압구정아파트지구 특별계획구역6-1 재건축 정비구역', short_name: '한양7차아파트 재건축',
    aliases: ['한양7차아파트 재건축'], representative_jibun: '강남구 압구정동 527번지 일대' },
  { ...base, id: 2, name: '대청마을 북측구역 소규모주택정비 관리지역', short_name: '대청마을 북측 모아타운',
    aliases: ['일원동 619번지 일원 모아타운'], representative_jibun: '강남구 일원동 619번지 일원' },
  { ...base, id: 3, name: '가상 한양 테스트', short_name: '한양 테스트', representative_jibun: null },
]

describe('사업 검색 (명령 팔레트)', () => {
  it('정규화: 공백·번지·서울특별시 제거', () => {
    expect(normQuery(' 서울특별시 강남구 일원동 619번지 ')).toBe('강남구일원동619')
  })
  it("'한양': 이름 앞부분 일치가 먼저, 포함은 다음", () => {
    const hits = searchProjects(P, '한양')
    expect(hits.map((h) => h.project.id)).toEqual([1, 3])
    expect(hits.map((h) => h.rank)).toEqual([0, 0])
    expect(searchProjects(P, '7차').map((h) => [h.project.id, h.rank])).toEqual([[1, 1]])
  })
  it("'일원동 619': 별칭·대표 지번 부분 일치", () => {
    const hits = searchProjects(P, '일원동 619')
    expect(hits.map((h) => [h.project.id, h.field])).toEqual([[2, 'alias']])
    expect(searchProjects(P, '압구정동 527').map((h) => [h.project.id, h.field])).toEqual([[1, 'jibun']])
  })
  it('압구정동 528은 사업 대표 지번이 아니므로 사업 결과 없음 (주소 그룹에서 찾음)', () => {
    expect(searchProjects(P, '압구정동 528')).toEqual([])
  })
  it('1글자는 결과 없음', () => {
    expect(searchProjects(P, '한')).toEqual([])
  })
  it("주소 검색어: 구 없이 동·번지면 '강남구'를 붙이고, 그 밖에는 그대로", () => {
    expect(addressQuery('압구정동 528')).toBe('강남구 압구정동 528')
    expect(addressQuery('일원동 산 12')).toBe('강남구 일원동 산 12')
    expect(addressQuery('강남구 일원동 619')).toBe('강남구 일원동 619')
    expect(addressQuery('서초구 방배동 1')).toBe('서초구 방배동 1')
    expect(addressQuery('서울특별시 강남구 테헤란로 427')).toBe('서울특별시 강남구 테헤란로 427')
    expect(addressQuery('테헤란로 427')).toBe('테헤란로 427')
  })
  it('최근 검색: 앞으로, 중복 제거, 5개', () => {
    let r: string[] = []
    for (const q of ['a', 'b', 'c', 'd', 'e', 'f', 'c']) r = pushRecent(r, q)
    expect(r).toEqual(['c', 'f', 'e', 'd', 'b'])
  })
})
