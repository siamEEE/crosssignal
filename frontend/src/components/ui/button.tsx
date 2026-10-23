import { cva, type VariantProps } from 'class-variance-authority'
import { Slot } from 'radix-ui'
import type * as React from 'react'
import { cn } from '@/lib/utils'

// shadcn/ui-style button, restyled for Culture Radio.
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold transition-all duration-150 select-none disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-4 [&_svg]:shrink-0 cursor-pointer',
  {
    variants: {
      variant: {
        primary:
          'bg-ink text-ivory shadow-[4px_4px_0_var(--color-lime)] hover:-translate-y-0.5 hover:shadow-[6px_6px_0_var(--color-lime)] active:translate-y-0 active:shadow-[2px_2px_0_var(--color-lime)]',
        accent:
          'bg-lime text-ink border-2 border-ink shadow-[3px_3px_0_var(--color-ink)] hover:-translate-y-0.5 hover:shadow-[5px_5px_0_var(--color-ink)] active:translate-y-0 active:shadow-[1px_1px_0_var(--color-ink)]',
        outline:
          'border-2 border-ink bg-ivory text-ink hover:bg-ink hover:text-ivory',
        ghost: 'text-ink hover:bg-ink/8',
        quiet: 'text-muted hover:text-ink underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-8 rounded-full px-3 text-xs',
        md: 'h-10 rounded-full px-4 text-sm',
        lg: 'h-13 rounded-full px-6 text-base',
        icon: 'size-9 rounded-full',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

export function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<'button'> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : 'button'
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />
}
