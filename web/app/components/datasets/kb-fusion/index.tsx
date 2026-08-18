'use client'

import { Button } from '@langgenius/dify-ui/button'
import { Input } from '@langgenius/dify-ui/input'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchFusionRetrieve } from './services'
import type { FusionRecord, FusionStrategy } from './types'

const STRATEGIES: FusionStrategy[] = ['rrf', 'max', 'sum']

const strategyLabelKey: Record<FusionStrategy, string> = {
  rrf: 'strategyRRF',
  max: 'strategyMax',
  sum: 'strategySum',
}

export default function KBFusionSearch() {
  const { t } = useTranslation('datasetFusion')
  const [query, setQuery] = useState('')
  const [strategy, setStrategy] = useState<FusionStrategy>('rrf')
  const [result, setResult] = useState<{ datasets: number; records: FusionRecord[] } | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const runSearch = async (q: string) => {
    abortRef.current?.abort()
    setError(false)
    if (!q.trim()) {
      setResult(null)
      return
    }
    setIsLoading(true)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const data = await fetchFusionRetrieve({ query: q.trim(), strategy })
      if (!controller.signal.aborted) setResult(data)
    } catch {
      if (!controller.signal.aborted) setError(true)
    } finally {
      if (!controller.signal.aborted) setIsLoading(false)
    }
  }

  const handleSearch = () => {
    void runSearch(query)
  }

  const records = result?.records ?? []
  const hasSearched = result !== null

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-4">
      <div>
        <div className="text-[18px]/[21.6px] font-semibold text-text-primary">{t('title')}</div>
        <div className="mt-1 max-w-2xl text-sm text-text-tertiary">{t('desc')}</div>
      </div>

      {/* search bar */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSearch()
          }}
          placeholder={t('searchPlaceholder')}
          aria-label={t('inputLabel')}
          className="w-96"
          data-testid="fusion-search-input"
        />
        <Button size="medium" variant="primary" onClick={handleSearch} data-testid="fusion-search-button">
          {t('searchButton')}
        </Button>
        <select
          value={strategy}
          onChange={(e) => setStrategy(e.target.value as FusionStrategy)}
          aria-label={t('strategy')}
          className="h-9 rounded-lg border border-divider-regular bg-background-default px-2 text-sm text-text-primary"
          data-testid="fusion-strategy"
        >
          {STRATEGIES.map((s) => (
            <option key={s} value={s}>
              {t(strategyLabelKey[s])}
            </option>
          ))}
        </select>
      </div>

      {/* results */}
      <div className="min-h-0 flex-1 overflow-auto">
        {isLoading && <div className="p-4 text-sm text-text-tertiary">{t('loading')}</div>}
        {!isLoading && error && (
          <div className="flex items-center gap-3 p-4">
            <span className="text-sm text-text-destructive">{t('searchError')}</span>
            <Button size="small" variant="secondary" onClick={handleSearch}>
              {t('retry')}
            </Button>
          </div>
        )}
        {!isLoading && !error && !hasSearched && (
          <div className="p-4 text-sm text-text-tertiary">{t('noQuery')}</div>
        )}
        {!isLoading && !error && hasSearched && records.length === 0 && (
          <div className="p-4 text-sm text-text-tertiary">
            {result && result.datasets === 0 ? t('noAccess') : t('noResults')}
          </div>
        )}
        {!isLoading && !error && records.length > 0 && (
          <>
            <div className="px-4 pb-2 text-xs text-text-tertiary">
              {t('resultCount', { count: records.length, datasets: result?.datasets ?? 0 })}
            </div>
            <div className="flex flex-col gap-3 px-4 pb-4">
              {records.map((record, index) => (
                <article
                  key={`${record.document_id}:${index}`}
                  className="rounded-xl border border-divider-regular bg-background-section-burn p-4"
                  data-testid="fusion-record"
                >
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <h3 className="min-w-0 flex-1 truncate text-sm font-medium text-text-primary">
                      {record.title || t('unknownTitle')}
                    </h3>
                    <span className="shrink-0 text-xs text-text-tertiary">
                      {t('score')}: {record.score.toFixed(4)}
                    </span>
                  </div>
                  <div className="text-sm leading-relaxed text-text-secondary">{record.content}</div>
                  <div className="mt-2 text-xs text-text-tertiary">
                    {t('sourceLabel')}: {record.dataset_id}
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
