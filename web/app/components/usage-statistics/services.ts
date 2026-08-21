import type {
  InterfaceCallResponse,
  InterfaceDimension,
  KBCallStatResponse,
  KBTrendResponse,
  UsageDimension,
} from './types'
// oxlint-disable-next-line no-restricted-imports -- usage statistics endpoints are not generated yet.
import { get } from '@/service/base'

export const fetchKBCallStats = async (
  days: number,
  limit = 20,
  dimension: UsageDimension = 'dataset',
): Promise<KBCallStatResponse> => {
  const params = new URLSearchParams({ days: String(days), limit: String(limit), dimension })
  return await get<KBCallStatResponse>(
    `/workspaces/current/statistics/knowledge-base/calls?${params.toString()}`,
  )
}

export const fetchKBTrend = async (days: number, bucket = 'day'): Promise<KBTrendResponse> => {
  const params = new URLSearchParams({ days: String(days), bucket })
  return await get<KBTrendResponse>(
    `/workspaces/current/statistics/knowledge-base/trend?${params.toString()}`,
  )
}

export const fetchInterfaceCalls = async (
  days: number,
  dimension: InterfaceDimension = 'type',
  limit = 20,
): Promise<InterfaceCallResponse> => {
  const params = new URLSearchParams({ days: String(days), dimension, limit: String(limit) })
  return await get<InterfaceCallResponse>(
    `/workspaces/current/statistics/interfaces/calls?${params.toString()}`,
  )
}
