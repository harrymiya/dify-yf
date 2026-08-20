import type { ComponentProps } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import KBFusionSearch from '../index'

type ButtonProps = ComponentProps<'button'>
type InputProps = ComponentProps<'input'>

const h = vi.hoisted(() => {
  return {
    mockFetch: vi.fn(),
  }
})

vi.mock('../services', () => ({
  fetchFusionRetrieve: (...args: unknown[]) => h.mockFetch(...args),
}))

vi.mock('@tanstack/react-query', () => {
  const useQuery = ({ queryKey }: { queryKey: unknown }) => {
    const key = Array.isArray(queryKey) ? queryKey.filter(Boolean).join(',') : String(queryKey)
    if (key.includes('datasets'))
      return {
        data: {
          data: [
            { id: 'ds-1', name: 'First KB' },
            { id: 'ds-2', name: 'Second KB' },
          ],
        },
        isLoading: false,
        isError: false,
      }
    return { data: undefined, isLoading: false, isError: false }
  }
  return { useQuery }
})

vi.mock('@langgenius/dify-ui/button', () => ({
  Button: ({ children, onClick, ...props }: ButtonProps) => (
    <button type="button" onClick={onClick} {...props}>
      {children}
    </button>
  ),
}))

vi.mock('@langgenius/dify-ui/input', () => ({
  Input: (props: InputProps) => <input {...props} />,
}))

const sampleRecords = [
  {
    dataset_id: 'ds-1',
    document_id: 'doc-1',
    title: 'Cache invalidation',
    content: 'The hardest problem in computer science.',
    score: 0.9123,
    metadata: {},
  },
  {
    dataset_id: 'ds-2',
    document_id: 'doc-2',
    title: null,
    content: 'Second source paragraph.',
    score: 0.45,
    metadata: {},
  },
]

describe('KBFusionSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    h.mockFetch.mockResolvedValue({
      query: 'q',
      datasets: 2,
      strategy: 'rrf',
      records: sampleRecords,
    })
  })

  it('shows the empty-query hint before any search', () => {
    render(<KBFusionSearch />)
    expect(screen.getByText(/noQuery/i)).toBeInTheDocument()
    expect(h.mockFetch).not.toHaveBeenCalled()
  })

  it('searches and renders fused result records', async () => {
    render(<KBFusionSearch />)
    fireEvent.change(screen.getByTestId('fusion-search-input'), {
      target: { value: 'cache invalidation' },
    })
    fireEvent.click(screen.getByTestId('fusion-search-button'))

    expect(await screen.findByText('The hardest problem in computer science.')).toBeInTheDocument()
    expect(screen.getByText(/First KB/)).toBeInTheDocument()
    expect(screen.queryByText('ds-1')).not.toBeInTheDocument()
    expect(h.mockFetch).toHaveBeenCalledWith({
      query: 'cache invalidation',
      strategy: 'rrf',
    })
  })

  it('renders the fallback title for records without a title', async () => {
    render(<KBFusionSearch />)
    fireEvent.change(screen.getByTestId('fusion-search-input'), { target: { value: 'q' } })
    fireEvent.click(screen.getByTestId('fusion-search-button'))

    await screen.findByText('The hardest problem in computer science.')
    expect(screen.getByText(/unknownTitle/i)).toBeInTheDocument()
  })

  it('shows the error state and allows retry', async () => {
    h.mockFetch.mockRejectedValue(new Error('boom'))
    render(<KBFusionSearch />)
    fireEvent.change(screen.getByTestId('fusion-search-input'), { target: { value: 'q' } })
    fireEvent.click(screen.getByTestId('fusion-search-button'))

    await waitFor(() => expect(screen.getByText(/searchError/i)).toBeInTheDocument())
  })
})
