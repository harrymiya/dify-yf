import { get } from '@/service/base'
import type { AuditLogListResponse, AuditLogQueryParams } from './types'

export const fetchAuditLogs = async (params: AuditLogQueryParams): Promise<AuditLogListResponse> => {
  const query = new URLSearchParams()
  if (params.log_type) query.set('log_type', params.log_type)
  if (params.action) query.set('action', params.action)
  if (params.status) query.set('status', params.status)
  if (params.resource_id) query.set('resource_id', params.resource_id)
  if (params.page && params.page > 0) query.set('page', String(params.page))
  if (params.page_size && params.page_size > 0) query.set('page_size', String(params.page_size))
  const qs = query.toString()
  return await get<AuditLogListResponse>(`/workspaces/current/audit-logs${qs ? `?${qs}` : ''}`)
}
