export type DepartmentNode = {
  id: string
  tenant_id: string
  parent_id: string | null
  name: string
  description?: string | null
  sort: number
  children: DepartmentNode[]
}

export type KBPermissionSubjectType = 'account' | 'department' | 'role'

export type KBGrant = {
  id: string
  subject_type: KBPermissionSubjectType
  subject_id: string
  resource_type: string
  resource_id: string
  action: string
  created_at: string | null
}

export type KBCreateGrantPayload = {
  subject_type: KBPermissionSubjectType
  subject_id: string
  actions: string[]
  resource_type: 'dataset' | 'document'
  resource_id: string
}

export type KBRrevokeGrantPayload = {
  subject_type: KBPermissionSubjectType
  subject_id: string
  actions?: string[]
  resource_type: 'dataset' | 'document'
  resource_id: string
}

export type DepartmentTreeResponse = {
  data: DepartmentNode[]
}

export type DepartmentMembersResponse = {
  data: string[]
}

export type GrantListResponse = {
  data: KBGrant[]
}

export type SimpleResponse = {
  result: string
  created?: number
  removed?: number
}

export type SimpleDataResponse = {
  data?: string
  result?: string
}

/**
 * Frontend display action keys mapped to the backend snake_case enum values
 * (KBPermissionAction). The object keys double as the i18n label suffix, e.g.
 * `actionDatasetPreview`, while the values are what the server accepts.
 */
export const KBActionEnum = {
  DatasetPreview: 'dataset_preview',
  DatasetReadOnly: 'dataset_readonly',
  DatasetEdit: 'dataset_edit',
  DatasetDelete: 'dataset_delete',
  DatasetRetrievalRecall: 'dataset_retrieval_recall',
  DatasetUse: 'dataset_use',
  DatasetDocumentDownload: 'dataset_document_download',
  DatasetDeleteFile: 'dataset_delete_file',
  DatasetAccessConfig: 'dataset_access_config',
  DatasetApiKeyManage: 'dataset_api_key_manage',
  DocumentRead: 'document_read',
  DocumentRetrieval: 'document_retrieval',
  DocumentEdit: 'document_edit',
  DocumentDownload: 'document_download',
  DocumentDelete: 'document_delete',
} as const

export type KBActionKey = keyof typeof KBActionEnum

/** Reverse lookup: backend snake_case value -> display action key (for i18n label). */
export const backendActionToKey = (backendValue: string): KBActionKey | undefined => {
  const found = Object.entries(KBActionEnum).find(([, v]) => v === backendValue)
  return found?.[0] as KBActionKey | undefined
}
