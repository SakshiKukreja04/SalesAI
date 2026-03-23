export default function ConfidenceBar({ confidence }) {
  const percentValue = typeof confidence === 'number' ? (confidence * 100) : 0
  const safePercent = Math.min(100, Math.max(0, percentValue))

  let barColor = 'bg-red-500'
  if (safePercent >= 70) {
    barColor = 'bg-green-500'
  } else if (safePercent >= 50) {
    barColor = 'bg-yellow-500'
  }

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-gray-700">Confidence</span>
        <span className="text-xs font-semibold text-gray-800">{safePercent.toFixed(0)}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${safePercent}%` }}
        />
      </div>
    </div>
  )
}
