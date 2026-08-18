import { fireEvent, render, screen } from '@testing-library/react'
import GrantPanel from '../grant-panel'

const h = vi.hoisted(() => {
  return {
    mockGet: vi.fn(),
    mockCreateGrant: vi.fn(),
    mockFetchGrants: vi.fn(),
    mockFetchDepartmentTree: vi.fn(),
    mockInvalidate: vi.fn(),
    queryStore: {} as Record<string, unknown>,
  }
})

vi.mock('@/service/base', () => ({
  get: (...args: unknown[]) => h.mockGet(...args),
}))

vi.mock('@/service/use-common', () => ({
  useMembers: () => ({
    data: {
      accounts: [
        { id: 'acct-1', name: 'Alice', email: 'alice@example.com' },
        { id: 'acct-2', name: 'Bob', email: 'bob@example.com' },
      ],
    },
  }),
}))

vi.mock('../services', () => ({
  createGrant: (...args: unknown[]) => h.mockCreateGrant(...args),
  fetchGrants: (...args: unknown[]) => h.mockFetchGrants(...args),
  fetchDepartmentTree: (...args: unknown[]) => h.mockFetchDepartmentTree(...args),
  revokeGrant: vi.fn(),
}))

vi.mock('@tanstack/react-query', () => {
  const useQuery = vi.fn(({ queryKey, enabled }: any) => {
    const key = Array.isArray(queryKey) ? queryKey.filter(Boolean).join(',') : String(queryKey)
    return {
      ...(h.queryStore[key] ?? { data: undefined }),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
      enabled,
    }
  })
  return {
    useQuery,
    useQueryClient: () => ({ invalidateQueries: h.mockInvalidate }),
  }
})

vi.mock('@langgenius/dify-ui/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@langgenius/dify-ui/button', () => ({
  Button: ({ children, onClick, disabled }: any) => (
    <button type="button" onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}))

describe('GrantPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.queryStore = {
      'dataset-permission,datasets': { data: { data: [{ id: 'ds-1', name: 'Knowledge One' }] } },
      'dataset-permission,departments': {
        data: [{ id: 'dep-1', parent_id: null, name: 'Engineering', children: [] }],
      },
      'dataset-permission,grants,dataset,ds-1': {
        data: [
          {
            id: 'g-1',
            subject_type: 'account',
            subject_id: 'acct-1',
            action: 'DatasetPreview',
            resource_id: 'ds-1',
            resource_type: 'dataset',
            created_at: null,
          },
        ],
      },
    }
    h.mockFetchGrants.mockResolvedValue({ data: [] })
    h.mockFetchDepartmentTree.mockResolvedValue([])
    h.mockGet.mockResolvedValue({ data: [{ id: 'ds-1', name: 'Knowledge One' }] })
    h.mockCreateGrant.mockResolvedValue({ created: 1, result: 'success' })
  })

  it('renders resource, subject and grant controls', () => {
    render(<GrantPanel />)
    expect(screen.getByTestId('resource-type-select')).toBeInTheDocument()
    expect(screen.getByTestId('resource-select')).toBeInTheDocument()
    expect(screen.getByTestId('subject-type-select')).toBeInTheDocument()
    expect(screen.getByTestId('subject-select')).toBeInTheDocument()
  })

  it('enables grant submission when resource, subject and actions are chosen', () => {
    render(<GrantPanel />)

    fireEvent.change(screen.getByTestId('resource-select'), { target: { value: 'ds-1' } })
    fireEvent.change(screen.getByTestId('subject-select'), { target: { value: 'acct-1' } })
    fireEvent.click(screen.getByTestId('action-DatasetPreview'))

    expect(screen.getByRole('button', { name: /grant/i })).not.toBeDisabled()
  })

  it('creates a grant with the selected subject, resource and actions', () => {
    render(<GrantPanel />)

    fireEvent.change(screen.getByTestId('resource-select'), { target: { value: 'ds-1' } })
    fireEvent.change(screen.getByTestId('subject-type-select'), { target: { value: 'department' } })
    fireEvent.change(screen.getByTestId('subject-select'), { target: { value: 'dep-1' } })
    fireEvent.click(screen.getByTestId('action-DatasetEdit'))
    fireEvent.click(screen.getByTestId('action-DatasetDelete'))

    fireEvent.click(screen.getByRole('button', { name: /grant/i }))

    expect(h.mockCreateGrant).toHaveBeenCalledWith({
      subject_type: 'department',
      subject_id: 'dep-1',
      actions: ['DatasetEdit', 'DatasetDelete'],
      resource_type: 'dataset',
      resource_id: 'ds-1',
    })
  })
})
