export type KBCallStat = {
  dataset_id: string
  calls: number
}

export type UsageDimension = 'dataset' | 'user' | 'department'
export type InterfaceDimension = 'type' | 'user' | 'department'

export type UsageRankItem = {
  id: string
  name: string
  calls: number
  is_virtual?: boolean
}

export type UserUsageRankItem = UsageRankItem & {
  email: string | null
}

export type DepartmentUsageRankItem = UsageRankItem & {
  parent_id: string | null
}

export type KBCallStatResponse =
  | {
      days: number
      total_calls: number
      dimension?: UsageDimension
      data: KBCallStat[]
    }
  | {
      days: number
      total_calls: number
      dimension?: UsageDimension
      data: UserUsageRankItem[]
    }
  | {
      days: number
      total_calls: number
      grouped_calls: number
      aggregation: 'include_descendants'
      dimension?: UsageDimension
      data: DepartmentUsageRankItem[]
    }

export type KBTrendPoint = {
  bucket: string
  calls: number
}

export type KBTrendResponse = {
  days: number
  bucket: string
  data: KBTrendPoint[]
}

export type InterfaceCallResponse =
  | {
      days: number
      total_calls: number
      dimension?: InterfaceDimension
      data: Record<string, number>
    }
  | {
      days: number
      total_calls: number
      dimension?: InterfaceDimension
      data: UserUsageRankItem[]
    }
  | {
      days: number
      total_calls: number
      grouped_calls: number
      aggregation: 'include_descendants'
      dimension?: InterfaceDimension
      data: DepartmentUsageRankItem[]
    }
