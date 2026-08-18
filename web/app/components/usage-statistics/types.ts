export type KBCallStat = {
  dataset_id: string
  calls: number
}

export type KBCallStatResponse = {
  days: number
  total_calls: number
  data: KBCallStat[]
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

export type InterfaceCallResponse = {
  days: number
  total_calls: number
  data: Record<string, number>
}
