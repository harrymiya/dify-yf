'use client'

import type { AuditLogItem, AuditLogType } from './types'
import { Button } from '@langgenius/dify-ui/button'
import { Input } from '@langgenius/dify-ui/input'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { KBPageLayout } from '@/app/components/datasets/kb-page-layout'
// oxlint-disable-next-line no-restricted-imports -- KB permission feature endpoints are not generated yet.
import { fetchDepartmentTree } from '@/app/components/datasets/kb-permission/services'
import type { DepartmentNode } from '@/app/components/datasets/kb-permission/types'
import { fetchDatasets } from '@/service/datasets'
import { useMembers } from '@/service/use-common'
import { fetchAuditLogs } from './services'

const RESOURCE_LABEL_KEY: Record<string, string> = {
  dataset: 'resourceDataset',
  document: 'resourceDocument',
  app: 'resourceApp',
  department: 'resourceDepartment',
  role: 'resourceRole',
}

const resourceLabel = (
  row: AuditLogItem,
  datasets: Array<{ id: string; name: string }>,
  departmentById: Map<string, string>,
  t: (key: string) => string,
): string => {
  const id = row.resource_id
  if (!id) return '-'
  switch (row.resource_type) {
    case 'dataset':
      return datasets.find((d) => d.id === id)?.name || t(RESOURCE_LABEL_KEY.dataset)
    case 'department':
      return departmentById.get(id) || t(RESOURCE_LABEL_KEY.department)
    case 'document':
      return t(RESOURCE_LABEL_KEY.document)
    case 'app':
      return t(RESOURCE_LABEL_KEY.app)
    case 'role':
      return t(RESOURCE_LABEL_KEY.role)
    default:
      return '-'
  }
}

const TYPE_ORDER: AuditLogType[] = ['qna', 'retrieval', 'download', 'permission_change', 'system']

const flattenDepartments = (nodes: DepartmentNode[]): Array<{ id: string; name: string }> => {
  const flat: Array<{ id: string; name: string }> = []
  const walk = (list: DepartmentNode[]) => {
    for (const n of list) {
      flat.push({ id: n.id, name: n.name })
      if (n.children?.length) walk(n.children)
    }
  }
  walk(nodes)
  return flat
}

const userTypeLabelKey = (userType: string): string => {
  switch (userType) {
    case 'account':
      return 'userTypeAccount'
    case 'end-user':
      return 'userTypeEndUser'
    case 'system':
      return 'userTypeSystem'
    default:
      return 'userTypeAccount'
  }
}

const typeLabelKey = (type: AuditLogType) =>
  `type${type.charAt(0).toUpperCase()}${type.slice(1).replace(/_(\w)/g, (_m, c: string) => c.toUpperCase())}`

export default function AuditLogsPage() {
  const { t: rawT } = useTranslation('auditLogs')
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string
  const [logType, setLogType] = useState('')
  const [action, setAction] = useState('')
  const [status, setStatus] = useState('')
  const [resourceId, setResourceId] = useState('')
  const [departmentId, setDepartmentId] = useState('')
  const [applied, setApplied] = useState({
    logType: '',
    action: '',
    status: '',
    resourceId: '',
    departmentId: '',
  })
  const [page, setPage] = useState(1)
  const pageSize = 20

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['audit-logs', applied, page, pageSize],
    queryFn: () =>
      fetchAuditLogs({
        log_type: applied.logType || undefined,
        action: applied.action || undefined,
        status: applied.status || undefined,
        resource_id: applied.resourceId || undefined,
        department_id: applied.departmentId || undefined,
        page,
        page_size: pageSize,
      }),
  })

  const { data: membersData } = useMembers()
  const members = membersData?.accounts ?? []

  const { data: datasetPage } = useQuery({
    queryKey: ['audit-logs', 'datasets'],
    queryFn: () => fetchDatasets({ url: '/datasets', params: { limit: 100, page: 1 } }),
  })
  const datasets = datasetPage?.data ?? []

  const { data: departmentTree = [] } = useQuery({
    queryKey: ['audit-logs', 'departments'],
    queryFn: fetchDepartmentTree,
  })

  const departmentById = useMemo(() => {
    const map = new Map<string, string>()
    const walk = (nodes: Array<{ id: string; name: string; children?: unknown[] }>) => {
      for (const n of nodes) {
        map.set(n.id, n.name)
        if (n.children?.length) walk(n.children as typeof nodes)
      }
    }
    walk(departmentTree)
    return map
  }, [departmentTree])

  const departmentOptions = useMemo(() => flattenDepartments(departmentTree), [departmentTree])

  const memberById = useMemo(
    () => new Map(members.map((m) => [m.id, m])),
    [members],
  )

  const applyFilters = () => {
    setApplied({ logType, action, status, resourceId, departmentId })
    setPage(1)
  }

  const rows = data?.data ?? []
  const total = data?.total ?? 0
  const totalPages = data ? Math.max(Math.ceil(data.total / data.page_size), 1) : 1

  return (
    <KBPageLayout title={t('title')} description={t('desc')}>
      <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg shadow-xs shadow-shadow-shadow-3">
        <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-divider-subtle px-4 py-3">
          <select
            value={logType}
            onChange={(e) => setLogType(e.target.value)}
            className="h-8 rounded-lg border border-divider-regular bg-background-default px-2 system-sm-regular text-text-primary"
            aria-label={t('typeFilter')}
            data-testid="filter-type"
          >
            <option value="">{t('typeAll')}</option>
            {TYPE_ORDER.map((type) => (
              <option key={type} value={type}>
                {t(typeLabelKey(type))}
              </option>
            ))}
          </select>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-8 rounded-lg border border-divider-regular bg-background-default px-2 system-sm-regular text-text-primary"
            aria-label={t('statusFilter')}
            data-testid="filter-status"
          >
            <option value="">{t('statusAll')}</option>
            <option value="success">{t('statusSuccess')}</option>
            <option value="failure">{t('statusFailure')}</option>
          </select>
          <Input
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder={t('actionFilter')}
            className="w-40"
            data-testid="filter-action"
          />
          <Input
            value={resourceId}
            onChange={(e) => setResourceId(e.target.value)}
            placeholder={t('resourceIdPlaceholder')}
            className="w-56"
            data-testid="filter-resource"
          />
          <select
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
            className="h-8 rounded-lg border border-divider-regular bg-background-default px-2 system-sm-regular text-text-primary"
            aria-label={t('departmentFilter')}
            data-testid="filter-department"
          >
            <option value="">{t('allDepartments')}</option>
            {departmentOptions.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
          <Button size="small" variant="primary" onClick={applyFilters} data-testid="apply-filters">
            {t('search')}
          </Button>
          <Button
            size="small"
            variant="tertiary"
            onClick={() => {
              setLogType('')
              setAction('')
              setStatus('')
              setResourceId('')
              setDepartmentId('')
              setApplied({ logType: '', action: '', status: '', resourceId: '', departmentId: '' })
              setPage(1)
            }}
          >
            {t('reset')}
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto bg-background-default-subtle p-2">
          {isLoading && <div className="p-6 text-sm text-text-tertiary">{t('loading')}</div>}
          {isError && (
            <button
              type="button"
              className="p-6 text-sm text-text-destructive"
              onClick={() => refetch()}
            >
              {t('loadError')}
            </button>
          )}
          {!isLoading && !isError && rows.length === 0 && (
            <div className="p-6 text-sm text-text-tertiary">{t('noData')}</div>
          )}
          {!isLoading && !isError && rows.length > 0 && (
            <table className="w-full border-separate border-spacing-y-1 text-left system-sm-regular">
              <thead className="sticky top-0 bg-background-default-subtle">
                <tr className="text-xs text-text-tertiary">
                  <th className="px-3 py-2 font-medium">{t('colTime')}</th>
                  <th className="px-2 py-2 font-medium">{t('colType')}</th>
                  <th className="px-2 py-2 font-medium">{t('colAction')}</th>
                  <th className="px-2 py-2 font-medium">{t('colStatus')}</th>
                  <th className="px-2 py-2 font-medium">{t('colUser')}</th>
                  <th className="px-2 py-2 font-medium">{t('colDepartment')}</th>
                  <th className="px-2 py-2 font-medium">{t('colResource')}</th>
                  <th className="px-2 py-2 font-medium">{t('colIp')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="rounded-l-lg bg-background-section-burn px-3 py-2 whitespace-nowrap text-text-secondary">
                      {row.created_at ? new Date(row.created_at).toLocaleString() : '-'}
                    </td>
                    <td className="bg-background-section-burn px-2 py-2 text-text-primary">
                      {t(typeLabelKey(row.log_type))}
                    </td>
                    <td className="max-w-48 truncate bg-background-section-burn px-2 py-2 text-text-primary">
                      {row.action}
                    </td>
                    <td className="bg-background-section-burn px-2 py-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs ${
                          row.status === 'success'
                            ? 'bg-components-badge-status-light-success-halo text-text-success'
                            : 'bg-components-badge-status-light-error-halo text-text-destructive'
                        }`}
                      >
                        {row.status === 'success' ? t('statusSuccess') : t('statusFailure')}
                      </span>
                    </td>
                    <td className="max-w-48 truncate bg-background-section-burn px-2 py-2 text-text-secondary">
                      {row.user_name ??
                        (row.user_type === 'account' && row.user_id
                          ? memberById.get(row.user_id)?.name ||
                            memberById.get(row.user_id)?.email ||
                            t(userTypeLabelKey('account'))
                          : row.user_type
                            ? t(userTypeLabelKey(row.user_type))
                            : '-')}
                    </td>
                    <td className="max-w-48 truncate bg-background-section-burn px-2 py-2 text-text-secondary">
                      {row.department_names?.length
                        ? row.department_names.join(' / ')
                        : '-'}
                    </td>
                    <td className="max-w-48 truncate bg-background-section-burn px-2 py-2 text-text-tertiary">
                      {resourceLabel(row, datasets, departmentById, t)}
                    </td>
                    <td className="rounded-r-lg bg-background-section-burn px-2 py-2 whitespace-nowrap text-text-tertiary">
                      {row.ip ?? '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-divider-subtle px-4 py-3">
          <div className="text-xs text-text-tertiary">{t('total', { count: total })}</div>
          <div className="flex items-center gap-2">
            <div className="text-xs text-text-tertiary">{t('pageOf', { page, totalPages })}</div>
            <Button
              size="small"
              variant="secondary"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              {t('prev')}
            </Button>
            <Button
              size="small"
              variant="secondary"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              {t('next')}
            </Button>
          </div>
        </div>
      </div>
    </KBPageLayout>
  )
}
