import { useRef, useState } from 'react'
import { getDashboard, mergeCSVs, streamCategorize, uploadCSV, uploadP2PCSV } from './api'
import { Sidebar } from './components/Sidebar'
import { Landing } from './components/Landing'
import { Preview } from './components/Preview'
import { Dashboard } from './components/Dashboard'
import type { AppView, DashboardData, UploadResponse, UploadedFile } from './types'

export default function App() {
  const [view, setView] = useState<AppView>('landing')
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [previewData, setPreviewData] = useState<UploadResponse | null>(null)
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [isCategorizing, setIsCategorizing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const esRef = useRef<EventSource | null>(null)

  const hasCC = uploadedFiles.some((f) => f.kind === 'cc')
  const hasP2P = uploadedFiles.some((f) => f.kind === 'p2p')
  const onlyP2P = hasP2P && !hasCC

  async function handleUpload(file: File) {
    setError(null)
    setDashboardData(null)
    setProgress(null)
    try {
      const data = await uploadCSV(file)
      await mergeAfterUpload(file.name, data, 'cc')
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function handleP2PUpload(file: File) {
    setError(null)
    setDashboardData(null)
    setProgress(null)
    try {
      const data = await uploadP2PCSV(file)
      await mergeAfterUpload(file.name, data, 'p2p')
    } catch (e) {
      setError((e as Error).message)
    }
  }

  // Each upload creates its own session; combine them via /merge so each file
  // can be removed independently.
  async function mergeAfterUpload(
    name: string,
    data: UploadResponse,
    kind: 'cc' | 'p2p',
  ) {
    const newFile: UploadedFile = {
      name,
      sessionId: data.session_id,
      count: kind === 'cc' ? data.cc_count : data.p2p_count,
      kind,
    }
    const newFiles = [...uploadedFiles, newFile]
    setUploadedFiles(newFiles)

    if (newFiles.length === 1) {
      setPreviewData(data)
    } else {
      const merged = await mergeCSVs(newFiles.map((f) => f.sessionId))
      setPreviewData(merged)
    }
    setView('preview')
  }

  async function handleRemoveFile(sessionId: string) {
    const remaining = uploadedFiles.filter((f) => f.sessionId !== sessionId)
    setUploadedFiles(remaining)
    setDashboardData(null)
    if (remaining.length === 0) {
      setPreviewData(null)
      setView('landing')
    } else {
      try {
        const merged = await mergeCSVs(remaining.map((f) => f.sessionId))
        setPreviewData(merged)
        setView('preview')
      } catch (e) {
        setError((e as Error).message)
      }
    }
  }

  function handleCategorize() {
    const activeSessionId = previewData?.session_id
    if (!activeSessionId || isCategorizing) return
    if (hasCC && !apiKey) return
    esRef.current?.close()
    setIsCategorizing(true)
    setProgress(null)
    setError(null)

    esRef.current = streamCategorize(activeSessionId, apiKey, {
      onProgress: (done, total) => setProgress({ done, total }),
      onDone: async () => {
        try {
          const data = await getDashboard(activeSessionId)
          setDashboardData(data)
          setView('dashboard')
        } catch (e) {
          setError((e as Error).message)
        } finally {
          setIsCategorizing(false)
          setProgress(null)
        }
      },
      onError: (msg) => {
        setError(msg)
        setIsCategorizing(false)
      },
    })
  }

  function handleReset() {
    esRef.current?.close()
    setView('landing')
    setUploadedFiles([])
    setPreviewData(null)
    setDashboardData(null)
    setProgress(null)
    setIsCategorizing(false)
    setError(null)
  }

  const canCategorize =
    uploadedFiles.length > 0 && !isCategorizing && (onlyP2P || !!apiKey)

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-50">
      <Sidebar
        uploadedFiles={uploadedFiles}
        hasDashboard={view === 'dashboard'}
        apiKey={apiKey}
        apiKeyRequired={hasCC}
        onApiKeyChange={setApiKey}
        onUpload={handleUpload}
        onP2PUpload={handleP2PUpload}
        onCategorize={handleCategorize}
        onReset={handleReset}
        onRemoveFile={handleRemoveFile}
        canCategorize={canCategorize}
        isCategorizing={isCategorizing}
        progress={progress}
        error={error}
      />
      <main className="flex-1 overflow-y-auto">
        {view === 'landing' && <Landing />}
        {view === 'preview' && previewData && <Preview data={previewData} />}
        {view === 'dashboard' && dashboardData && <Dashboard data={dashboardData} />}
      </main>
    </div>
  )
}
