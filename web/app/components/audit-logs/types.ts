export type AuditLogType = 'qna' | 'retrieval' | 'download' | 'permission_change' | 'system'
export type AuditLogStatus = 'success' | 'failure'

export type AuditLogItem = {
  id: string
  user_id: string | null
  user_type: string | null
  log_type: AuditLogType
  action: string
  status: AuditLogStatus
  resource_type: string | null
  resource_id: string | null
  detail: Record<string, unknown> | null
  ip: string | null
  request_id: string | null
  trace_id: string | null
  created_at: string | null
}

export type AuditLogListResponse = {
  data: AuditLogItem[]
  total: number
  page: number
  page_size: number
}

export type AuditLogQueryParams = {
  log_type?: string
  action?: string
  status?: string
  resource_id?: string
  page?: number
  page_size?: number
}
