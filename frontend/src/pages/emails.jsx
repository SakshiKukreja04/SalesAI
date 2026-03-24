import { useEffect } from 'react'

import EmailTable from '../components/EmailTable'
import { useData } from '../context/DataContext'

export default function EmailsPage() {
  const { visibleEmails, loadingEmails, refreshEmails } = useData()

  useEffect(() => {
    refreshEmails()
  }, [refreshEmails])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-slate-900">Emails</h2>
        <button
          type="button"
          onClick={refreshEmails}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          Refresh
        </button>
      </div>

      {loadingEmails ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, idx) => (
            <div key={idx} className="h-12 animate-pulse rounded-lg bg-slate-200" />
          ))}
        </div>
      ) : (
        <EmailTable emails={visibleEmails} />
      )}
    </div>
  )
}
