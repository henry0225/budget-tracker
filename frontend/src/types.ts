export interface Transaction {
  date: string
  merchant: string
  description: string
  amount: number
  category?: string
}

export interface UploadResponse {
  session_id: string
  transaction_count: number
  cc_count: number
  p2p_count: number
  merchant_count: number
  preview: Transaction[]
  kind?: 'cc' | 'p2p'
  p2p_summary?: P2PSummary
}

export interface CategoryTotal {
  category: string
  amount: number
}

export interface MonthlyPoint {
  month: string
  [category: string]: number | string
}

export interface Metrics {
  total: number
  count: number
  average: number
  top_category: string
}

export interface InsightItem {
  type: string
  title: string
  data?: Record<string, unknown>
}

export interface UploadedFile {
  name: string
  sessionId: string
  count: number
  kind: 'cc' | 'p2p'
}

export interface DashboardData {
  transactions: Transaction[]
  category_totals: CategoryTotal[]
  monthly_series: MonthlyPoint[]
  metrics: Metrics
  insights: InsightItem[]
}

export type AppView = 'landing' | 'preview' | 'dashboard'

// ── Venmo/Zelle insight data (matches backend summarize_p2p) ───────────────

export interface P2PCounterparty {
  name: string
  amount: number
  count: number
}

export interface P2PServiceSplit {
  service: 'Venmo' | 'Zelle'
  sent: number
  received: number
}

export interface P2PSummary {
  sent_total: number
  received_total: number
  sent_count: number
  received_count: number
  by_service: P2PServiceSplit[]
  top_sent: P2PCounterparty[]
  top_received: P2PCounterparty[]
}
