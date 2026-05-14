import {
  ArrowDownLeft,
  ArrowUpRight,
  ArrowLeftRight,
  Calendar,
  CreditCard,
  Repeat,
  Tag,
  TrendingDown,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react'
import { catColor } from '../../constants'
import { fmtCurrency, fmtDollar } from '../../lib/format'
import type { InsightItem, P2PSummary } from '../../types'

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

function P2PCard({ title, data }: InsightItem) {
  const d = data as unknown as P2PSummary
  const net = d.sent_total - d.received_total

  return (
    <CardShell wide>
      <CardHeader Icon={ArrowLeftRight} title={title} />

      {/* Headline numbers */}
      <div className="grid grid-cols-3 gap-4 border-b border-zinc-800 pb-4">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-zinc-600">Sent</p>
          <p className="mt-1 text-xl font-semibold text-red-400 tabular-nums">
            {fmtCurrency(d.sent_total)}
          </p>
          <p className="text-[10px] text-zinc-600">{d.sent_count} transactions</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-zinc-600">
            Received <span className="text-zinc-700">(auto-subtracted)</span>
          </p>
          <p className="mt-1 text-xl font-semibold text-emerald-400 tabular-nums">
            −{fmtCurrency(d.received_total)}
          </p>
          <p className="text-[10px] text-zinc-600">{d.received_count} transactions</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-wider text-zinc-600">
            Net = category total
          </p>
          <p
            className={`mt-1 text-xl font-semibold tabular-nums ${
              net >= 0 ? 'text-zinc-100' : 'text-emerald-400'
            }`}
          >
            {net >= 0 ? '' : '−'}
            {fmtCurrency(Math.abs(net))}
          </p>
          <p className="text-[10px] text-zinc-600">Counted in total spending</p>
        </div>
      </div>

      {/* Service split */}
      {d.by_service.length > 0 && (
        <div className="mt-4 space-y-2">
          {d.by_service.map((s) => (
            <div key={s.service} className="flex items-center gap-3 text-xs">
              <span className="w-12 shrink-0 text-zinc-400">{s.service}</span>
              <span className="flex flex-1 items-center gap-3 text-zinc-500">
                <span>
                  <ArrowUpRight className="mr-0.5 inline h-3 w-3 text-red-400" />
                  <span className="tabular-nums text-zinc-300">{fmtCurrency(s.sent)}</span> sent
                </span>
                <span>
                  <ArrowDownLeft className="mr-0.5 inline h-3 w-3 text-emerald-400" />
                  <span className="tabular-nums text-zinc-300">{fmtCurrency(s.received)}</span> received
                </span>
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Top counterparties */}
      <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
        <CounterpartySection title="Most sent to" parties={d.top_sent} color="#f87171" />
        <CounterpartySection
          title="Most received from"
          parties={d.top_received}
          color="#34d399"
        />
      </div>

      <p className="mt-4 border-t border-zinc-800 pt-3 text-[10px] leading-relaxed text-zinc-600">
        The <span className="text-zinc-400">Venmo &amp; Zelle</span> category is net
        spending: every received P2P is automatically subtracted, so your total
        spending reflects what actually left your accounts.
      </p>
    </CardShell>
  )
}

function CounterpartySection({
  title,
  parties,
  color,
}: {
  title: string
  parties: P2PSummary['top_sent']
  color: string
}) {
  if (parties.length === 0) {
    return (
      <div>
        <p className="mb-2 text-[10px] uppercase tracking-wider text-zinc-600">{title}</p>
        <p className="text-xs text-zinc-600">None.</p>
      </div>
    )
  }
  const max = parties[0].amount
  return (
    <div>
      <p className="mb-2 text-[10px] uppercase tracking-wider text-zinc-600">{title}</p>
      <div className="space-y-1.5">
        {parties.slice(0, 6).map((p) => (
          <div key={p.name}>
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="min-w-0 truncate text-zinc-300">{p.name}</span>
              <span className="shrink-0 tabular-nums text-zinc-500">
                {fmtCurrency(p.amount)}
              </span>
            </div>
            <div className="mt-0.5 h-1 overflow-hidden rounded-full bg-zinc-800/60">
              <div
                className="h-full rounded-full"
                style={{ width: `${(p.amount / max) * 100}%`, background: color, opacity: 0.75 }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Dispatch ───────────────────────────────────────────────────────────────────

function InsightCard(insight: InsightItem) {
  switch (insight.type) {
    case 'top_category':
      return <TopCategoryCard {...insight} />
    case 'p2p_summary':
      return <P2PCard {...insight} />
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
