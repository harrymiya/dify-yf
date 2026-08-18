export type DepartmentNode = {
  id: string
  tenant_id: string
  parent_id: string | null
  name: string
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
