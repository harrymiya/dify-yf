import { fireEvent, render, screen } from '@testing-library/react'
import UsageStatisticsPage from '../index'

type QueryArgs = {
  queryKey: unknown
  queryFn?: () => unknown
}

const h = vi.hoisted(() => {
  return {
    queryResults: {} as Record<string, Record<string, unknown>>,
    mockFetchKB: vi.fn(),
    mockFetchTrend: vi.fn(),
    mockFetchInterfaces: vi.fn(),
  }
})

vi.mock('../services', () => ({
  fetchKBCallStats: (...a: unknown[]) => h.mockFetchKB(...a),
  fetchKBTrend: (...a: unknown[]) => h.mockFetchTrend(...a),
  fetchInterfaceCalls: (...a: unknown[]) => h.mockFetchInterfaces(...a),
}))

vi.mock('@/service/datasets', () => ({
  fetchDatasets: vi.fn(() =>
    Promise.resolve({ data: { data: [], has_more: false, limit: 100, page: 1, total: 0 } }),
  ),
}))

vi.mock('@tanstack/react-query', () => {
  const useQuery = ({ queryKey, queryFn }: QueryArgs) => {
    const key = Array.isArray(queryKey) ? queryKey.join(',') : String(queryKey)
    if (typeof queryFn === 'function') void queryFn()
    return { isLoading: false, isError: false, refetch: vi.fn(), ...(h.queryResults[key] ?? {}) }
  }
  return { useQuery }
})

const base = {
  kb: {
    days: 30,
    total_calls: 12,
    data: [
      { dataset_id: 'ds-1', calls: 10 },
      { dataset_id: 'ds-2', calls: 2 },
    ],
  },
  trend: {
    days: 30,
    bucket: 'day',
    data: [
      { bucket: '2024-01-01', calls: 5 },
      { bucket: '2024-01-02', calls: 7 },
    ],
  },
  iface: { days: 30, total_calls: 20, data: { qna: 12, download: 8 } },
  kbUser: {
    days: 30,
    dimension: 'user',
    total_calls: 12,
    data: [
      { id: 'account-1', name: 'Alice', email: 'alice@example.com', is_virtual: false, calls: 8 },
      { id: '__external_api__', name: '外部调用 / API', email: null, is_virtual: true, calls: 4 },
    ],
  },
  kbDept: {
    days: 30,
    dimension: 'department',
    total_calls: 12,
    grouped_calls: 20,
    aggregation: 'include_descendants',
    data: [
      { id: 'dept-root', name: 'Engineering', parent_id: null, is_virtual: false, calls: 12 },
      { id: '__unassigned__', name: '未分配', parent_id: null, is_virtual: true, calls: 8 },
    ],
  },
  ifaceUser: {
    days: 30,
    dimension: 'user',
    total_calls: 20,
    data: [
      { id: 'account-2', name: 'Bob', email: 'bob@example.com', is_virtual: false, calls: 20 },
    ],
  },
  ifaceDept: {
    days: 30,
    dimension: 'department',
    total_calls: 20,
    grouped_calls: 30,
    aggregation: 'include_descendants',
    data: [
      { id: 'dept-root', name: 'Engineering', parent_id: null, is_virtual: false, calls: 20 },
      { id: '__unassigned__', name: '未分配', parent_id: null, is_virtual: true, calls: 10 },
    ],
  },
}

describe('UsageStatisticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.queryResults = {
      'usage-statistics,kb-calls,30,dataset': { data: base.kb },
      'usage-statistics,kb-calls,30,user': { data: base.kbUser },
      'usage-statistics,kb-calls,30,department': { data: base.kbDept },
      'usage-statistics,kb-trend,30': { data: base.trend },
      'usage-statistics,interfaces,30,type': { data: base.iface },
      'usage-statistics,interfaces,30,user': { data: base.ifaceUser },
      'usage-statistics,interfaces,30,department': { data: base.ifaceDept },
      'usage-statistics,kb-calls,7,dataset': { data: base.kb },
      'usage-statistics,kb-calls,7,user': { data: base.kbUser },
      'usage-statistics,kb-calls,7,department': { data: base.kbDept },
      'usage-statistics,kb-trend,7': { data: base.trend },
      'usage-statistics,interfaces,7,type': { data: base.iface },
      'usage-statistics,interfaces,7,user': { data: base.ifaceUser },
      'usage-statistics,interfaces,7,department': { data: base.ifaceDept },
      'usage-statistics,datasets': {
        data: {
          data: [
            { id: 'ds-1', name: 'Demo KB' },
            { id: 'ds-2', name: 'Second KB' },
          ],
        },
      },
    }
  })

  it('renders the top trend card and all six grid cards', () => {
    render(<UsageStatisticsPage />)
    expect(screen.getByText('usageStatistics.kbTrendTitle')).toBeInTheDocument()
    expect(screen.getByText('usageStatistics.kbTopByDatasetTitle')).toBeInTheDocument()
    expect(screen.getByText('usageStatistics.kbTopByUserTitle')).toBeInTheDocument()
    expect(screen.getByText('usageStatistics.kbTopByDepartmentTitle')).toBeInTheDocument()
    expect(screen.getByText('usageStatistics.interfaceTitle')).toBeInTheDocument()
    expect(screen.getByText('usageStatistics.interfaceByUserTitle')).toBeInTheDocument()
    expect(screen.getByText('usageStatistics.interfaceByDepartmentTitle')).toBeInTheDocument()
  })

  it('queries all dimensions for KB and interface calls plus trend', () => {
    render(<UsageStatisticsPage />)
    expect(h.mockFetchKB).toHaveBeenCalledWith(30, 20, 'dataset')
    expect(h.mockFetchKB).toHaveBeenCalledWith(30, 20, 'user')
    expect(h.mockFetchKB).toHaveBeenCalledWith(30, 20, 'department')
    expect(h.mockFetchInterfaces).toHaveBeenCalledWith(30, 'type', 20)
    expect(h.mockFetchInterfaces).toHaveBeenCalledWith(30, 'user', 20)
    expect(h.mockFetchInterfaces).toHaveBeenCalledWith(30, 'department', 20)
    expect(h.mockFetchTrend).toHaveBeenCalledWith(30)
  })

  it('renders dataset, user, and department rows together', () => {
    render(<UsageStatisticsPage />)
    expect(screen.getByText('Demo KB')).toBeInTheDocument()
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('外部调用 / API')).toBeInTheDocument()
    expect(screen.getAllByText('Engineering').length).toBeGreaterThan(0)
  })

  it('renders loading state', () => {
    h.queryResults = {
      'usage-statistics,kb-calls,30,dataset': { isLoading: true },
      'usage-statistics,kb-calls,30,user': { isLoading: true },
      'usage-statistics,kb-calls,30,department': { isLoading: true },
      'usage-statistics,kb-trend,30': { isLoading: true },
      'usage-statistics,interfaces,30,type': { isLoading: true },
      'usage-statistics,interfaces,30,user': { isLoading: true },
      'usage-statistics,interfaces,30,department': { isLoading: true },
    }
    render(<UsageStatisticsPage />)
    expect(screen.getAllByText('usageStatistics.loading').length).toBeGreaterThan(0)
  })

  it('switches the day range and re-etchs all queries', () => {
    render(<UsageStatisticsPage />)
    fireEvent.click(screen.getByTestId('days-7'))
    expect(h.mockFetchKB).toHaveBeenCalledWith(7, 20, 'dataset')
    expect(h.mockFetchKB).toHaveBeenCalledWith(7, 20, 'user')
    expect(h.mockFetchKB).toHaveBeenCalledWith(7, 20, 'department')
    expect(h.mockFetchTrend).toHaveBeenCalledWith(7)
    expect(h.mockFetchInterfaces).toHaveBeenCalledWith(7, 'type', 20)
  })
})
