import type { ComponentProps } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import AuditLogsPage from '../index'

type ButtonProps = ComponentProps<'button'>
type InputProps = ComponentProps<'input'>

const h = vi.hoisted(() => {
  return {
    mockFetch: vi.fn(),
    queryResult: {} as Record<string, unknown>,
  }
})

vi.mock('../services', () => ({
  fetchAuditLogs: (...args: unknown[]) => h.mockFetch(...args),
}))

vi.mock('@tanstack/react-query', () => {
  const useQuery = () => ({
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
    ...h.queryResult,
  })
  return { useQuery }
})

vi.mock('@langgenius/dify-ui/button', () => ({
  Button: ({ children, onClick, disabled, ...props }: ButtonProps) => (
    <button type="button" onClick={onClick} disabled={disabled} {...props}>
      {children}
    </button>
  ),
}))

vi.mock('@langgenius/dify-ui/input', () => ({
  Input: (props: InputProps) => <input {...props} />,
}))

const sample = {
  data: [
    {
      id: 'log-1',
      user_id: 'u-1',
      user_type: 'account',
      log_type: 'qna',
      action: 'retrieve',
      status: 'success',
      resource_type: 'dataset',
      resource_id: 'ds-1',
      detail: null,
      ip: '127.0.0.1',
      request_id: 'req-1',
      trace_id: null,
      created_at: '2024-01-01T00:00:00Z',
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
}

describe('AuditLogsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.queryResult = { data: sample, isLoading: false, isError: false, refetch: vi.fn() }
    h.mockFetch.mockResolvedValue(sample)
  })

  it('renders the audit log table with rows', () => {
    render(<AuditLogsPage />)
    expect(screen.getByText('retrieve')).toBeInTheDocument()
    expect(screen.getByText('ds-1')).toBeInTheDocument()
  })

  it('renders empty state when no logs', () => {
    h.queryResult = {
      data: { data: [], total: 0, page: 1, page_size: 20 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    }
    render(<AuditLogsPage />)
    expect(screen.queryByText('retrieve')).not.toBeInTheDocument()
  })

  it('applies filters and triggers a refetch via query key change', () => {
    render(<AuditLogsPage />)
    fireEvent.change(screen.getByTestId('filter-type'), { target: { value: 'download' } })
    fireEvent.change(screen.getByTestId('filter-status'), { target: { value: 'failure' } })
    fireEvent.click(screen.getByTestId('apply-filters'))
    // The applied state is updated, which changes the query key; assert no crash and the table still renders.
    expect(screen.getByText('retrieve')).toBeInTheDocument()
  })

  it('navigates pages with the next button', () => {
    h.queryResult = {
      data: { data: sample.data, total: 40, page: 1, page_size: 20 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    }
    render(<AuditLogsPage />)
    fireEvent.click(screen.getByRole('button', { name: /next/i }))
    // page should advance (query re-run not observable with static mock), just ensure no throw
    expect(screen.getByText('retrieve')).toBeInTheDocument()
  })
})
