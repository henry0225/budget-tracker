import { Calendar, CreditCard, Repeat, Tag, TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react'
import { catColor } from '../../constants'
import { fmtCurrency, fmtDollar } from '../../lib/format'
import type { InsightItem } from '../../types'

// ── Shared primitives ──────────────────────────────────────────────────────────

function CardShell({ wide, children }: { wide?: boolean; children: React.ReactNode }) {
  return (
    <div
      className={`rounded-xl border border-zinc-800 bg-zinc-900 p-5 transition-colors hover:border-zinc-700${wide ? ' sm:col-span-2' : ''}`}
    >
      {children}
    </div>
  )
}

function CardHeader({ Icon, title }: { Icon: LucideIcon; title: string }) {
  return (
    <div className="mb-4 flex items-center gap-2.5">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-zinc-800">
        <Icon className="h-3.5 w-3.5 text-zinc-400" />
      </div>
      <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">{title}</p>
    </div>
  )
}

// ── Card variants ──────────────────────────────────────────────────────────────

interface CatData {
  all_cats: { category: string; amount: number; pct: number }[]
  category: string
  pct: number
}

function TopCategoryCard({ title, data }: InsightItem) {
  const d = data as unknown as CatData
  return (
    <CardShell wide>
      <CardHeader Icon={Tag} title={title} />
      {/* Proportional stacked bar */}
      <div className="flex h-3 gap-px overflow-hidden rounded-full">
        {d.all_cats.map((cat) => (
          <div
            key={cat.category}
            className="h-full shrink-0"
            style={{ width: `${cat.pct}%`, background: catColor(cat.category) }}
          />
        ))}
      </div>
      {/* Legend */}
      <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-2.5 sm:grid-cols-3">
        {d.all_cats.map((cat) => (
          <div key={cat.category} className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: catColor(cat.category) }}
              />
              <span className="truncate text-sm text-zinc-400">{cat.category}</span>
            </div>
            <span className="shrink-0 tabular-nums text-xs text-zinc-500">{cat.pct.toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </CardShell>
  )
}

interface DowData {
  days: { day: string; amount: number; count: number }[]
  peak_day: string
}

const BAR_MAX_PX = 52

function DayOfWeekCard({ title, data }: InsightItem) {
  const d = data as unknown as DowData
  const max = Math.max(...d.days.map((x) => x.amount))
  return (
    <CardShell wide>
      <CardHeader Icon={Calendar} title={title} />
      <p className="mb-5 -mt-2 text-sm text-zinc-400">
        Most spending on <span className="font-medium text-zinc-200">{d.peak_day}s</span>
      </p>
      {/* Bar chart */}
      <div className="flex items-end gap-1.5">
        {d.days.map(({ day, amount }) => {
          const isPeak = day === d.peak_day
          const barPx = max > 0 ? Math.max(2, Math.round((amount / max) * BAR_MAX_PX)) : 2
          return (
            <div key={day} className="flex flex-1 flex-col items-center gap-1.5">
              <div
                className={`w-full rounded-t-[3px] ${isPeak ? 'bg-indigo-500' : 'bg-zinc-700/70'}`}
                style={{ height: barPx }}
              />
              <span
                className={`text-[10px] ${isPeak ? 'font-medium text-zinc-300' : 'text-zinc-600'}`}
              >
                {day}
              </span>
            </div>
          )
        })}
      </div>
    </CardShell>
  )
}

interface LargestData {
  merchant: string
  amount: number
  date: string
  category: string
}

function LargestPurchaseCard({ title, data }: InsightItem) {
  const d = data as unknown as LargestData
  return (
    <CardShell>
      <CardHeader Icon={CreditCard} title={title} />
      <p className="text-3xl font-bold tabular-nums text-zinc-100">{fmtCurrency(d.amount)}</p>
      <p className="mt-2 text-sm text-zinc-400">{d.merchant}</p>
      <p className="mt-0.5 text-xs text-zinc-600">{d.date}</p>
    </CardShell>
  )
}

interface MomData {
  curr_month: string
  curr_amount: number
  prev_month: string
  prev_amount: number
  pct: number
  direction: 'up' | 'down'
}

function MomCard({ title, type, data }: InsightItem) {
  const d = data as unknown as MomData
  const isUp = type === 'mom_up'
  return (
    <CardShell>
      <CardHeader Icon={isUp ? TrendingUp : TrendingDown} title={title} />
      <div className="flex items-end gap-5">
        <div>
          <p className="text-2xl font-bold tabular-nums text-zinc-100">{fmtDollar(d.curr_amount)}</p>
          <p className="mt-0.5 text-xs text-zinc-500">{d.curr_month}</p>
        </div>
        <p className={`mb-0.5 text-xl font-semibold ${isUp ? 'text-red-400' : 'text-emerald-400'}`}>
          {isUp ? '↑' : '↓'}{d.pct.toFixed(0)}%
        </p>
        <div>
          <p className="text-2xl font-bold tabular-nums text-zinc-600">{fmtDollar(d.prev_amount)}</p>
          <p className="mt-0.5 text-xs text-zinc-700">{d.prev_month}</p>
        </div>
      </div>
    </CardShell>
  )
}

interface RecurringItem {
  name: string
  count: number
  avg: number
  total: number
}

interface RecurringData {
  items: RecurringItem[]
  grand_total: number
}

function RecurringCard({ title, data }: InsightItem) {
  const d = data as unknown as RecurringData
  return (
    <CardShell wide>
      <CardHeader Icon={Repeat} title={title} />
      <div className="divide-y divide-zinc-800/60">
        {d.items.map((item) => (
          <div key={item.name} className="flex items-center justify-between py-2.5">
            <div>
              <p className="text-sm font-medium text-zinc-300">{item.name}</p>
              <p className="mt-0.5 text-xs text-zinc-600">
                {item.count} charges · ~{fmtCurrency(item.avg)} avg
              </p>
            </div>
            <p className="tabular-nums text-sm text-zinc-400">{fmtCurrency(item.total)}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 flex justify-between border-t border-zinc-700/60 pt-3">
        <p className="text-xs text-zinc-500">Total</p>
        <p className="text-sm font-semibold text-zinc-200">{fmtCurrency(d.grand_total)}</p>
      </div>
    </CardShell>
  )
}

// ── Dispatch ───────────────────────────────────────────────────────────────────

function InsightCard(insight: InsightItem) {
  switch (insight.type) {
    case 'top_category':
      return <TopCategoryCard {...insight} />
    case 'day_of_week':
      return <DayOfWeekCard {...insight} />
    case 'largest_purchase':
      return <LargestPurchaseCard {...insight} />
    case 'mom_up':
    case 'mom_down':
      return <MomCard {...insight} />
    case 'recurring':
      return <RecurringCard {...insight} />
    default:
      return null
  }
}

interface Props {
  insights: InsightItem[]
}

export function Insights({ insights }: Props) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {insights.map((insight, i) => (
        <InsightCard key={i} {...insight} />
      ))}
    </div>
  )
}
