import { Tooltip as T } from 'radix-ui'
import type * as React from 'react'
import { cn } from '@/lib/utils'

export const TooltipProvider = T.Provider

export function Tooltip({
  content,
  children,
  className,
}: {
  content: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <T.Root delayDuration={150}>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content
          sideOffset={6}
          className={cn(
            'z-50 max-w-72 rounded-xl bg-ink px-3 py-2 text-xs leading-relaxed text-ivory shadow-pop',
            className,
          )}
        >
          {content}
          <T.Arrow className="fill-ink" />
        </T.Content>
      </T.Portal>
    </T.Root>
  )
}
