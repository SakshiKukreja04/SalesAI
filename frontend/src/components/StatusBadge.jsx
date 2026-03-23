export default function StatusBadge({ status }) {
  const statusConfig = {
    replied: {
      bg: 'bg-green-100',
      text: 'text-green-800',
      label: 'Replied'
    },
    escalated: {
      bg: 'bg-red-100',
      text: 'text-red-800',
      label: 'Escalated'
    },
    failed: {
      bg: 'bg-gray-100',
      text: 'text-gray-800',
      label: 'Failed'
    }
  }

  const config = statusConfig[status] || statusConfig.failed

  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  )
}
