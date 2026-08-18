'use client'

import type { ReactNode } from 'react'
import { cn } from '@langgenius/dify-ui/cn'
import { useTranslation } from 'react-i18next'
import Link from '@/next/link'

type KBPageLayoutProps = {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  children: ReactNode
  contentClassName?: string
}

export function KBPageLayout({
  title,
  description,
  action,
  children,
  contentClassName,
}: KBPageLayoutProps) {
  const { t } = useTranslation()

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-background-body">
      <div className="sticky top-0 z-10 flex shrink-0 flex-col gap-3 bg-background-body px-8 pt-4 pb-3">
        <Link
          href="/datasets"
          className="inline-flex h-8 w-fit items-center gap-1 rounded-lg px-1.5 system-xs-medium text-text-tertiary transition-colors hover:bg-state-base-hover hover:text-text-secondary focus-visible:ring-2 focus-visible:ring-state-accent-solid focus-visible:outline-hidden"
        >
          <span aria-hidden className="i-ri-arrow-left-line size-4 shrink-0" />
          <span>{t('operation.back' as never, { ns: 'common' })}</span>
        </Link>
        <div className="flex min-h-8 flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="truncate text-[18px]/[21.6px] font-semibold text-text-primary">
              {title}
            </h1>
            {description && (
              <p className="mt-1 max-w-2xl system-sm-regular text-text-tertiary">{description}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      </div>
      <div className={cn('min-h-0 flex-1 overflow-hidden px-8 pb-6', contentClassName)}>
        {children}
      </div>
    </div>
  )
}
