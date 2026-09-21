import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { triggerExchangeAction, triggerRefundAction, updateCustomerIssue } from '../services/api'
import { useData } from '../context/DataContext'

function SeverityBadge({ severity }) {
  const s = (severity || 'none').toLowerCase()
  if (s.includes('severe') || s.includes('unusable') || s.includes('high') || s.includes('urgent')) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700 ring-1 ring-inset ring-rose-600/20">
        <span className="h-1.5 w-1.5 rounded-full bg-rose-600 animate-pulse" />
        Severe / Unusable
      </span>
    )
  }
  if (s.includes('moderate') || s.includes('functional') || s.includes('medium')) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-700 ring-1 ring-inset ring-amber-600/20">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
        Moderate Defect
      </span>
    )
  }
  if (s.includes('minor') || s.includes('cosmetic') || s.includes('low')) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 ring-1 ring-inset ring-blue-700/10">
        <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
        Minor Cosmetic
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
      Standard
    </span>
  )
}

function StatusBadge({ status }) {
  const st = (status || 'open').toLowerCase()
  if (st === 'refund_initiated') {
    return (
      <span className="inline-flex items-center rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800 ring-1 ring-inset ring-emerald-600/20">
        Refund Initiated
      </span>
    )
  }
  if (st === 'exchange_pending') {
    return (
      <span className="inline-flex items-center rounded-md bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-800 ring-1 ring-inset ring-indigo-600/20">
        Exchange Pending
      </span>
    )
  }
  if (st === 'options_presented') {
    return (
      <span className="inline-flex items-center rounded-md bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 ring-1 ring-inset ring-amber-600/20">
        Options Presented
      </span>
    )
  }
  if (st === 'resolved' || st === 'closed') {
    return (
      <span className="inline-flex items-center rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
        Resolved
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-md bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-600/20">
      Open Dispute
    </span>
  )
}

export default function OpenIssuesPage() {
  const { issues, loadingIssues, refreshIssues } = useData()
  const [selectedStatus, setSelectedStatus] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedIssue, setSelectedIssue] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    refreshIssues()
    const interval = setInterval(refreshIssues, 25000)
    return () => clearInterval(interval)
  }, [refreshIssues])

  const filteredIssues = useMemo(() => {
    return (issues || []).filter((item) => {
      const matchStatus =
        selectedStatus === 'all' || (item.status || '').toLowerCase() === selectedStatus.toLowerCase()
      const q = searchQuery.toLowerCase()
      const matchQuery =
        !q ||
        (item.issue_title || '').toLowerCase().includes(q) ||
        (item.customer_email || '').toLowerCase().includes(q) ||
        (item.order_number || '').toLowerCase().includes(q) ||
        (item.defect_type || '').toLowerCase().includes(q)
      return matchStatus && matchQuery
    })
  }, [issues, selectedStatus, searchQuery])

  const stats = useMemo(() => {
    const total = (issues || []).length
    const refundInit = (issues || []).filter((i) => i.status === 'refund_initiated').length
    const exchangePend = (issues || []).filter((i) => i.status === 'exchange_pending').length
    const optionsPres = (issues || []).filter((i) => i.status === 'options_presented').length
    const dars = (issues || []).map((i) => Number(i.defect_area_ratio) || 0).filter((d) => d > 0)
    const avgDar = dars.length ? (dars.reduce((a, b) => a + b, 0) / dars.length) * 100 : 0

    return { total, refundInit, exchangePend, optionsPres, avgDar: Math.round(avgDar) }
  }, [issues])

  const handleResolve = async (issueId) => {
    setActionLoading(true)
    try {
      await updateCustomerIssue(issueId, { status: 'resolved', resolution_notes: 'Resolved by Admin' })
      toast.success('Issue marked as resolved')
      refreshIssues()
      if (selectedIssue?.id === issueId) setSelectedIssue(null)
    } catch (err) {
      toast.error('Failed to update issue status')
    } finally {
      setActionLoading(false)
    }
  }

  const handleTriggerRefund = async (issue) => {
    setActionLoading(true)
    try {
      await triggerRefundAction({
        order_number: issue.order_number || 'ORD-CURRENT',
        customer_email: issue.customer_email,
        customer_id: issue.customer_id,
        reason: `Admin refund for ${issue.issue_title} (Defect: ${issue.defect_type})`,
      })
      toast.success(`Refund initiated for ${issue.order_number || 'order'}`)
      refreshIssues()
      if (selectedIssue?.id === issue.id) setSelectedIssue(null)
    } catch (err) {
      toast.error('Failed to trigger refund')
    } finally {
      setActionLoading(false)
    }
  }

  const handleTriggerExchange = async (issue) => {
    setActionLoading(true)
    try {
      await triggerExchangeAction({
        order_number: issue.order_number || 'ORD-CURRENT',
        customer_email: issue.customer_email,
        customer_id: issue.customer_id,
        sku: 'FW-009',
        replacement_sku: 'FW-009',
      })
      toast.success(`Replacement exchange dispatched for ${issue.order_number || 'order'}`)
      refreshIssues()
      if (selectedIssue?.id === issue.id) setSelectedIssue(null)
    } catch (err) {
      toast.error('Failed to trigger exchange')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Open Customer Issues & Defect Triage</h1>
          <p className="text-sm text-slate-500">
            Real-time multimodal defect inspection, inventory availability checks, and autonomous refund/exchange resolutions.
          </p>
        </div>
        <button
          onClick={() => refreshIssues()}
          disabled={loadingIssues}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-50"
        >
          {loadingIssues ? 'Refreshing...' : 'Refresh Issues'}
        </button>
      </div>

      {/* Metric Cards */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Total Tracked Issues</p>
          <p className="mt-2 text-3xl font-bold text-slate-900">{stats.total}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-600">Options Presented</p>
          <p className="mt-2 text-3xl font-bold text-amber-700">{stats.optionsPres}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-600">Refunds Initiated</p>
          <p className="mt-2 text-3xl font-bold text-emerald-700">{stats.refundInit}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">Exchanges Pending</p>
          <p className="mt-2 text-3xl font-bold text-indigo-700">{stats.exchangePend}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Avg Defect Area (DAR)</p>
          <p className="mt-2 text-3xl font-bold text-slate-900">{stats.avgDar}%</p>
        </div>
      </section>

      {/* Filters & Search */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap gap-2">
          {[
            { key: 'all', label: 'All Issues' },
            { key: 'options_presented', label: 'Options Presented' },
            { key: 'refund_initiated', label: 'Refunds Initiated' },
            { key: 'exchange_pending', label: 'Exchanges Pending' },
            { key: 'resolved', label: 'Resolved' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setSelectedStatus(tab.key)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                selectedStatus === tab.key
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="w-full sm:w-72">
          <input
            type="text"
            placeholder="Search by customer, order, defect..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm placeholder-slate-400 focus:border-slate-900 focus:outline-none"
          />
        </div>
      </div>

      {/* Issues Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {loadingIssues && issues.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">Loading issues...</div>
        ) : filteredIssues.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-base font-semibold text-slate-700">No issues found</p>
            <p className="mt-1 text-sm text-slate-400">
              When customers report damages, defects, or request refunds, issues will be automatically triaged and listed here.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-3.5">Customer & Order</th>
                  <th className="px-4 py-3.5">Issue & Defect Triage</th>
                  <th className="px-4 py-3.5">Severity & DAR</th>
                  <th className="px-4 py-3.5">Autonomous Resolution Plan</th>
                  <th className="px-4 py-3.5">Status</th>
                  <th className="px-4 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {filteredIssues.map((issue) => {
                  const darPercent = Math.round((Number(issue.defect_area_ratio) || 0) * 100)
                  return (
                    <tr key={issue.id} className="hover:bg-slate-50/75 transition-colors">
                      {/* Customer & Order */}
                      <td className="px-4 py-3.5">
                        <div className="font-semibold text-slate-900">{issue.customer_name || 'Customer'}</div>
                        <div className="text-xs text-slate-500">{issue.customer_email}</div>
                        {issue.order_number && (
                          <span className="mt-1 inline-block rounded bg-slate-100 px-2 py-0.5 text-xs font-mono font-medium text-slate-700">
                            {issue.order_number}
                          </span>
                        )}
                      </td>

                      {/* Issue & Defect */}
                      <td className="px-4 py-3.5">
                        <div className="font-medium text-slate-900">{issue.issue_title}</div>
                        <div className="text-xs text-slate-500 max-w-xs truncate">{issue.description}</div>
                        {issue.defect_type && issue.defect_type !== 'none' && (
                          <span className="mt-1 inline-flex items-center rounded-full bg-purple-50 px-2 py-0.5 text-xs font-medium text-purple-700">
                            {issue.defect_type.replace('_', ' ')}
                          </span>
                        )}
                      </td>

                      {/* Severity & DAR */}
                      <td className="px-4 py-3.5">
                        <div className="space-y-1">
                          <SeverityBadge severity={issue.severity} />
                          {darPercent > 0 && (
                            <div className="flex items-center gap-2 pt-1">
                              <div className="h-1.5 w-16 rounded-full bg-slate-200 overflow-hidden">
                                <div
                                  className={`h-full ${
                                    darPercent > 25 ? 'bg-rose-500' : darPercent > 10 ? 'bg-amber-500' : 'bg-blue-500'
                                  }`}
                                  style={{ width: `${Math.min(100, darPercent)}%` }}
                                />
                              </div>
                              <span className="text-xs font-semibold text-slate-600">{darPercent}% DAR</span>
                            </div>
                          )}
                        </div>
                      </td>

                      {/* Suggested Action */}
                      <td className="px-4 py-3.5">
                        <div className="text-xs font-medium text-slate-900">
                          {issue.suggested_action || 'Autonomous Triage Review'}
                        </div>
                        {issue.resolution_notes && (
                          <div className="text-xs text-slate-500 max-w-xs truncate mt-0.5">
                            {issue.resolution_notes}
                          </div>
                        )}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3.5">
                        <StatusBadge status={issue.status} />
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3.5 text-right space-x-1.5 whitespace-nowrap">
                        <button
                          onClick={() => setSelectedIssue(issue)}
                          className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200"
                        >
                          View
                        </button>
                        {issue.status !== 'refund_initiated' && issue.status !== 'resolved' && (
                          <button
                            onClick={() => handleTriggerRefund(issue)}
                            disabled={actionLoading}
                            className="rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                          >
                            Refund
                          </button>
                        )}
                        {issue.status !== 'exchange_pending' && issue.status !== 'resolved' && (
                          <button
                            onClick={() => handleTriggerExchange(issue)}
                            disabled={actionLoading}
                            className="rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                          >
                            Exchange
                          </button>
                        )}
                        {issue.status !== 'resolved' && (
                          <button
                            onClick={() => handleResolve(issue.id)}
                            disabled={actionLoading}
                            className="rounded-md bg-slate-800 px-2.5 py-1 text-xs font-medium text-white hover:bg-slate-900 disabled:opacity-50"
                          >
                            Resolve
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Details Modal */}
      {selectedIssue && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-lg font-bold text-slate-900">Issue Details & Triage Audit</h3>
              <button
                onClick={() => setSelectedIssue(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Customer:</span>
                <span className="font-semibold text-slate-900">{selectedIssue.customer_name} ({selectedIssue.customer_email})</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Order ID:</span>
                <span className="font-mono font-medium text-slate-900">{selectedIssue.order_number || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Defect Type:</span>
                <span className="font-medium capitalize text-purple-700">{selectedIssue.defect_type || 'Unspecified'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Severity:</span>
                <SeverityBadge severity={selectedIssue.severity} />
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Defect Area Ratio (DAR):</span>
                <span className="font-semibold text-slate-900">{Math.round((Number(selectedIssue.defect_area_ratio) || 0) * 100)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Current Status:</span>
                <StatusBadge status={selectedIssue.status} />
              </div>

              <div className="border-t pt-3">
                <p className="text-xs font-semibold text-slate-500 uppercase">Issue Description</p>
                <p className="mt-1 text-slate-700 bg-slate-50 rounded-lg p-2.5 text-xs">{selectedIssue.description || 'No description recorded.'}</p>
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase">Resolution Notes & AI Action Plan</p>
                <p className="mt-1 text-slate-700 bg-emerald-50 rounded-lg p-2.5 text-xs font-medium text-emerald-900">
                  {selectedIssue.resolution_notes || selectedIssue.suggested_action || 'Pending resolution action.'}
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t pt-4">
              <button
                onClick={() => setSelectedIssue(null)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                Close
              </button>
              {selectedIssue.status !== 'refund_initiated' && (
                <button
                  onClick={() => handleTriggerRefund(selectedIssue)}
                  disabled={actionLoading}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-medium text-white hover:bg-emerald-700"
                >
                  Authorize Full Refund
                </button>
              )}
              {selectedIssue.status !== 'resolved' && (
                <button
                  onClick={() => handleResolve(selectedIssue.id)}
                  disabled={actionLoading}
                  className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-medium text-white hover:bg-slate-800"
                >
                  Mark Resolved
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
