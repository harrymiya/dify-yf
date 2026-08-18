'use client'

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import DepartmentPanel from './department-panel'
import GrantPanel from './grant-panel'

export default function KBPermission() {
  const { t } = useTranslation('datasetPermission')
  const [tab, setTab] = useState<'departments' | 'grants'>('departments')

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 p-4">
      <div>
        <div className="text-[18px]/[21.6px] font-semibold text-text-primary">{t('title')}</div>
        <div className="mt-1 max-w-2xl text-sm text-text-tertiary">{t('desc')}</div>
      </div>
      <div className="flex gap-1 border-b border-divider-subtle">
        <button
          type="button"
          onClick={() => setTab('departments')}
          className={`rounded-t-lg px-4 py-2 text-sm font-medium ${
            tab === 'departments'
              ? 'border-b-2 border-state-accent-solid text-text-primary'
              : 'text-text-tertiary hover:text-text-secondary'
          }`}
          data-testid="tab-departments"
        >
          {t('departmentTab')}
        </button>
        <button
          type="button"
          onClick={() => setTab('grants')}
          className={`rounded-t-lg px-4 py-2 text-sm font-medium ${
            tab === 'grants' ? 'border-b-2 border-state-accent-solid text-text-primary' : 'text-text-tertiary hover:text-text-secondary'
          }`}
          data-testid="tab-grants"
        >
          {t('grantTab')}
        </button>
      </div>
      <div className="min-h-0 flex-1">
        {tab === 'departments' ? <DepartmentPanel /> : <GrantPanel />}
      </div>
    </div>
  )
}
