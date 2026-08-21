import { fetchAuditLogs } from '../services'

const h = vi.hoisted(() => ({ mockGet: vi.fn() }))

vi.mock('@/service/base', () => ({
  get: (...args: unknown[]) => h.mockGet(...args),
}))

describe('fetchAuditLogs', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.mockGet.mockResolvedValue({ data: [], total: 0, page: 1, page_size: 20 })
  })

  it('appends department_id to the query string', async () => {
    await fetchAuditLogs({ department_id: 'dept-1', page: 1, page_size: 20 })
    const [url] = h.mockGet.mock.calls[0]
    const search = new URL(url, 'http://localhost').searchParams
    expect(search.get('department_id')).toBe('dept-1')
    expect(search.get('page')).toBe('1')
    expect(search.get('page_size')).toBe('20')
  })

  it('omits department_id when not provided', async () => {
    await fetchAuditLogs({ log_type: 'qna', page: 1, page_size: 20 })
    const [url] = h.mockGet.mock.calls[0]
    const search = new URL(url, 'http://localhost').searchParams
    expect(search.has('department_id')).toBe(false)
    expect(search.get('log_type')).toBe('qna')
  })
})
