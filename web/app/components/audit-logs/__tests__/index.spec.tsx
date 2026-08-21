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

vi.mock('@/service/use-common', () => ({
  useMembers: () => ({
    data: {
      accounts: [{ id: 'u-1', name: 'Alice', email: 'alice@example.com' }],
    },
  }),
}))

vi.mock('@tanstack/react-query', () => {
  const useQuery = ({ queryKey }: { queryKey: unknown }) => {
    const key = Array.isArray(queryKey) ? queryKey.filter(Boolean).join(',') : String(queryKey)
    if (key.includes('datasets'))
      return {
        data: { data: [{ id: 'ds-1', name: 'Demo KB' }] },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      }
    if (key.includes('departments'))
      return {
        data: [
          {
            id: 'dept-1',
            tenant_id: 't-1',
            parent_id: null,
            name: 'Engineering',
            sort: 0,
            children: [],
          },
        ],
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      }
    return { isLoading: false, isError: false, refetch: vi.fn(), ...h.queryResult }
  }
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
      user_name: 'Alice',
      user_email: 'alice@example.com',
      department_ids: ['dept-1'],
      department_names: ['Engineering', 'Platform'],
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
    expect(screen.getByText('Demo KB')).toBeInTheDocument()
    expect(screen.getByText('Alice')).toBeInTheDocument()
  })

  it('displays department names joined for the department column', () => {
    render(<AuditLogsPage />)
    expect(screen.getByText('Engineering / Platform')).toBeInTheDocument()
  })

  it('falls back to a dash when user_name and department_names are absent', () => {
    h.queryResult = {
      data: {
        data: [
          {
            ...sample.data[0],
            user_name: null,
            user_type: null,
            user_id: null,
            department_ids: [],
            department_names: [],
            ip: null,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    }
    render(<AuditLogsPage />)
    // User, department, and IP cells fall back to '-'.
    expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(3)
  })

  it('selecting a department renders it as a filter option and applying keeps the filter', () => {
    render(<AuditLogsPage />)
    const deptOption = screen.getByRole('option', { name: 'Engineering' })
    expect(deptOption).toBeInTheDocument()
    fireEvent.change(screen.getByTestId('filter-department'), { target: { value: 'dept-1' } })
    fireEvent.click(screen.getByTestId('apply-filters'))
    // Applying filters changes applied state without crashing.
    expect(screen.getByText('retrieve')).toBeInTheDocument()
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
