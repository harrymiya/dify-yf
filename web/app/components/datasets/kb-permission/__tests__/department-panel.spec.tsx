import type { ComponentProps } from 'react'
import type { DepartmentNode } from '../types'
import { fireEvent, render, screen } from '@testing-library/react'
import DepartmentPanel from '../department-panel'

type QueryArgs = {
  queryKey: unknown
}
type MutationArgs = {
  mutationFn: (...args: unknown[]) => unknown
}
type ButtonProps = ComponentProps<'button'> & {
  variant?: string
}
type InputProps = ComponentProps<'input'>

const h = vi.hoisted(() => {
  return {
    mockFetchTree: vi.fn(),
    mockCreateDepartment: vi.fn(),
    mockFetchMembers: vi.fn(),
    mockInvalidate: vi.fn(),
    tree: [] as DepartmentNode[],
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
  const useQuery = vi.fn(({ queryKey }: QueryArgs) => {
    const key = Array.isArray(queryKey) ? queryKey.join(',') : String(queryKey)
    if (key.includes('members')) return { data: [], isLoading: false, isError: false }
    return { data: h.tree, isLoading: false, isError: false, refetch: vi.fn() }
  })
  return {
    useQuery,
    useQueryClient: () => ({ invalidateQueries: h.mockInvalidate }),
    useMutation: ({ mutationFn }: MutationArgs) => ({
      mutate: (...args: unknown[]) => mutationFn(...args),
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
  Button: ({ children, onClick, disabled, variant }: ButtonProps) => (
    <button type="button" onClick={onClick} disabled={disabled} data-variant={variant}>
      {children}
    </button>
  ),
}))

vi.mock('@langgenius/dify-ui/input', () => ({
  Input: (props: InputProps) => <input {...props} />,
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
        children: [
          {
            id: 'dep-2',
            tenant_id: 't1',
            parent_id: 'dep-1',
            name: 'Backend',
            sort: 0,
            children: [],
          },
        ],
      },
    ]
    h.mockFetchTree.mockResolvedValue(h.tree)
    h.mockFetchMembers.mockResolvedValue([])
    h.mockCreateDepartment.mockResolvedValue('dep-3')
  })

  it('renders the department tree', async () => {
    render(<DepartmentPanel />)
    expect(await screen.findByText('Engineering')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))
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
