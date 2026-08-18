'use client'

import type { DepartmentNode } from './types'
import { Button } from '@langgenius/dify-ui/button'
import { Input } from '@langgenius/dify-ui/input'
import { toast } from '@langgenius/dify-ui/toast'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  addDepartmentMembers,
  createDepartment,
  deleteDepartment,
  fetchDepartmentMembers,
  fetchDepartmentTree,
  updateDepartment,
} from './services'

type EditingState = {
  mode: 'create' | 'rename'
  parentId: string | null
  id?: string
  name: string
} | null

const flatten = (nodes: DepartmentNode[]): DepartmentNode[] =>
  nodes.flatMap((node) => [node, ...flatten(node.children ?? [])])

export default function DepartmentPanel() {
  const { t: rawT } = useTranslation('datasetPermission')
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<EditingState>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [nameInput, setNameInput] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const {
    data: tree = [],
    isLoading,
    isError,
    refetch,
  } = useQuery<DepartmentNode[]>({
    queryKey: ['dataset-permission', 'departments'],
    queryFn: fetchDepartmentTree,
  })

  const allNodes = flatten(tree)

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['dataset-permission', 'departments'] })
  }, [queryClient])

  const createMutation = useMutation({
    mutationFn: (payload: { name: string; parent_id: string | null }) => createDepartment(payload),
    onSuccess: () => {
      toast.success(t('createdSuccess'))
      invalidate()
      setEditing(null)
      setNameInput('')
    },
    onError: () => toast.error(t('loadError')),
  })

  const renameMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => updateDepartment(id, { name }),
    onSuccess: () => {
      toast.success(t('updatedSuccess'))
      invalidate()
      setEditing(null)
      setNameInput('')
    },
    onError: () => toast.error(t('loadError')),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteDepartment,
    onSuccess: () => {
      toast.success(t('deletedSuccess'))
      invalidate()
      setSelectedId(null)
    },
    onError: () => toast.error(t('loadError')),
  })

  const memberMutation = useMutation({
    mutationFn: ({ id, accountIds }: { id: string; accountIds: string[] }) =>
      addDepartmentMembers(id, accountIds),
    onSuccess: () => {
      toast.success(t('addMemberSuccess'))
      if (selectedId)
        queryClient.invalidateQueries({ queryKey: ['dataset-permission', 'members', selectedId] })
    },
    onError: () => toast.error(t('loadError')),
  })

  const selected = allNodes.find((node) => node.id === selectedId) ?? null
  const { data: memberIds = [] } = useQuery<string[]>({
    queryKey: ['dataset-permission', 'members', selectedId],
    queryFn: () => (selectedId ? fetchDepartmentMembers(selectedId) : Promise.resolve([])),
    enabled: !!selectedId,
  })

  const toggleExpand = (id: string) => setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))

  const renderNode = (node: DepartmentNode, depth: number) => {
    const hasChildren = (node.children ?? []).length > 0
    const isOpen = expanded[node.id]
    return (
      <div key={node.id}>
        <div
          className={`group flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 system-sm-regular hover:bg-state-base-hover ${
            selectedId === node.id
              ? 'text-text-primary-on-solid bg-state-accent-solid'
              : 'text-text-primary'
          }`}
          role="button"
          tabIndex={0}
          onClick={() => setSelectedId(node.id)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') setSelectedId(node.id)
          }}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              toggleExpand(node.id)
            }}
            className={`w-4 shrink-0 text-xs transition-transform ${isOpen ? 'rotate-90' : ''} ${
              hasChildren ? 'visible' : 'invisible'
            }`}
            aria-label="toggle"
          >
            ▸
          </button>
          <span className="min-w-0 flex-1 truncate">{node.name}</span>
          <span className="shrink-0 text-xs opacity-60">{(node.children ?? []).length}</span>
        </div>
        {hasChildren && isOpen && (
          <div className="pl-4">{node.children.map((c) => renderNode(c, depth + 1))}</div>
        )}
      </div>
    )
  }

  const submitEdit = () => {
    const name = nameInput.trim()
    if (!name) return
    if (editing?.mode === 'create') createMutation.mutate({ name, parent_id: editing.parentId })
    else if (editing?.mode === 'rename' && editing.id)
      renameMutation.mutate({ id: editing.id, name })
  }

  return (
    <div className="grid h-full grid-cols-1 gap-4 xl:grid-cols-[280px_1fr]">
      {/* tree */}
      <div className="flex min-h-0 flex-col rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-2 shadow-xs shadow-shadow-shadow-3">
        <div className="mb-2 flex items-center justify-between px-2 pt-1">
          <span className="text-sm font-medium text-text-primary">{t('departmentTab')}</span>
          <Button
            size="small"
            variant="secondary"
            onClick={() => setEditing({ mode: 'create', parentId: null, name: '' })}
          >
            {t('createDepartment')}
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {isLoading && <div className="px-3 py-2 text-sm text-text-tertiary">{t('loading')}</div>}
          {isError && (
            <button
              type="button"
              className="px-3 py-2 text-sm text-text-destructive"
              onClick={() => refetch()}
            >
              {t('loadError')}
            </button>
          )}
          {!isLoading && tree.length === 0 && (
            <div className="px-3 py-2 text-sm text-text-tertiary">{t('noDepartments')}</div>
          )}
          {tree.map((node) => renderNode(node, 0))}
        </div>
        {editing && editing.mode === 'create' && editing.parentId === null && (
          <div className="mt-2 flex flex-col gap-2 border-t border-divider-regular p-2">
            <Input
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submitEdit()}
              placeholder={t('departmentNamePlaceholder')}
              data-testid="create-department-input"
            />
            <div className="flex gap-2">
              <Button
                size="small"
                variant="primary"
                onClick={submitEdit}
                disabled={!nameInput.trim()}
              >
                {t('create')}
              </Button>
              <Button
                size="small"
                variant="tertiary"
                onClick={() => {
                  setEditing(null)
                  setNameInput('')
                }}
              >
                {t('cancel')}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* detail */}
      <div className="flex min-h-0 flex-col gap-4 overflow-y-auto">
        {!selected ? (
          <div className="flex h-full items-center justify-center rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg system-sm-regular text-text-tertiary shadow-xs shadow-shadow-shadow-3">
            {t('noDepartments')}
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between gap-3 rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
              <div className="min-w-0">
                <div className="text-base font-medium text-text-primary">{selected.name}</div>
                <div className="mt-0.5 text-xs text-text-tertiary">#{selected.id}</div>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button
                  size="small"
                  variant="secondary"
                  onClick={() => {
                    setEditing({
                      mode: 'rename',
                      parentId: selected.parent_id,
                      id: selected.id,
                      name: selected.name,
                    })
                    setNameInput(selected.name)
                  }}
                >
                  {t('rename')}
                </Button>
                <Button
                  size="small"
                  variant="secondary"
                  onClick={() => setEditing({ mode: 'create', parentId: selected.id, name: '' })}
                >
                  {t('createDepartment')}
                </Button>
                <Button
                  size="small"
                  variant="secondary"
                  tone="destructive"
                  onClick={() => deleteMutation.mutate(selected.id)}
                >
                  {t('deleteDepartment')}
                </Button>
              </div>
            </div>

            {editing && editing.mode === 'rename' && (
              <div className="flex flex-col gap-2 rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
                <Input
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && submitEdit()}
                  data-testid="rename-department-input"
                />
                <div className="flex gap-2">
                  <Button
                    size="small"
                    variant="primary"
                    onClick={submitEdit}
                    disabled={!nameInput.trim()}
                  >
                    {t('save')}
                  </Button>
                  <Button
                    size="small"
                    variant="tertiary"
                    onClick={() => {
                      setEditing(null)
                      setNameInput('')
                    }}
                  >
                    {t('cancel')}
                  </Button>
                </div>
              </div>
            )}

            {editing && editing.mode === 'create' && editing.parentId === selected.id && (
              <div className="flex flex-col gap-2 rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
                <Input
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && submitEdit()}
                  data-testid="create-sub-department-input"
                />
                <div className="flex gap-2">
                  <Button
                    size="small"
                    variant="primary"
                    onClick={submitEdit}
                    disabled={!nameInput.trim()}
                  >
                    {t('create')}
                  </Button>
                  <Button
                    size="small"
                    variant="tertiary"
                    onClick={() => {
                      setEditing(null)
                      setNameInput('')
                    }}
                  >
                    {t('cancel')}
                  </Button>
                </div>
              </div>
            )}

            <div className="rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
              <div className="mb-3 flex items-center justify-between">
                <span className="text-sm font-medium text-text-primary">{t('members')}</span>
                <MemberPicker
                  existing={memberIds}
                  onAdd={(ids) => memberMutation.mutate({ id: selected.id, accountIds: ids })}
                />
              </div>
              {memberIds.length === 0 ? (
                <div className="py-6 text-center text-sm text-text-tertiary">{t('noMembers')}</div>
              ) : (
                <ul className="flex flex-col divide-y divide-divider-subtle">
                  {memberIds.map((id) => (
                    <li key={id} className="flex items-center justify-between py-2 text-sm">
                      <span className="truncate text-text-primary">{id}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function MemberPicker({ onAdd }: { existing: string[]; onAdd: (ids: string[]) => void }) {
  const { t: rawT } = useTranslation('datasetPermission')
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string
  const [input, setInput] = useState('')
  const add = () => {
    const value = input.trim()
    if (!value) return
    onAdd(
      value
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    )
    setInput('')
  }
  return (
    <div className="flex items-center gap-2">
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && add()}
        placeholder={t('selectMemberPlaceholder')}
        className="w-56"
        data-testid="member-picker-input"
      />
      <Button size="small" variant="primary" onClick={add} disabled={!input.trim()}>
        {t('addMembers')}
      </Button>
    </div>
  )
}
