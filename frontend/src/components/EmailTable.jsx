import { useMemo, useState } from 'react'

const statuses = ['all', 'replied', 'failed', 'escalated']

export default function EmailTable({ emails = [] }) {
  const [query, setQuery] = useState('')
  const [emotion, setEmotion] = useState('all')
  const [status, setStatus] = useState('all')

  const emotions = useMemo(() => {
    const values = new Set(emails.map((item) => (item.emotion || '').trim()).filter(Boolean))
    return ['all', ...Array.from(values)]
  }, [emails])

  const filtered = useMemo(() => {
    return emails.filter((row) => {
      const searchable = `${row.sender || ''} ${row.subject || ''} ${row.reply || ''}`.toLowerCase()
      const matchesQuery = !query || searchable.includes(query.toLowerCase())
      const matchesEmotion = emotion === 'all' || row.emotion === emotion
      const matchesStatus = status === 'all' || row.status === status
      return matchesQuery && matchesEmotion && matchesStatus
    })
  }, [emails, query, emotion, status])

  const exportCsv = () => {
    const header = ['Sender', 'Subject', 'Intent', 'Emotion', 'Status', 'Response']
    const rows = filtered.map((row) => [
      row.sender || '',
      row.subject || '',
      row.intent || '',
      row.emotion || '',
      row.status || '',
      (row.reply || '').replace(/\n/g, ' '),
    ])

    const csv = [header, ...rows]
      .map((line) => line.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
      .join('\n')

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'emails_export.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  if (!emails.length) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-500">
        No emails available for this view.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search sender, subject, response..."
          className="min-w-[220px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />

        <select
          value={emotion}
          onChange={(event) => setEmotion(event.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          {emotions.map((item) => (
            <option key={item} value={item}>
              {item === 'all' ? 'All emotions' : item}
            </option>
          ))}
        </select>

        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        >
          {statuses.map((item) => (
            <option key={item} value={item}>
              {item === 'all' ? 'All statuses' : item}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={exportCsv}
          className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          Export CSV
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Sender</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Subject</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Intent</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Emotion</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Status</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Response</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((row) => (
                <tr key={row.id || `${row.sender}-${row.subject}-${row.timestamp}`}>
                  <td className="px-4 py-3 text-slate-700">{row.sender || '-'}</td>
                  <td className="max-w-[280px] truncate px-4 py-3 text-slate-700">{row.subject || '-'}</td>
                  <td className="px-4 py-3 text-slate-700">{row.intent || '-'}</td>
                  <td className="px-4 py-3 text-slate-700">{row.emotion || '-'}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium capitalize text-slate-700">
                      {row.status || '-'}
                    </span>
                  </td>
                  <td className="max-w-[380px] truncate px-4 py-3 text-slate-600">{row.reply || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
