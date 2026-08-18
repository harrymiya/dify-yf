import { fireEvent, render, screen } from '@testing-library/react'
import UsageStatisticsPage from '../index'

const h = vi.hoisted(() => {
  return {
    queryResult: {} as Record<string, unknown>,
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
  const useQuery = () => ({ isLoading: false, isError: false, refetch: vi.fn(), ...h.queryResult })
  return { useQuery }
})

const base = {
  kb: { days: 30, total_calls: 12, data: [{ dataset_id: 'ds-1', calls: 10 }, { dataset_id: 'ds-2', calls: 2 }] },
  trend: { days: 30, bucket: 'day', data: [{ bucket: '2024-01-01', calls: 5 }, { bucket: '2024-01-02', calls: 7 }] },
  iface: { days: 30, total_calls: 20, data: { qna: 12, download: 8 } },
}

describe('UsageStatisticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.queryResult = {}
  })

  it('renders the three statistics cards', () => {
    h.queryResult = { data: { ...base.kb } }
    render(<UsageStatisticsPage />)
    expect(screen.getByText('Knowledge base call volume (Top)')).toBeInTheDocument()
    expect(screen.getByText('Call trend')).toBeInTheDocument()
    expect(screen.getByText('Interface / event calls')).toBeInTheDocument()
  })

  it('renders kb call rows', () => {
    h.queryResult = { data: { ...base.kb } }
    render(<UsageStatisticsPage />)
    expect(screen.getByText('ds-1')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
  })

  it('switches the day range', () => {
    h.queryResult = { data: { ...base.kb } }
    render(<UsageStatisticsPage />)
    fireEvent.click(screen.getByTestId('days-7'))
    // state updated; assert the component still renders without crashing
    expect(screen.getByText('ds-1')).toBeInTheDocument()
  })
})
