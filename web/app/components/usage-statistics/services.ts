import { get } from '@/service/base'
import type { InterfaceCallResponse, KBCallStatResponse, KBTrendResponse } from './types'

export const fetchKBCallStats = async (days: number, limit = 20): Promise<KBCallStatResponse> => {
  return await get<KBCallStatResponse>(
    `/workspaces/current/statistics/knowledge-base/calls?days=${days}&limit=${limit}`,
  )
}

export const fetchKBTrend = async (days: number, bucket = 'day'): Promise<KBTrendResponse> => {
  return await get<KBTrendResponse>(
    `/workspaces/current/statistics/knowledge-base/trend?days=${days}&bucket=${bucket}`,
  )
}

export const fetchInterfaceCalls = async (days: number): Promise<InterfaceCallResponse> => {
  return await get<InterfaceCallResponse>(
    `/workspaces/current/statistics/interfaces/calls?days=${days}`,
  )
}
