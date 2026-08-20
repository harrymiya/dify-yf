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
    mockAddMembers: vi.fn(),
    mockInvalidate: vi.fn(),
    tree: [] as DepartmentNode[],
    memberIds: [] as string[],
  }
})

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
  fetchDepartmentTree: (...args: unknown[]) => h.mockFetchTree(...args),
  createDepartment: (...args: unknown[]) => h.mockCreateDepartment(...args),
  updateDepartment: vi.fn(),
  deleteDepartment: vi.fn(),
  fetchDepartmentMembers: (...args: unknown[]) => h.mockFetchMembers(...args),
  addDepartmentMembers: (...args: unknown[]) => h.mockAddMembers(...args),
}))

vi.mock('@tanstack/react-query', () => {
  const useQuery = vi.fn(({ queryKey }: QueryArgs) => {
    const key = Array.isArray(queryKey) ? queryKey.join(',') : String(queryKey)
    if (key.includes('members')) return { data: h.memberIds, isLoading: false, isError: false }
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

vi.mock('@langgenius/dify-ui/avatar', () => ({
  Avatar: ({ name }: { name?: string }) => <span data-testid="avatar">{name}</span>,
}))

vi.mock('@langgenius/dify-ui/combobox', () => {
  const Combobox = ({
    items,
    onValueChange,
    multiple,
    children,
  }: {
    items: { id: string; name?: string; email?: string }[]
    onValueChange?: (v: unknown) => void
    multiple?: boolean
    children?: React.ReactNode
  }) => (
    <div data-testid="member-picker-combobox">
      {children}
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() =>
            onValueChange?.(
      multiple
        ? [{ ...item, name: item.name ?? '', email: item.email ?? '' }]
        : item,
    )
          }
        >
          {item.name || item.email}
        </button>
      ))}
    </div>
  )
  return {
    Combobox,
    ComboboxValue: ({ children }: { children?: (v: unknown) => React.ReactNode }) =>
      children?.([]),
    ComboboxChip: ({ children }: { children?: React.ReactNode }) => children ?? null,
    ComboboxChipRemove: () => null,
    ComboboxChips: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    ComboboxInput: (props: InputProps) => <input {...props} />,
    ComboboxInputGroup: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    ComboboxItem: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    ComboboxItemIndicator: () => null,
    ComboboxItemText: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    ComboboxList: () => null,
    ComboboxPopup: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    ComboboxPortal: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    ComboboxPositioner: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
    ComboboxEmpty: () => null,
  }
})

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
    h.memberIds = []
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

  it('adds a selected member to a department via the member picker', async () => {
    h.mockFetchMembers.mockResolvedValue(['acct-1'])
    render(<DepartmentPanel />)

    fireEvent.click(await screen.findByText('Engineering'))

    // Only members not already in the department are offered.
    const bobOption = screen.getByRole('button', { name: 'Bob' })
    fireEvent.click(bobOption)

    fireEvent.click(screen.getByRole('button', { name: /addMembers/i }))

    expect(h.mockAddMembers).toHaveBeenCalledWith('dep-1', ['acct-2'])
  })

  it('shows member names and email instead of raw ids', async () => {
    h.memberIds = ['acct-1']
    h.mockFetchMembers.mockResolvedValue(['acct-1'])
    render(<DepartmentPanel />)

    fireEvent.click(await screen.findByText('Engineering'))

    const row = await screen.findByTestId('department-member-acct-1')
    expect(row).toHaveTextContent('Alice')
    expect(row).toHaveTextContent('alice@example.com')
    expect(screen.queryByText('acct-1')).not.toBeInTheDocument()
  })

  it('shows department description instead of its id in the header', async () => {
    h.tree = [
      {
        id: 'dep-1',
        tenant_id: 't1',
        parent_id: null,
        name: 'Engineering',
        description: 'Builds and maintains the platform',
        sort: 0,
        children: [],
      },
    ]
    render(<DepartmentPanel />)

    fireEvent.click(await screen.findByText('Engineering'))

    // The description appears in the detail header, not in the tree node.
    expect(screen.getByText('Builds and maintains the platform')).toBeInTheDocument()
    expect(screen.queryByText('#dep-1')).not.toBeInTheDocument()
  })
})
