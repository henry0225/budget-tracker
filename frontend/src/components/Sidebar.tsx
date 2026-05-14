import { useCallback, useRef, useState } from 'react'
import {
  ArrowLeftRight,
  CreditCard,
  Eye,
  EyeOff,
  RotateCcw,
  Sparkles,
  Upload,
  X,
} from 'lucide-react'
import clsx from 'clsx'
import type { UploadedFile } from '../types'

interface SidebarProps {
  uploadedFiles: UploadedFile[]
  hasDashboard: boolean
  apiKey: string
  apiKeyRequired: boolean
  onApiKeyChange: (key: string) => void
  onUpload: (file: File) => void
  onP2PUpload: (file: File) => void
  onCategorize: () => void
  onReset: () => void
  onRemoveFile: (sessionId: string) => void
  canCategorize: boolean
  isCategorizing: boolean
  progress: { done: number; total: number } | null
  error: string | null
}

function UploadZone({
  label,
  hint,
  Icon,
  onFile,
}: {
  label: string
  hint: string
  Icon: typeof Upload
  onFile: (file: File) => void
}) {
  const [isDragging, setIsDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const accept = useCallback(
    (file: File) => {
      if (file.name.toLowerCase().endsWith('.csv')) onFile(file)
    },
    [onFile],
  )

  return (
    <div
      role="button"
      tabIndex={0}
      className={clsx(
        'cursor-pointer rounded-lg border-2 border-dashed px-4 py-4 text-center transition-colors',
        isDragging
          ? 'border-indigo-400 bg-indigo-400/5'
          : 'border-zinc-700 hover:border-zinc-500',
      )}
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setIsDragging(false)
        const f = e.dataTransfer.files[0]
        if (f) accept(f)
      }}
      onClick={() => fileRef.current?.click()}
      onKeyDown={(e) => e.key === 'Enter' && fileRef.current?.click()}
    >
      <Icon className="mx-auto mb-1.5 h-4 w-4 text-zinc-500" />
      <p className="text-xs text-zinc-400">{label}</p>
      <p className="mt-0.5 text-[10px] text-zinc-600">{hint}</p>
      <input
        ref={fileRef}
        type="file"
        accept=".csv"
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) accept(f)
          e.target.value = ''
        }}
      />
    </div>
  )
}

export function Sidebar({
  uploadedFiles,
  hasDashboard,
  apiKey,
  apiKeyRequired,
  onApiKeyChange,
  onUpload,
  onP2PUpload,
  onCategorize,
  onReset,
  onRemoveFile,
  canCategorize,
  isCategorizing,
  progress,
  error,
}: SidebarProps) {
  const [showKey, setShowKey] = useState(false)

  const progressPct = progress ? (progress.done / progress.total) * 100 : 0

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-zinc-800 bg-zinc-900">
      <div className="flex items-center gap-2.5 border-b border-zinc-800 px-5 py-4">
        <span className="text-indigo-400">●</span>
        <span className="font-semibold tracking-tight">Budget Tracker</span>
      </div>

      <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-5">
        {/* Credit card upload */}
        <div>
          <div className="mb-2 flex items-center gap-1.5">
            <CreditCard className="h-3 w-3 text-zinc-500" />
            <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
              Credit card CSV
            </p>
          </div>
          <UploadZone
            label="Drop CSV here"
            hint="Robinhood · Capital One"
            Icon={Upload}
            onFile={onUpload}
          />
        </div>

        {/* Checking / P2P upload */}
        <div>
          <div className="mb-2 flex items-center gap-1.5">
            <ArrowLeftRight className="h-3 w-3 text-zinc-500" />
            <p className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
              Venmo &amp; Zelle
            </p>
          </div>
          <UploadZone
            label="Drop checking CSV"
            hint="Capital One 360 Checking"
            Icon={Upload}
            onFile={onP2PUpload}
          />
          <p className="mt-2 text-[10px] leading-relaxed text-zinc-600">
            Adds a <span className="text-zinc-400">Venmo &amp; Zelle</span> category. No
            API key needed.
          </p>
        </div>

        {/* Uploaded files */}
        {uploadedFiles.length > 0 && (
          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
              Loaded
            </p>
            <div className="space-y-1">
              {uploadedFiles.map((f) => (
                <div
                  key={f.sessionId}
                  className="flex items-center gap-2 rounded-md bg-zinc-800/60 px-2.5 py-1.5"
                >
                  <span
                    className={clsx(
                      'shrink-0 rounded px-1 text-[9px] font-semibold uppercase tracking-wider',
                      f.kind === 'p2p'
                        ? 'bg-orange-500/20 text-orange-300'
                        : 'bg-indigo-500/20 text-indigo-300',
                    )}
                  >
                    {f.kind === 'p2p' ? 'P2P' : 'CC'}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs text-zinc-300">{f.name}</p>
                    <p className="text-[10px] text-zinc-600">
                      {f.count.toLocaleString()} {f.kind === 'p2p' ? 'sent' : 'txns'}
                    </p>
                  </div>
                  <button
                    onClick={() => onRemoveFile(f.sessionId)}
                    className="shrink-0 text-zinc-600 transition-colors hover:text-zinc-400"
                    aria-label={`Remove ${f.name}`}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
            {hasDashboard && (
              <button
                onClick={onReset}
                className="mt-2 flex items-center gap-1 text-[11px] text-zinc-600 transition-colors hover:text-zinc-400"
              >
                <RotateCcw className="h-3 w-3" />
                Start over
              </button>
            )}
          </div>
        )}

        {/* API key — only when CC data is loaded */}
        {apiKeyRequired && (
          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
              DeepSeek API key
            </p>
            <div className="relative">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => onApiKeyChange(e.target.value)}
                placeholder="sk-…"
                className="w-full rounded-md border border-zinc-700 bg-zinc-800 py-2 pl-3 pr-9 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/40 transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400 transition-colors"
                tabIndex={-1}
              >
                {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
            <p className="mt-1 text-[10px] text-zinc-700">platform.deepseek.com</p>
          </div>
        )}

        {/* Categorize */}
        <button
          onClick={onCategorize}
          disabled={!canCategorize}
          className="flex items-center justify-center gap-2 rounded-lg bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Sparkles className="h-4 w-4" />
          {isCategorizing
            ? 'Categorizing…'
            : hasDashboard
              ? 'Re-categorize'
              : apiKeyRequired
                ? 'Categorize'
                : 'Generate dashboard'}
        </button>

        {/* Progress */}
        {isCategorizing && (
          <div className="space-y-1.5">
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-zinc-800">
              {progress ? (
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-indigo-500 transition-all duration-300"
                  style={{ width: `${progressPct}%` }}
                />
              ) : (
                <div className="absolute inset-y-0 w-1/3 rounded-full bg-indigo-500 animate-progress-slide" />
              )}
            </div>
            <p className="text-[11px] text-zinc-500">
              {progress ? `${progress.done} / ${progress.total} merchants` : 'Starting…'}
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="rounded-md border border-red-900/50 bg-red-950/30 px-3 py-2 text-[11px] leading-relaxed text-red-400">
            {error}
          </p>
        )}
      </div>

      <div className="border-t border-zinc-800 px-5 py-3">
        <p className="text-[10px] text-zinc-700">DeepSeek · React · FastAPI</p>
      </div>
    </aside>
  )
}
