// Hermes SpendGuard — Desktop plugin (Hermes Desktop Plugin SDK, @hermes/plugin-sdk).
// One ESM file, no build step. Adds a SpendGuard page + sidebar entry to the
// native Hermes Desktop app. Data comes from the shared backend namespace
// (/api/plugins/hermes-spendguard/) provided by dashboard/plugin_api.py.
//
// NOTE: this file is loaded uncompiled by Hermes Desktop, so UI is built
// with jsx() calls, never JSX syntax (per the Desktop Plugin SDK docs).

import { host, jsx, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { useEffect, useState } from 'react'

function money(x) {
  if (x === null || x === undefined) return '—'
  return '$' + Number(x).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function Period(label, p) {
  const pct = p.cap ? Math.min(100, p.pct || 0) : 0
  const color = p.over ? '#c0392b' : pct >= 90 ? '#e2661e' : pct >= 75 ? '#e6a817' : '#3d9970'
  return jsx('section', { key: label, style: { marginBottom: 20 } },
    jsx('h3', null, label),
    p.cap
      ? jsx('div', null,
          jsx('div', { style: { display: 'flex', justifyContent: 'space-between', fontVariantNumeric: 'tabular-nums' } },
            jsx('span', null, `${money(p.spent)} of ${money(p.cap)}`),
            jsx('span', null, `${(p.pct || 0).toFixed(0)}%`)),
          jsx('div', { style: { height: 12, borderRadius: 6, background: '#e9e2cd', overflow: 'hidden', marginTop: 6 } },
            jsx('div', { style: { height: '100%', width: pct + '%', background: color, borderRadius: 6 } })))
      : jsx('p', { style: { opacity: 0.75 } }, `${money(p.spent)} spent · no budget set`),
    jsx('p', { style: { opacity: 0.75, fontSize: 13 } },
      `${p.calls} calls${p.unpriced ? ` · ⚠ ${p.unpriced} unpriced` : ''}`))
}

function SpendGuardPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    host
      .fetchJSON('/api/plugins/hermes-spendguard/status')
      .then((res) => { if (alive) setData(res) })
      .catch(() => { if (alive) setError('Could not load SpendGuard status.') })
    return () => { alive = false }
  }, [])

  if (error) return jsx('div', { style: { padding: 24 } },
    jsx('h1', null, '💸 SpendGuard'), jsx('p', null, error))
  if (!data) return jsx('div', { style: { padding: 24 } },
    jsx('p', null, 'Loading your spend…'))

  const st = data.status
  const icon = { ok: '🟢', warn: '🟡', over: '🔴', unbudgeted: '⚪' }[st.state] || ''
  return jsx('div', { style: { padding: 24, maxWidth: 880, margin: '0 auto' } },
    jsx('h1', null, `💸 SpendGuard ${icon}`),
    jsx('p', { style: { opacity: 0.72 } },
      st.state === 'over'
        ? 'Budget reached — new turns are blocked before they reach the model.'
        : 'Every API call, priced and counted against the budgets only you can set.'),
    Period('Today', st.day),
    Period('This month', st.month),
    jsx('p', { style: { opacity: 0.65, fontSize: 13, textAlign: 'center' } },
      'Budgets change only from the /spendguard command — the agent can read its spend, never raise its own cap.'))
}

export default {
  id: 'hermes-spendguard',
  name: 'SpendGuard',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'spendguard-page',
      area: ROUTES_AREA,
      title: 'SpendGuard',
      data: { path: '/spendguard' },
      render: () => jsx(SpendGuardPage, {}),
    })
    ctx.register({
      id: 'spendguard-nav',
      area: SIDEBAR_NAV_AREA,
      title: 'SpendGuard',
      data: { path: '/spendguard', label: 'SpendGuard', codicon: 'shield' },
      render: () => null,
    })
  },
}
