'use client'

import type { InterfaceCallResponse, KBCallStatResponse, KBTrendResponse } from './types'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { KBPageLayout } from '@/app/components/datasets/kb-page-layout'
import { fetchInterfaceCalls, fetchKBCallStats, fetchKBTrend } from './services'

const DAY_OPTIONS = [7, 30, 90]

const cap = (value: string): string => {
  if (!value) return value
  return (
    value.charAt(0).toUpperCase() +
    value.slice(1).replace(/_(\w)/g, (_m, c: string) => c.toUpperCase())
  )
}

export default function UsageStatisticsPage() {
  const { t: rawT } = useTranslation('usageStatistics')
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string
  const [days, setDays] = useState(30)

  const {
    data: kbStats,
    isLoading: kbLoading,
    isError: kbError,
    refetch: refetchKb,
  } = useQuery<KBCallStatResponse>({
    queryKey: ['usage-statistics', 'kb-calls', days],
    queryFn: () => fetchKBCallStats(days),
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
    queryKey: ['usage-statistics', 'interfaces', days],
    queryFn: () => fetchInterfaceCalls(days),
  })

  const maxTrend = useMemo(
    () => Math.max(1, ...(trend?.data ?? []).map((point) => point.calls)),
    [trend],
  )

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
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* KB top calls */}
        <div className="rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-text-primary">{t('kbTopTitle')}</span>
            {kbStats && (
              <span className="text-xl font-semibold text-text-primary">{kbStats.total_calls}</span>
            )}
          </div>
          {kbLoading && <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>}
          {kbError && (
            <button
              type="button"
              className="py-4 text-sm text-text-destructive"
              onClick={() => refetchKb()}
            >
              {t('loadError')}
            </button>
          )}
          {!kbLoading && !kbError && (kbStats?.data.length === 0 || !kbStats) && (
            <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
          )}
          {!kbLoading && !kbError && kbStats && kbStats.data.length > 0 && (
            <ul className="flex flex-col divide-y divide-divider-subtle">
              {kbStats.data.map((item, index) => (
                <li key={item.dataset_id} className="flex items-center gap-3 py-2">
                  <span className="w-5 shrink-0 text-xs text-text-tertiary">{index + 1}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-text-primary">
                    {item.dataset_id}
                  </span>
                  <span className="shrink-0 text-sm font-medium text-text-secondary">
                    {item.calls}
                  </span>
                </li>
              ))}
            </ul>
          )}
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
              {/* simple bar chart */}
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
            <span className="text-sm font-medium text-text-primary">{t('interfaceTitle')}</span>
            {interfaces && (
              <span className="text-xl font-semibold text-text-primary">
                {interfaces.total_calls}
              </span>
            )}
          </div>
          {ifaceLoading && <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>}
          {ifaceError && (
            <button
              type="button"
              className="py-4 text-sm text-text-destructive"
              onClick={() => refetchIface()}
            >
              {t('loadError')}
            </button>
          )}
          {!ifaceLoading &&
            !ifaceError &&
            interfaces &&
            Object.keys(interfaces.data).length === 0 && (
              <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
            )}
          {!ifaceLoading &&
            !ifaceError &&
            interfaces &&
            Object.keys(interfaces.data).length > 0 && (
              <ul className="flex flex-col divide-y divide-divider-subtle">
                {Object.entries(interfaces.data).map(([eventType, count]) => (
                  <li key={eventType} className="flex items-center justify-between py-2">
                    <span className="text-sm text-text-primary">{t(`type${cap(eventType)}`)}</span>
                    <span className="text-sm font-medium text-text-secondary">{count}</span>
                  </li>
                ))}
              </ul>
            )}
        </div>
      </div>
    </KBPageLayout>
  )
}
