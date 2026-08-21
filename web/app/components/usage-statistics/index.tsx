'use client'

import type {
  DepartmentUsageRankItem,
  InterfaceCallResponse,
  InterfaceDimension,
  KBCallStatResponse,
  KBTrendResponse,
  UsageDimension,
  UserUsageRankItem,
} from './types'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { KBPageLayout } from '@/app/components/datasets/kb-page-layout'
import { fetchDatasets } from '@/service/datasets'
import { fetchInterfaceCalls, fetchKBCallStats, fetchKBTrend } from './services'

const DAY_OPTIONS = [7, 30, 90]

const DIMENSION_OPTIONS: UsageDimension[] = ['dataset', 'user', 'department']

const cap = (value: string): string => {
  if (!value) return value
  return (
    value.charAt(0).toUpperCase() +
    value.slice(1).replace(/_(\w)/g, (_m, c: string) => c.toUpperCase())
  )
}

type RankItem = (UserUsageRankItem | DepartmentUsageRankItem) & { is_virtual?: boolean }

function RankRow({
  item,
  index,
  showEmail,
}: {
  item: RankItem
  index: number
  showEmail: boolean
}) {
  return (
    <li key={item.id} className="flex items-center gap-3 py-2">
      <span className="w-5 shrink-0 text-xs text-text-tertiary">{index + 1}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm text-text-primary">{item.name}</span>
        {showEmail && item.email && (
          <span className="block truncate text-xs text-text-tertiary">{item.email}</span>
        )}
      </span>
      <span className="shrink-0 text-sm font-medium text-text-secondary">{item.calls}</span>
    </li>
  )
}

export default function UsageStatisticsPage() {
  const { t: rawT } = useTranslation('usageStatistics')
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string
  const [days, setDays] = useState(30)
  const [dimension, setDimension] = useState<UsageDimension>('dataset')

  // Interfaces use a parallel but distinct dimension vocabulary
  // (type | user | department) while KB uses dataset | user | department.
  const interfaceDimension: InterfaceDimension = dimension === 'dataset' ? 'type' : dimension

  const {
    data: kbStats,
    isLoading: kbLoading,
    isError: kbError,
    refetch: refetchKb,
  } = useQuery<KBCallStatResponse>({
    queryKey: ['usage-statistics', 'kb-calls', days, dimension],
    queryFn: () => fetchKBCallStats(days, 20, dimension),
  })

  const {
    data: trend,
    isLoading: trendLoading,
    isError: trendError,
    refetch: refetchTrend,
  } = useQuery<KBTrendResponse>({
    queryKey: ['usage-statistics', 'kb-trend', days],
    queryFn: () => fetchKBTrend(days),
  })

  const {
    data: interfaces,
    isLoading: ifaceLoading,
    isError: ifaceError,
    refetch: refetchIface,
  } = useQuery<InterfaceCallResponse>({
    queryKey: ['usage-statistics', 'interfaces', days, interfaceDimension],
    queryFn: () => fetchInterfaceCalls(days, interfaceDimension, 20),
  })

  const maxTrend = useMemo(
    () => Math.max(1, ...(trend?.data ?? []).map((point) => point.calls)),
    [trend],
  )

  const { data: datasetPage } = useQuery({
    queryKey: ['usage-statistics', 'datasets'],
    queryFn: () => fetchDatasets({ url: '/datasets', params: { limit: 100, page: 1 } }),
    enabled: dimension === 'dataset',
  })
  const datasetNameById = useMemo(
    () => new Map((datasetPage?.data ?? []).map((d) => [d.id, d.name])),
    [datasetPage],
  )

  const showIfaceRank = interfaceDimension === 'user' || interfaceDimension === 'department'
  const ifaceRankItems = (interfaces?.data ?? []) as RankItem[]
  const ifaceRankItemCount = showIfaceRank ? ifaceRankItems.length : 0

  const renderKbBody = () => {
    if (kbLoading) return <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>
    if (kbError) {
      return (
        <button
          type="button"
          className="py-4 text-sm text-text-destructive"
          onClick={() => refetchKb()}
        >
          {t('loadError')}
        </button>
      )
    }
    if (!kbStats || (Array.isArray(kbStats.data) && kbStats.data.length === 0)) {
      return <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
    }
    if (dimension === 'dataset') {
      return (
        <ul className="flex flex-col divide-y divide-divider-subtle">
          {Array.isArray(kbStats.data) &&
            kbStats.data.map((item, index) => {
              if (!('dataset_id' in item)) return null
              const dItem = item as { dataset_id: string; calls: number }
              return (
                <li key={dItem.dataset_id} className="flex items-center gap-3 py-2">
                  <span className="w-5 shrink-0 text-xs text-text-tertiary">{index + 1}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-text-primary">
                    {datasetNameById.get(dItem.dataset_id) || '-'}
                  </span>
                  <span className="shrink-0 text-sm font-medium text-text-secondary">
                    {dItem.calls}
                  </span>
                </li>
              )
            })}
        </ul>
      )
    }
    return (
      <ul className="flex flex-col divide-y divide-divider-subtle">
        {Array.isArray(kbStats.data) &&
          (kbStats.data as RankItem[]).map((item, index) => (
            <RankRow key={item.id} item={item} index={index} showEmail={dimension === 'user'} />
          ))}
      </ul>
    )
  }

  const renderIfaceBody = () => {
    if (ifaceLoading) return <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>
    if (ifaceError) {
      return (
        <button
          type="button"
          className="py-4 text-sm text-text-destructive"
          onClick={() => refetchIface()}
        >
          {t('loadError')}
        </button>
      )
    }
    if (!interfaces) return <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
    if (showIfaceRank) {
      if (ifaceRankItemCount === 0) {
        return <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
      }
      return (
        <ul className="flex flex-col divide-y divide-divider-subtle">
          {ifaceRankItems.map((item, index) => (
            <RankRow key={item.id} item={item} index={index} showEmail={dimension === 'user'} />
          ))}
        </ul>
      )
    }
    if (Object.keys(interfaces.data as Record<string, number>).length === 0) {
      return <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
    }
    return (
      <ul className="flex flex-col divide-y divide-divider-subtle">
        {Object.entries(interfaces.data as Record<string, number>).map(([eventType, count]) => (
          <li key={eventType} className="flex items-center justify-between py-2">
            <span className="text-sm text-text-primary">{t(`type${cap(eventType)}`)}</span>
            <span className="text-sm font-medium text-text-secondary">{count}</span>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <KBPageLayout
      title={t('title')}
      description={t('desc')}
      contentClassName="overflow-y-auto"
      action={
        <div className="flex items-center gap-1 rounded-lg bg-components-panel-bg p-1 shadow-xs shadow-shadow-shadow-3">
          {DAY_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setDays(option)}
              className={`rounded-md px-3 py-1.5 system-sm-medium ${
                days === option
                  ? 'bg-background-default text-text-primary shadow-xs'
                  : 'text-text-tertiary hover:text-text-secondary'
              }`}
              aria-pressed={days === option}
              data-testid={`days-${option}`}
            >
              {t(`days${option}`)}
            </button>
          ))}
        </div>
      }
    >
      <div className="mb-4 flex items-center gap-1 rounded-lg bg-components-panel-bg p-1 shadow-xs shadow-shadow-shadow-3 w-fit">
        {DIMENSION_OPTIONS.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setDimension(option)}
            className={`rounded-md px-3 py-1.5 system-sm-medium ${
              dimension === option
                ? 'bg-background-default text-text-primary shadow-xs'
                : 'text-text-tertiary hover:text-text-secondary'
            }`}
            aria-pressed={dimension === option}
            data-testid={`dimension-${option}`}
          >
            {t(`dimension${cap(option)}`)}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* KB top calls */}
        <div className="rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-text-primary">
              {t(dimension === 'dataset' ? 'kbTopTitle' : `kbTopBy${cap(dimension)}Title`)}
            </span>
            {kbStats && (
              <span className="text-xl font-semibold text-text-primary">{kbStats.total_calls}</span>
            )}
          </div>
          {renderKbBody()}
        </div>

        {/* trend */}
        <div className="rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
          <div className="mb-3 text-sm font-medium text-text-primary">{t('kbTrendTitle')}</div>
          {trendLoading && <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>}
          {trendError && (
            <button
              type="button"
              className="py-4 text-sm text-text-destructive"
              onClick={() => refetchTrend()}
            >
              {t('loadError')}
            </button>
          )}
          {!trendLoading && !trendError && (trend?.data.length === 0 || !trend) && (
            <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
          )}
          {!trendLoading && !trendError && trend && trend.data.length > 0 && (
            <div>
              <div className="flex h-36 items-end gap-0.5">
                {trend.data.map((point) => (
                  <div
                    key={point.bucket}
                    className="flex-1 rounded-t bg-state-accent-solid/80"
                    style={{ height: `${Math.max(2, (point.calls / maxTrend) * 100)}%` }}
                    title={`${point.bucket}: ${point.calls}`}
                  />
                ))}
              </div>
              <div className="mt-1 text-xs text-text-tertiary">
                {trend.data[0]?.bucket ?? ''} – {trend.data[trend.data.length - 1]?.bucket ?? ''}
              </div>
            </div>
          )}
        </div>

        {/* interface calls */}
        <div className="rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-text-primary">
              {t(showIfaceRank ? `interfaceBy${cap(dimension)}Title` : 'interfaceTitle')}
            </span>
            {interfaces && (
              <span className="text-xl font-semibold text-text-primary">
                {interfaces.total_calls}
              </span>
            )}
          </div>
          {renderIfaceBody()}
        </div>
      </div>
    </KBPageLayout>
  )
}
