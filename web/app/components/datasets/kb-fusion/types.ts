export type FusionStrategy = 'rrf' | 'max' | 'sum'

export type FusionRecord = {
  dataset_id: string
  document_id: string
  title: string | null
  content: string
  score: number
  metadata: Record<string, unknown>
}

export type FusionRetrieveResponse = {
  query: string
  datasets: number
  strategy: FusionStrategy
  records: FusionRecord[]
}

export type FusionRetrieveParams = {
  query: string
  top_k?: number
  score_threshold?: number
  strategy?: FusionStrategy
  dataset_ids?: string[]
}
