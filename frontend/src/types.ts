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
  merchant_count: number
  preview: Transaction[]
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
}

export interface DashboardData {
  transactions: Transaction[]
  category_totals: CategoryTotal[]
  monthly_series: MonthlyPoint[]
  metrics: Metrics
  insights: InsightItem[]
}

export type AppView = 'landing' | 'preview' | 'dashboard'
