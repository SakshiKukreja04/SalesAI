export default function EmotionBadge({ emotion }) {
  const emotionConfig = {
    happy: {
      bg: 'bg-green-100',
      text: 'text-green-700',
      label: 'Happy'
    },
    neutral: {
      bg: 'bg-yellow-100',
      text: 'text-yellow-700',
      label: 'Neutral'
    },
    frustrated: {
      bg: 'bg-orange-100',
      text: 'text-orange-700',
      label: 'Frustrated'
    },
    angry: {
      bg: 'bg-red-100',
      text: 'text-red-700',
      label: 'Angry'
    }
  }

  const config = emotionConfig[emotion?.toLowerCase()] || emotionConfig.neutral

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  )
}
