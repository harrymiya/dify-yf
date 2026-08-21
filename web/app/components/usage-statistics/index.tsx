'use client'

import type { EChartsOption } from 'echarts'
import type { ReactNode } from 'react'
import type {
  DepartmentUsageRankItem,
  InterfaceCallResponse,
  KBCallStatResponse,
  KBTrendResponse,
  UserUsageRankItem,
} from './types'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { KBPageLayout } from '@/app/components/datasets/kb-page-layout'
import { fetchDatasets } from '@/service/datasets'
import { fetchInterfaceCalls, fetchKBCallStats, fetchKBTrend } from './services'

const DAY_OPTIONS = [7, 30, 90]

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
        {showEmail && 'email' in item && item.email && (
          <span className="block truncate text-xs text-text-tertiary">{item.email}</span>
        )}
      </span>
      <span className="shrink-0 text-sm font-medium text-text-secondary">{item.calls}</span>
    </li>
  )
}

function StatCard({
  title,
  value,
  children,
}: {
  title: string
  value?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="flex h-full min-h-[240px] flex-col rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
      <div className="mb-3 flex shrink-0 items-center justify-between">
        <span className="text-sm font-medium text-text-primary">{title}</span>
        {value !== undefined && (
          <span className="text-xl font-semibold text-text-primary">{value}</span>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </div>
  )
}

export default function UsageStatisticsPage() {
  const { t: rawT } = useTranslation('usageStatistics')
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string
  const [days, setDays] = useState(30)

  const {
    data: kbDataset,
    isLoading: kbDatasetLoading,
    isError: kbDatasetError,
    refetch: refetchKbDataset,
  } = useQuery<KBCallStatResponse>({
    queryKey: ['usage-statistics', 'kb-calls', days, 'dataset'],
    queryFn: () => fetchKBCallStats(days, 20, 'dataset'),
  })

  const {
    data: kbUsers,
    isLoading: kbUsersLoading,
    isError: kbUsersError,
    refetch: refetchKbUsers,
  } = useQuery<KBCallStatResponse>({
    queryKey: ['usage-statistics', 'kb-calls', days, 'user'],
    queryFn: () => fetchKBCallStats(days, 20, 'user'),
  })

  const {
    data: kbDepartments,
    isLoading: kbDeptLoading,
    isError: kbDeptError,
    refetch: refetchKbDept,
  } = useQuery<KBCallStatResponse>({
    queryKey: ['usage-statistics', 'kb-calls', days, 'department'],
    queryFn: () => fetchKBCallStats(days, 20, 'department'),
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
    data: ifaceType,
    isLoading: ifaceTypeLoading,
    isError: ifaceTypeError,
    refetch: refetchIfaceType,
  } = useQuery<InterfaceCallResponse>({
    queryKey: ['usage-statistics', 'interfaces', days, 'type'],
    queryFn: () => fetchInterfaceCalls(days, 'type', 20),
  })

  const {
    data: ifaceUsers,
    isLoading: ifaceUsersLoading,
    isError: ifaceUsersError,
    refetch: refetchIfaceUsers,
  } = useQuery<InterfaceCallResponse>({
    queryKey: ['usage-statistics', 'interfaces', days, 'user'],
    queryFn: () => fetchInterfaceCalls(days, 'user', 20),
  })

  const {
    data: ifaceDepartments,
    isLoading: ifaceDeptLoading,
    isError: ifaceDeptError,
    refetch: refetchIfaceDept,
  } = useQuery<InterfaceCallResponse>({
    queryKey: ['usage-statistics', 'interfaces', days, 'department'],
    queryFn: () => fetchInterfaceCalls(days, 'department', 20),
  })

  const trendOption = useMemo<EChartsOption>(() => {
    const buckets = (trend?.data ?? []).map((point) => point.bucket)
    const calls = (trend?.data ?? []).map((point) => point.calls)
    return {
      grid: { left: 8, right: 16, top: 16, bottom: 0, containLabel: true },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: buckets,
        axisLine: { lineStyle: { color: 'var(--color-dividers-divider2)' } },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 12 },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'var(--color-dividers-divider2)' } },
        axisLabel: { color: 'var(--color-text-tertiary)', fontSize: 12 },
      },
      series: [
        {
          type: 'bar',
          data: calls,
          barWidth: 16,
          itemStyle: {
            color: 'var(--color-state-accent-solid)',
            borderRadius: [4, 4, 0, 0],
          },
        },
      ],
    }
  }, [trend])

  const { data: datasetPage } = useQuery({
    queryKey: ['usage-statistics', 'datasets'],
    queryFn: () => fetchDatasets({ url: '/datasets', params: { limit: 100, page: 1 } }),
  })
  const datasetNameById = useMemo(
    () => new Map((datasetPage?.data ?? []).map((d) => [d.id, d.name])),
    [datasetPage],
  )

  const renderKbDatasetBody = () => {
    if (kbDatasetLoading)
      return <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>
    if (kbDatasetError) {
      return (
        <button
          type="button"
          className="py-4 text-sm text-text-destructive"
          onClick={() => refetchKbDataset()}
        >
          {t('loadError')}
        </button>
      )
    }
    const data = kbDataset?.data ?? []
    if (!Array.isArray(data) || data.length === 0) {
      return <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
    }
    return (
      <ul className="flex flex-col divide-y divide-divider-subtle">
        {data.map((item, index) => {
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

  const renderKbRankBody = (
    stats: KBCallStatResponse | undefined,
    loading: boolean,
    error: boolean,
    refetch: () => void,
    showEmail: boolean,
  ) => {
    if (loading) return <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>
    if (error) {
      return (
        <button type="button" className="py-4 text-sm text-text-destructive" onClick={refetch}>
          {t('loadError')}
        </button>
      )
    }
    const data = (stats?.data ?? []) as RankItem[]
    if (data.length === 0)
      return <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
    return (
      <ul className="flex flex-col divide-y divide-divider-subtle">
        {data.map((item, index) => (
          <RankRow key={item.id} item={item} index={index} showEmail={showEmail} />
        ))}
      </ul>
    )
  }

  const renderIfaceTypeBody = () => {
    if (ifaceTypeLoading)
      return <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>
    if (ifaceTypeError) {
      return (
        <button
          type="button"
          className="py-4 text-sm text-text-destructive"
          onClick={() => refetchIfaceType()}
        >
          {t('loadError')}
        </button>
      )
    }
    const data = (ifaceType?.data ?? {}) as Record<string, number>
    if (Object.keys(data).length === 0) {
      return <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
    }
    return (
      <ul className="flex flex-col divide-y divide-divider-subtle">
        {Object.entries(data).map(([eventType, count]) => (
          <li key={eventType} className="flex items-center justify-between py-2">
            <span className="text-sm text-text-primary">{t(`type${cap(eventType)}`)}</span>
            <span className="text-sm font-medium text-text-secondary">{count}</span>
          </li>
        ))}
      </ul>
    )
  }

  const renderIfaceRankBody = (
    stats: InterfaceCallResponse | undefined,
    loading: boolean,
    error: boolean,
    refetch: () => void,
    showEmail: boolean,
  ) => {
    if (loading) return <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>
    if (error) {
      return (
        <button type="button" className="py-4 text-sm text-text-destructive" onClick={refetch}>
          {t('loadError')}
        </button>
      )
    }
    const data = (stats?.data ?? []) as RankItem[]
    if (data.length === 0)
      return <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
    return (
      <ul className="flex flex-col divide-y divide-divider-subtle">
        {data.map((item, index) => (
          <RankRow key={item.id} item={item} index={index} showEmail={showEmail} />
        ))}
      </ul>
    )
  }

  const renderTrendBody = () => {
    if (trendLoading) return <div className="py-4 text-sm text-text-tertiary">{t('loading')}</div>
    if (trendError) {
      return (
        <button
          type="button"
          className="py-4 text-sm text-text-destructive"
          onClick={() => refetchTrend()}
        >
          {t('loadError')}
        </button>
      )
    }
    if (!trend || trend.data.length === 0) {
      return <div className="py-4 text-sm text-text-tertiary">{t('noData')}</div>
    }
    return (
      <div className="h-full w-full">
        <ReactECharts
          option={trendOption}
          opts={{ renderer: 'svg' }}
          style={{ height: '100%', width: '100%' }}
        />
      </div>
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
      {/* trend */}
      <div className="flex h-[300px] flex-col rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg p-4 shadow-xs shadow-shadow-shadow-3">
        <div className="mb-3 shrink-0 text-sm font-medium text-text-primary">
          {t('kbTrendTitle')}
        </div>
        <div className="min-h-0 flex-1">{renderTrendBody()}</div>
      </div>

      {/* 6-grid: row 1 = KB rankings by dimension, row 2 = interface calls by dimension */}
      <div className="mt-4 grid grid-cols-1 gap-4 xl:h-[640px] xl:grid-cols-3 xl:grid-rows-2">
        <StatCard title={t('kbTopByDatasetTitle')} value={kbDataset?.total_calls}>
          {renderKbDatasetBody()}
        </StatCard>
        <StatCard title={t('kbTopByUserTitle')} value={kbUsers?.total_calls}>
          {renderKbRankBody(kbUsers, kbUsersLoading, kbUsersError, () => refetchKbUsers(), true)}
        </StatCard>
        <StatCard title={t('kbTopByDepartmentTitle')} value={kbDepartments?.total_calls}>
          {renderKbRankBody(
            kbDepartments,
            kbDeptLoading,
            kbDeptError,
            () => refetchKbDept(),
            false,
          )}
        </StatCard>

        <StatCard title={t('interfaceTitle')} value={ifaceType?.total_calls}>
          {renderIfaceTypeBody()}
        </StatCard>
        <StatCard title={t('interfaceByUserTitle')} value={ifaceUsers?.total_calls}>
          {renderIfaceRankBody(
            ifaceUsers,
            ifaceUsersLoading,
            ifaceUsersError,
            () => refetchIfaceUsers(),
            true,
          )}
        </StatCard>
        <StatCard title={t('interfaceByDepartmentTitle')} value={ifaceDepartments?.total_calls}>
          {renderIfaceRankBody(
            ifaceDepartments,
            ifaceDeptLoading,
            ifaceDeptError,
            () => refetchIfaceDept(),
            false,
          )}
        </StatCard>
      </div>
    </KBPageLayout>
  )
}
