'use client'

import type { AuditLogType } from './types'
import { Button } from '@langgenius/dify-ui/button'
import { Input } from '@langgenius/dify-ui/input'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { KBPageLayout } from '@/app/components/datasets/kb-page-layout'
import { fetchAuditLogs } from './services'

const TYPE_ORDER: AuditLogType[] = ['qna', 'retrieval', 'download', 'permission_change', 'system']

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
  const [applied, setApplied] = useState({ logType: '', action: '', status: '', resourceId: '' })
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
        page,
        page_size: pageSize,
      }),
  })

  const applyFilters = () => {
    setApplied({ logType, action, status, resourceId })
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
              setApplied({ logType: '', action: '', status: '', resourceId: '' })
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
                      {row.user_type ? t(userTypeLabelKey(row.user_type)) : ''} {row.user_id ?? ''}
                    </td>
                    <td className="max-w-48 truncate bg-background-section-burn px-2 py-2 text-text-tertiary">
                      {row.resource_id ?? '-'}
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
