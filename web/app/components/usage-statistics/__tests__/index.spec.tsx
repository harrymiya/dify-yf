import { fireEvent, render, screen } from '@testing-library/react'
import UsageStatisticsPage from '../index'

type QueryArgs = {
  queryKey: unknown
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

vi.mock('@tanstack/react-query', () => {
  const useQuery = ({ queryKey }: QueryArgs) => {
    const key = Array.isArray(queryKey) ? queryKey.join(',') : String(queryKey)
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
}

describe('UsageStatisticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.queryResults = {
      'usage-statistics,kb-calls,30': { data: base.kb },
      'usage-statistics,kb-trend,30': { data: base.trend },
      'usage-statistics,interfaces,30': { data: base.iface },
      'usage-statistics,kb-calls,7': { data: base.kb },
      'usage-statistics,kb-trend,7': { data: base.trend },
      'usage-statistics,interfaces,7': { data: base.iface },
      'usage-statistics,datasets': {
        data: { data: [{ id: 'ds-1', name: 'Demo KB' }, { id: 'ds-2', name: 'Second KB' }] },
      },
    }
  })

  it('renders the three statistics cards', () => {
    render(<UsageStatisticsPage />)
    expect(screen.getByText('usageStatistics.kbTopTitle')).toBeInTheDocument()
    expect(screen.getByText('usageStatistics.kbTrendTitle')).toBeInTheDocument()
    expect(screen.getByText('usageStatistics.interfaceTitle')).toBeInTheDocument()
  })

  it('renders kb call rows', () => {
    render(<UsageStatisticsPage />)
    expect(screen.getByText('Demo KB')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
  })

  it('switches the day range', () => {
    render(<UsageStatisticsPage />)
    fireEvent.click(screen.getByTestId('days-7'))
    // state updated; assert the component still renders without crashing
    expect(screen.getByText('Demo KB')).toBeInTheDocument()
  })
})
