export const ALLOWED_INTENTS = [
  'Complaint',
  'Inquiry',
  'Refund Request',
  'Order Status',
  'Product Question',
]

export const MANAGER_INTENT_PRESETS = {
  Product: ['Product Question'],
  Order: ['Order Status'],
  Refund: ['Refund Request'],
  Support: ['Complaint', 'Inquiry'],
}
