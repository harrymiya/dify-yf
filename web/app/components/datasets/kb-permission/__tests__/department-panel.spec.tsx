import { fireEvent, render, screen } from '@testing-library/react'
import DepartmentPanel from '../department-panel'

const h = vi.hoisted(() => {
  return {
    mockFetchTree: vi.fn(),
    mockCreateDepartment: vi.fn(),
    mockFetchMembers: vi.fn(),
    mockInvalidate: vi.fn(),
    tree: [] as any[],
  }
})

vi.mock('../services', () => ({
  fetchDepartmentTree: (...args: unknown[]) => h.mockFetchTree(...args),
  createDepartment: (...args: unknown[]) => h.mockCreateDepartment(...args),
  updateDepartment: vi.fn(),
  deleteDepartment: vi.fn(),
  fetchDepartmentMembers: (...args: unknown[]) => h.mockFetchMembers(...args),
  addDepartmentMembers: vi.fn(),
}))

vi.mock('@tanstack/react-query', () => {
  const useQuery = vi.fn(({ queryKey }: any) => {
    if ((queryKey as string[]).join(',').includes('members'))
      return { data: [], isLoading: false, isError: false } as any
    return { data: h.tree, isLoading: false, isError: false, refetch: vi.fn() } as any
  })
  return {
    useQuery,
    useQueryClient: () => ({ invalidateQueries: h.mockInvalidate }),
    useMutation: ({ mutationFn }: any) => ({
      mutate: (...args: any[]) => mutationFn(...args),
      isPending: false,
      isError: false,
      error: null,
    }),
  }
})

vi.mock('@langgenius/dify-ui/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@langgenius/dify-ui/button', () => ({
  Button: ({ children, onClick, disabled, variant }: any) => (
    <button type="button" onClick={onClick} disabled={disabled} data-variant={variant}>
      {children}
    </button>
  ),
}))

vi.mock('@langgenius/dify-ui/input', () => ({
  Input: (props: any) => <input {...props} />,
}))

describe('DepartmentPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.tree = [
      {
        id: 'dep-1',
        tenant_id: 't1',
        parent_id: null,
        name: 'Engineering',
        sort: 0,
        children: [{ id: 'dep-2', tenant_id: 't1', parent_id: 'dep-1', name: 'Backend', sort: 0, children: [] }],
      },
    ]
    h.mockFetchTree.mockResolvedValue(h.tree)
    h.mockFetchMembers.mockResolvedValue([])
    h.mockCreateDepartment.mockResolvedValue('dep-3')
  })

  it('renders the department tree', async () => {
    render(<DepartmentPanel />)
    expect(await screen.findByText('Engineering')).toBeInTheDocument()
    expect(screen.getByText('Backend')).toBeInTheDocument()
  })

  it('shows empty state with no departments', () => {
    h.tree = []
    render(<DepartmentPanel />)
    expect(screen.queryByText('Engineering')).not.toBeInTheDocument()
  })

  it('opens the create form and submits a new root department', () => {
    h.tree = []
    render(<DepartmentPanel />)

    fireEvent.click(screen.getByRole('button', { name: /createDepartment/i }))
    fireEvent.change(screen.getByTestId('create-department-input'), { target: { value: 'Ops' } })
    fireEvent.click(screen.getByRole('button', { name: /create$/i }))

    expect(h.mockCreateDepartment).toHaveBeenCalledWith({ name: 'Ops', parent_id: null })
  })
})
