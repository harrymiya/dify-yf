'use client'

import type { DepartmentNode, KBPermissionSubjectType } from './types'
import { Button } from '@langgenius/dify-ui/button'
import { toast } from '@langgenius/dify-ui/toast'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchDatasets } from '@/service/datasets'
import { useMembers } from '@/service/use-common'
import { createGrant, fetchDepartmentTree, fetchGrants, revokeGrant } from './services'

type ResourceType = 'dataset' | 'document'

type ActionKey =
  | 'DatasetPreview'
  | 'DatasetEdit'
  | 'DatasetDelete'
  | 'DatasetUse'
  | 'DatasetRetrievalRecall'
  | 'DatasetDocumentDownload'
  | 'DatasetAccessConfig'
  | 'DocumentRead'
  | 'DocumentEdit'
  | 'DocumentDownload'

const DATASET_ACTIONS: ActionKey[] = [
  'DatasetPreview',
  'DatasetEdit',
  'DatasetDelete',
  'DatasetRetrievalRecall',
  'DatasetUse',
]

const DOCUMENT_ACTIONS: ActionKey[] = ['DocumentRead', 'DocumentEdit', 'DocumentDownload']

export default function GrantPanel() {
  const { t: rawT } = useTranslation('datasetPermission')
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string
  const queryClient = useQueryClient()
  const [resourceType, setResourceType] = useState<ResourceType>('dataset')
  const [resourceId, setResourceId] = useState('')
  const [subjectType, setSubjectType] = useState<KBPermissionSubjectType>('account')
  const [subjectId, setSubjectId] = useState('')
  const [selectedActions, setSelectedActions] = useState<ActionKey[]>([])

  const { data: datasetPage } = useQuery({
    queryKey: ['dataset-permission', 'datasets'],
    queryFn: () => fetchDatasets({ url: '/datasets', params: { limit: 100, page: 1 } }),
  })
  const datasets = datasetPage?.data ?? []

  const { data: members } = useMembers()
  const accounts = useMemo(() => members?.accounts ?? [], [members?.accounts])

  const { data: departmentTree = [] } = useQuery<DepartmentNode[]>({
    queryKey: ['dataset-permission', 'departments'],
    queryFn: fetchDepartmentTree,
  })
  const departments = useMemo(() => {
    const flatten = (nodes: DepartmentNode[]): DepartmentNode[] =>
      nodes.flatMap((n) => [n, ...flatten(n.children ?? [])])
    return flatten(departmentTree)
  }, [departmentTree])

  const { data: grants = [] } = useQuery({
    queryKey: ['dataset-permission', 'grants', resourceType, resourceId],
    queryFn: () => fetchGrants(resourceType, resourceId).then((r) => r.data ?? []),
    enabled: !!resourceId,
  })

  const actions = resourceType === 'dataset' ? DATASET_ACTIONS : DOCUMENT_ACTIONS

  const actionLabel = (key: ActionKey) => t(`action${key}`)

  const subjectOptions = useMemo(() => {
    if (subjectType === 'account')
      return accounts.map((a) => ({ value: a.id, label: a.name || a.email }))
    if (subjectType === 'department')
      return departments.map((d) => ({ value: d.id, label: d.name }))
    return []
  }, [subjectType, accounts, departments])

  const toggleAction = (key: ActionKey) => {
    setSelectedActions((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    )
  }

  const canSubmit = !!resourceId && !!subjectId && selectedActions.length > 0

  const submit = async () => {
    if (!canSubmit) return
    try {
      await createGrant({
        subject_type: subjectType,
        subject_id: subjectId,
        actions: selectedActions,
        resource_type: resourceType,
        resource_id: resourceId,
      })
      toast.success(t('granted'))
      setSelectedActions([])
      queryClient.invalidateQueries({
        queryKey: ['dataset-permission', 'grants', resourceType, resourceId],
      })
    } catch {
      toast.error(t('loadError'))
    }
  }

  const revoke = async (payload: {
    subjectId: string
    subjectType: KBPermissionSubjectType
    actions?: ActionKey[]
  }) => {
    try {
      await revokeGrant({
        subject_type: payload.subjectType,
        subject_id: payload.subjectId,
        actions: payload.actions,
        resource_type: resourceType,
        resource_id: resourceId,
      })
      toast.success(t('revoked'))
      queryClient.invalidateQueries({
        queryKey: ['dataset-permission', 'grants', resourceType, resourceId],
      })
    } catch {
      toast.error(t('loadError'))
    }
  }

  const subjectLabel = (type: KBPermissionSubjectType, id: string): string => {
    if (type === 'account') return accounts.find((a) => a.id === id)?.name || id
    if (type === 'department') return departments.find((d) => d.id === id)?.name || id
    return id
  }

  return (
    <div className="grid h-full grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      {/* grant form */}
      <div className="flex flex-col gap-4 overflow-y-auto rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
        <div>
          <div className="text-base font-medium text-text-primary">{t('grantTitle')}</div>
          <div className="mt-0.5 text-xs text-text-tertiary">{t('grantDesc')}</div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-text-secondary">{t('resource')}</label>
          <div className="flex gap-2">
            <select
              value={resourceType}
              onChange={(e) => {
                setResourceType(e.target.value as ResourceType)
                setResourceId('')
              }}
              className="h-8 rounded-lg border border-divider-regular bg-background-default px-2 system-sm-regular text-text-primary"
              data-testid="resource-type-select"
            >
              <option value="dataset">{t('resourceDataset')}</option>
              <option value="document">{t('resourceDocument')}</option>
            </select>
            <select
              value={resourceId}
              onChange={(e) => setResourceId(e.target.value)}
              className="h-8 min-w-0 flex-1 rounded-lg border border-divider-regular bg-background-default px-2 system-sm-regular text-text-primary"
              data-testid="resource-select"
            >
              <option value="">{t('selectResource')}</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-text-secondary">{t('subject')}</label>
          <div className="flex gap-2">
            <select
              value={subjectType}
              onChange={(e) => {
                setSubjectType(e.target.value as KBPermissionSubjectType)
                setSubjectId('')
              }}
              className="h-8 rounded-lg border border-divider-regular bg-background-default px-2 system-sm-regular text-text-primary"
              data-testid="subject-type-select"
            >
              <option value="account">{t('subjectTypeAccount')}</option>
              <option value="department">{t('subjectTypeDepartment')}</option>
            </select>
            <select
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
              className="h-8 min-w-0 flex-1 rounded-lg border border-divider-regular bg-background-default px-2 system-sm-regular text-text-primary"
              data-testid="subject-select"
            >
              <option value="">{t('selectSubject')}</option>
              {subjectOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-text-secondary">{t('actions')}</label>
          <div className="flex flex-col gap-1.5">
            {actions.map((key) => (
              <label
                key={key}
                className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 system-sm-regular text-text-primary hover:bg-state-base-hover"
              >
                <input
                  type="checkbox"
                  checked={selectedActions.includes(key)}
                  onChange={() => toggleAction(key)}
                  data-testid={`action-${key}`}
                />
                {actionLabel(key)}
              </label>
            ))}
          </div>
        </div>

        <div className="mt-auto">
          <Button variant="primary" size="medium" onClick={submit} disabled={!canSubmit}>
            {t('grant')}
          </Button>
        </div>
      </div>

      {/* existing grants */}
      <div className="flex min-h-0 flex-col overflow-y-auto rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
        <div className="mb-2 text-sm font-medium text-text-primary">{t('existingGrants')}</div>
        {!resourceId ? (
          <div className="py-8 text-center text-sm text-text-tertiary">{t('selectResource')}</div>
        ) : grants.length === 0 ? (
          <div className="py-8 text-center text-sm text-text-tertiary">{t('noGrants')}</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-divider-subtle text-xs text-text-tertiary">
                <th className="py-2 pr-2 font-medium">{t('subject')}</th>
                <th className="py-2 pr-2 font-medium">{t('actions')}</th>
                <th className="py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {grants.map((grant) => (
                <tr key={grant.id} className="border-b border-divider-subtle">
                  <td className="py-2 pr-2 text-text-primary">
                    {subjectLabel(grant.subject_type, grant.subject_id)}
                  </td>
                  <td className="py-2 pr-2 text-text-secondary">
                    {t(`action${grant.action as ActionKey}`)}
                  </td>
                  <td className="py-2 text-right">
                    <Button
                      size="small"
                      variant="ghost"
                      tone="destructive"
                      onClick={() =>
                        revoke({
                          subjectId: grant.subject_id,
                          subjectType: grant.subject_type,
                          actions: [grant.action as ActionKey],
                        })
                      }
                    >
                      {t('revoke')}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
