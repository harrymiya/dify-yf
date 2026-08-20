'use client'

import type { Member } from '@/models/common'
import type { DepartmentNode } from './types'
import { Avatar } from '@langgenius/dify-ui/avatar'
import { Button } from '@langgenius/dify-ui/button'
import {
  Combobox,
  ComboboxChip,
  ComboboxChipRemove,
  ComboboxChips,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxInputGroup,
  ComboboxItem,
  ComboboxItemIndicator,
  ComboboxItemText,
  ComboboxList,
  ComboboxPopup,
  ComboboxPortal,
  ComboboxPositioner,
  ComboboxValue,
} from '@langgenius/dify-ui/combobox'
import { Input } from '@langgenius/dify-ui/input'
import { toast } from '@langgenius/dify-ui/toast'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMembers } from '@/service/use-common'
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
  description?: string
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
  const [descriptionInput, setDescriptionInput] = useState('')
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
    mutationFn: (payload: { name: string; description?: string; parent_id: string | null }) =>
      createDepartment(payload),
    onSuccess: () => {
      toast.success(t('createdSuccess'))
      invalidate()
      setEditing(null)
      setNameInput('')
      setDescriptionInput('')
    },
    onError: () => toast.error(t('loadError')),
  })

  const renameMutation = useMutation({
    mutationFn: ({ id, name, description }: { id: string; name: string; description?: string }) =>
      updateDepartment(id, { name, description }),
    onSuccess: () => {
      toast.success(t('updatedSuccess'))
      invalidate()
      setEditing(null)
      setNameInput('')
      setDescriptionInput('')
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
  const { data: accountsData } = useMembers()
  const accounts = accountsData?.accounts ?? []

  const toggleExpand = (id: string) => setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))

  const renderNode = (node: DepartmentNode, depth: number) => {
    const hasChildren = (node.children ?? []).length > 0
    const isOpen = expanded[node.id]
    return (
      <div key={node.id}>
        <div
          className={`group flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 system-sm-regular hover:bg-state-base-hover ${
            selectedId === node.id
              ? 'bg-state-base-active text-components-menu-item-text-active'
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
    const description = descriptionInput.trim() || undefined
    if (editing?.mode === 'create')
      createMutation.mutate({ name, description, parent_id: editing.parentId })
    else if (editing?.mode === 'rename' && editing.id)
      renameMutation.mutate({ id: editing.id, name, description })
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
            onClick={() => {
              setEditing({ mode: 'create', parentId: null, name: '' })
              setDescriptionInput('')
            }}
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
            <Input
              value={descriptionInput}
              onChange={(e) => setDescriptionInput(e.target.value)}
              placeholder={t('departmentDescriptionPlaceholder')}
              data-testid="create-department-description-input"
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
                  setDescriptionInput('')
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
                {selected.description && (
                  <div className="mt-0.5 text-xs text-text-tertiary">{selected.description}</div>
                )}
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
                      description: selected.description ?? '',
                    })
                    setNameInput(selected.name)
                    setDescriptionInput(selected.description ?? '')
                  }}
                >
                  {t('rename')}
                </Button>
                <Button
                  size="small"
                  variant="secondary"
                  onClick={() => {
                    setEditing({ mode: 'create', parentId: selected.id, name: '' })
                    setDescriptionInput('')
                  }}
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
                  placeholder={t('departmentNamePlaceholder')}
                  data-testid="rename-department-input"
                />
                <Input
                  value={descriptionInput}
                  onChange={(e) => setDescriptionInput(e.target.value)}
                  placeholder={t('departmentDescriptionPlaceholder')}
                  data-testid="rename-department-description-input"
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
                      setDescriptionInput('')
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
                  placeholder={t('departmentNamePlaceholder')}
                  data-testid="create-sub-department-input"
                />
                <Input
                  value={descriptionInput}
                  onChange={(e) => setDescriptionInput(e.target.value)}
                  placeholder={t('departmentDescriptionPlaceholder')}
                  data-testid="create-sub-department-description-input"
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
                      setDescriptionInput('')
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
                  {memberIds.map((id) => {
                    const account = accounts.find((account) => account.id === id)
                    return (
                      <li
                        key={id}
                        className="flex items-center gap-2.5 py-2 text-sm"
                        data-testid={`department-member-${id}`}
                      >
                        {account ? (
                          <>
                            <Avatar
                              avatar={account.avatar_url || account.avatar}
                              size="sm"
                              name={account.name}
                              className="shrink-0"
                            />
                            <span className="min-w-0">
                              <span className="block truncate system-sm-medium text-text-primary">
                                {account.name || account.email || '-'}
                              </span>
                              {account.email && account.email !== (account.name || '-') && (
                                <span className="block truncate system-xs-regular text-text-tertiary">
                                  {account.email}
                                </span>
                              )}
                            </span>
                          </>
                        ) : (
                          <span className="truncate text-text-secondary">-</span>
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function MemberPicker({ existing, onAdd }: { existing: string[]; onAdd: (ids: string[]) => void }) {
  const { t: rawT } = useTranslation('datasetPermission')
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string
  const { data } = useMembers()
  const accounts = data?.accounts ?? []
  const available = accounts.filter((member) => !existing.includes(member.id))

  const [value, setValue] = useState<Member[]>([])
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)

  const memberSearchText = (member: Member) =>
    `${member.name} ${member.email} ${member.id}`.toLowerCase()
  const filterFn = (member: Member, searchText: string) =>
    memberSearchText(member).includes(searchText.toLowerCase())

  const add = () => {
    if (value.length === 0) return
    onAdd(value.map((member) => member.id))
    setValue([])
    setQuery('')
    setOpen(false)
  }

  const memberLabel = (member: Member) => member.name || member.email || member.id

  return (
    <div className="flex items-center gap-2">
      <Combobox<Member, true>
        multiple
        items={available}
        value={value}
        onValueChange={setValue}
        inputValue={query}
        onInputValueChange={setQuery}
        open={open}
        onOpenChange={setOpen}
        itemToStringLabel={memberLabel}
        itemToStringValue={(member) => member.id}
        filter={filterFn}
      >
        <ComboboxInputGroup className="h-auto min-h-8 w-56 items-start py-1">
          <ComboboxChips>
            <ComboboxValue<Member, true>>
              {(selectedValue) => (
                <>
                  {selectedValue?.map((member) => (
                    <ComboboxChip key={member.id}>
                      <span className="max-w-32 truncate">{memberLabel(member)}</span>
                      <ComboboxChipRemove aria-label={`Remove ${memberLabel(member)}`} />
                    </ComboboxChip>
                  ))}
                  <ComboboxInput
                    data-testid="member-picker-input"
                    placeholder={
                      selectedValue?.length ? '' : (t('selectMemberPlaceholder') as string)
                    }
                    className="min-w-24 px-1 py-0.5"
                  />
                </>
              )}
            </ComboboxValue>
          </ComboboxChips>
        </ComboboxInputGroup>
        <ComboboxPortal>
          <ComboboxPositioner>
            <ComboboxPopup aria-label={t('addMembers') as string} className="w-56">
              <ComboboxList<Member>>
                {(member) => (
                  <ComboboxItem key={member.id} value={member} className="py-1.5">
                    <ComboboxItemText className="flex items-center px-0">
                      <span className="min-w-0 flex-1">
                        <span className="block truncate system-sm-medium text-text-primary">
                          {member.name || member.email}
                        </span>
                        {member.email && member.email !== member.name && (
                          <span className="block truncate system-xs-regular text-text-tertiary">
                            {member.email}
                          </span>
                        )}
                      </span>
                    </ComboboxItemText>
                    <ComboboxItemIndicator />
                  </ComboboxItem>
                )}
              </ComboboxList>
              <ComboboxEmpty>{t('noMemberResults')}</ComboboxEmpty>
            </ComboboxPopup>
          </ComboboxPositioner>
        </ComboboxPortal>
      </Combobox>
      <Button size="small" variant="primary" onClick={add} disabled={value.length === 0}>
        {t('addMembers')}
      </Button>
    </div>
  )
}
