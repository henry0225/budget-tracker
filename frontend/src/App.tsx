import { useRef, useState } from 'react'
import { getDashboard, mergeCSVs, streamCategorize, uploadCSV } from './api'
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

  async function handleUpload(file: File) {
    setError(null)
    setDashboardData(null)
    setProgress(null)
    try {
      const data = await uploadCSV(file)
      const newFiles = [
        ...uploadedFiles,
        { name: file.name, sessionId: data.session_id, count: data.transaction_count },
      ]
      setUploadedFiles(newFiles)

      if (newFiles.length > 1) {
        const merged = await mergeCSVs(newFiles.map((f) => f.sessionId))
        setPreviewData(merged)
      } else {
        setPreviewData(data)
      }
      setView('preview')
    } catch (e) {
      setError((e as Error).message)
    }
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
    if (!activeSessionId || !apiKey || isCategorizing) return
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

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-50">
      <Sidebar
        uploadedFiles={uploadedFiles}
        hasDashboard={view === 'dashboard'}
        apiKey={apiKey}
        onApiKeyChange={setApiKey}
        onUpload={handleUpload}
        onCategorize={handleCategorize}
        onReset={handleReset}
        onRemoveFile={handleRemoveFile}
        canCategorize={uploadedFiles.length > 0 && !!apiKey && !isCategorizing}
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
