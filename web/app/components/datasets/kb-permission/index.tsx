'use client'

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { KBPageLayout } from '../kb-page-layout'
import DepartmentPanel from './department-panel'
import GrantPanel from './grant-panel'

export default function KBPermission() {
  const { t: rawT } = useTranslation('datasetPermission')
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string
  const [tab, setTab] = useState<'departments' | 'grants'>('departments')

  return (
    <KBPageLayout title={t('title')} description={t('desc')}>
      <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-lg border-[0.5px] border-components-panel-border bg-components-panel-bg shadow-xs shadow-shadow-shadow-3">
        <div className="flex shrink-0 gap-1 border-b border-divider-subtle px-4 pt-3">
          <button
            type="button"
            onClick={() => setTab('departments')}
            className={`border-b-2 px-3 py-2 system-sm-medium ${
              tab === 'departments'
                ? 'border-state-accent-solid text-text-primary'
                : 'border-transparent text-text-tertiary hover:text-text-secondary'
            }`}
            data-testid="tab-departments"
          >
            {t('departmentTab')}
          </button>
          <button
            type="button"
            onClick={() => setTab('grants')}
            className={`border-b-2 px-3 py-2 system-sm-medium ${
              tab === 'grants'
                ? 'border-state-accent-solid text-text-primary'
                : 'border-transparent text-text-tertiary hover:text-text-secondary'
            }`}
            data-testid="tab-grants"
          >
            {t('grantTab')}
          </button>
        </div>
        <div className="min-h-0 flex-1 bg-background-default-subtle p-4">
          {tab === 'departments' ? <DepartmentPanel /> : <GrantPanel />}
        </div>
      </div>
    </KBPageLayout>
  )
}
