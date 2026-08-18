import type {
  DepartmentMembersResponse,
  DepartmentNode,
  DepartmentTreeResponse,
  GrantListResponse,
  KBCreateGrantPayload,
  KBRrevokeGrantPayload,
  SimpleDataResponse,
  SimpleResponse,
} from './types'
// oxlint-disable-next-line no-restricted-imports -- feature endpoints are not generated yet.
import { del, get, patch, post } from '@/service/base'

const DEPARTMENT_API = '/workspaces/current/departments'
const GRANT_API = '/workspaces/current/kb-permission-grants'

export const fetchDepartmentTree = async (): Promise<DepartmentNode[]> => {
  const resp = await get<DepartmentTreeResponse>(DEPARTMENT_API)
  return resp.data ?? []
}

export const createDepartment = async (payload: {
  name: string
  parent_id?: string | null
  sort?: number
}): Promise<string> => {
  const resp = await post<SimpleDataResponse>(DEPARTMENT_API, {
    body: {
      name: payload.name,
      parent_id: payload.parent_id ?? undefined,
      sort: payload.sort ?? 0,
    },
  })
  return resp.data ?? ''
}

export const updateDepartment = async (
  departmentId: string,
  payload: { name?: string; parent_id?: string | null; sort?: number },
): Promise<void> => {
  await patch<SimpleResponse>(`${DEPARTMENT_API}/${departmentId}`, {
    body: {
      name: payload.name,
      parent_id:
        payload.parent_id === null || payload.parent_id === undefined
          ? undefined
          : payload.parent_id,
      sort: payload.sort,
    },
  })
}

export const deleteDepartment = async (departmentId: string): Promise<void> => {
  await del<SimpleResponse>(`${DEPARTMENT_API}/${departmentId}`)
}

export const fetchDepartmentMembers = async (departmentId: string): Promise<string[]> => {
  const resp = await get<DepartmentMembersResponse>(`${DEPARTMENT_API}/${departmentId}/members`)
  return resp.data ?? []
}

export const addDepartmentMembers = async (
  departmentId: string,
  accountIds: string[],
): Promise<void> => {
  await post<SimpleResponse>(`${DEPARTMENT_API}/${departmentId}/members`, {
    body: { account_ids: accountIds },
  })
}

export const fetchGrants = async (
  resourceType: string,
  resourceId?: string,
): Promise<GrantListResponse> => {
  return await get<GrantListResponse>(GRANT_API, {
    params: {
      resource_type: resourceType,
      ...(resourceId ? { resource_id: resourceId } : {}),
    },
  })
}

export const createGrant = async (payload: KBCreateGrantPayload): Promise<number> => {
  const resp = await post<SimpleResponse>(GRANT_API, { body: payload })
  return resp.created ?? 0
}

export const revokeGrant = async (payload: KBRrevokeGrantPayload): Promise<number> => {
  const resp = await post<SimpleResponse>(`${GRANT_API}/revoke`, { body: payload })
  return resp.removed ?? 0
}
