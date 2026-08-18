'use client'

import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchInterfaceCalls, fetchKBCallStats, fetchKBTrend } from './services'
import type { InterfaceCallResponse, KBCallStatResponse, KBTrendResponse } from './types'

const DAY_OPTIONS = [7, 30, 90]

export default function UsageStatisticsPage() {
  const { t } = useTranslation('usageStatistics')
  const [days, setDays] = useState(30)

  const { data: kbStats, isLoading: kbLoading, isError: kbError, refetch: refetchKb } = useQuery<KBCallStatResponse>({
    queryKey: ['usage-statistics', 'kb-calls', days],
    queryFn: () => fetchKBCallStats(days),
  })

  const { data: trend, isLoading: trendLoading, isError: trendError, refetch: refetchTrend } = useQuery<KBTrendResponse>({
    queryKey: ['usage-statistics', 'kb-trend', days],
    queryFn: () => fetchKBTrend(days),
  })

  const { data: interfaces, isLoading: ifaceLoading, isError: ifaceError, refetch: refetchIface } = useQuery<InterfaceCallResponse>({
    queryKey: ['usage-statistics', 'interfaces', days],
    queryFn: () => fetchInterfaceCalls(days),
  })

  const maxTrend = useMemo(
    () => Math.max(1, ...(trend?.data ?? []).map((point) => point.calls)),
    [trend],
  )

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[18px]/[21.6px] font-semibold text-text-primary">{t('title')}</div>
          <div className="mt-1 max-w-2xl text-sm text-text-tertiary">{t('desc')}</div>
        </div>
        <div className="flex items-center gap-1 rounded-lg bg-background-section-burn p-1">
          {DAY_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setDays(option)}
              className={`rounded-md px-3 py-1 text-sm ${
                days === option ? 'bg-background-default text-text-primary shadow-xs' : 'text-text-tertiary hover:text-text-secondary'
              }`}
              aria-pressed={days === option}
              data-testid={`days-${option}`}
            >
              {t(`days${option}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* KB top calls */}
        <div className="rounded-xl bg-background-section-burn p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-text-primary">{t('kbTopTitle')}</span>
            {kbStats && <span className="text-xl font-semibold text-text-primary">{kbStats.total_calls}</span>}
          </div>
          {kbLoading && <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>}
          {kbError && (
            <button type="button" className="py-4 text-sm text-text-destructive" onClick={() => refetchKb()}>
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
                  <span className="min-w-0 flex-1 truncate text-sm text-text-primary">{item.dataset_id}</span>
                  <span className="shrink-0 text-sm font-medium text-text-secondary">{item.calls}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* trend */}
        <div className="rounded-xl bg-background-section-burn p-4">
          <div className="mb-3 text-sm font-medium text-text-primary">{t('kbTrendTitle')}</div>
          {trendLoading && <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>}
          {trendError && (
            <button type="button" className="py-4 text-sm text-text-destructive" onClick={() => refetchTrend()}>
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
                {trend.data.length ? trend.data[0].bucket : ''} – {trend.data.length ? trend.data[trend.data.length - 1].bucket : ''}
              </div>
            </div>
          )}
        </div>

        {/* interface calls */}
        <div className="rounded-xl bg-background-section-burn p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-text-primary">{t('interfaceTitle')}</span>
            {interfaces && <span className="text-xl font-semibold text-text-primary">{interfaces.total_calls}</span>}
          </div>
          {ifaceLoading && <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>}
          {ifaceError && (
            <button type="button" className="py-4 text-sm text-text-destructive" onClick={() => refetchIface()}>
              {t('loadError')}
            </button>
          )}
          {!ifaceLoading && !ifaceError && interfaces && Object.keys(interfaces.data).length === 0 && (
            <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
          )}
          {!ifaceLoading && !ifaceError && interfaces && Object.keys(interfaces.data).length > 0 && (
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
    </div>
  )
}

const cap = (value: string): string => {
  if (!value) return value
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_(\w)/g, (_m, c: string) => c.toUpperCase())
}
