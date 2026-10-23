import { ToggleGroup as TG } from 'radix-ui'
import { cn } from '@/lib/utils'

/** Single-select segmented control (shadcn ToggleGroup pattern). */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: T
  onChange: (value: T) => void
  options: { value: T; label: string; hint?: string }[]
  label: string
  className?: string
}) {
  return (
    <TG.Root
      type="single"
      value={value}
      onValueChange={(v) => v && onChange(v as T)}
      aria-label={label}
      className={cn('grid gap-2 sm:grid-cols-3', className)}
    >
      {options.map((option) => (
        <TG.Item
          key={option.value}
          value={option.value}
          className="discovery-mode group rounded-2xl border-2 border-ink/15 bg-ivory px-4 py-3 text-left transition-all hover:border-ink data-[state=on]:border-ink data-[state=on]:bg-ink data-[state=on]:text-ivory cursor-pointer"
        >
          <span className="block font-semibold">{option.label}</span>
          {option.hint && (
            <span className="mt-0.5 block text-xs text-muted group-data-[state=on]:text-ivory/70">
              {option.hint}
            </span>
          )}
        </TG.Item>
      ))}
    </TG.Root>
  )
}
