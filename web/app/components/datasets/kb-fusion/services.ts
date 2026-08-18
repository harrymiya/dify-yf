import { post } from '@/service/base'
import type { FusionRetrieveParams, FusionRetrieveResponse } from './types'

export const fetchFusionRetrieve = async (
  params: FusionRetrieveParams,
): Promise<FusionRetrieveResponse> => {
  return await post<FusionRetrieveResponse>('/workspaces/current/kb-fusion/retrieve', {
    body: {
      query: params.query,
      top_k: params.top_k ?? 10,
      ...(params.score_threshold !== undefined ? { score_threshold: params.score_threshold } : {}),
      strategy: params.strategy ?? 'rrf',
      ...(params.dataset_ids && params.dataset_ids.length > 0
        ? { dataset_ids: params.dataset_ids }
        : {}),
    },
  })
}
