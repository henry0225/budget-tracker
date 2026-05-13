import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { catColor } from '../../constants'
import { fmtCurrency, fmtDollar, fmtMonthLabel } from '../../lib/format'
import type { CategoryTotal, MonthlyPoint } from '../../types'

const TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: '#18181b',
  border: '1px solid #27272a',
  borderRadius: 8,
  fontSize: 12,
  color: '#a1a1aa',
  boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
        {title}
      </p>
      {children}
    </div>
  )
}

function SpendingBarChart({ data }: { data: CategoryTotal[] }) {
  // Ascending sort puts the largest bar at the bottom; recharts renders bottom → top
  const sorted = [...data].sort((a, b) => a.amount - b.amount)

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={sorted} layout="vertical" margin={{ top: 0, right: 72, bottom: 0, left: 0 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="category"
          width={168}
          tick={{ fontSize: 12, fill: '#a1a1aa' }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          cursor={{ fill: 'rgba(255,255,255,0.03)' }}
          formatter={(value: number) => [fmtCurrency(value), 'Spent']}
        />
        <Bar dataKey="amount" radius={[0, 4, 4, 0]} label={{ position: 'right', formatter: fmtDollar, fontSize: 11, fill: '#71717a' }}>
          {sorted.map(({ category }) => (
            <Cell key={category} fill={catColor(category)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function MonthlyAreaChart({
  data,
  categories,
}: {
  data: MonthlyPoint[]
  categories: CategoryTotal[]
}) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <XAxis
          dataKey="month"
          tick={{ fontSize: 11, fill: '#a1a1aa' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={fmtMonthLabel}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#a1a1aa' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => fmtDollar(v)}
          width={48}
        />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(value: number, name: string) => [fmtCurrency(value), name]}
        />
        {/* Render largest-first so biggest category anchors the bottom of the stack */}
        {categories.map(({ category }) => (
          <Area
            key={category}
            type="monotone"
            dataKey={category}
            stackId="a"
            stroke={catColor(category)}
            fill={catColor(category)}
            fillOpacity={0.75}
            strokeWidth={0}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )
}

interface Props {
  categoryTotals: CategoryTotal[]
  monthlySeries: MonthlyPoint[]
}

export function Charts({ categoryTotals, monthlySeries }: Props) {
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <ChartCard title="Spending by Category">
        <SpendingBarChart data={categoryTotals} />
      </ChartCard>
      <ChartCard title="Monthly Trend">
        <MonthlyAreaChart data={monthlySeries} categories={categoryTotals} />
      </ChartCard>
    </div>
  )
}
