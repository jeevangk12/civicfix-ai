import { useEffect, useRef } from 'react'
import { BarController, BarElement, CategoryScale, Chart, LinearScale, Tooltip } from 'chart.js'
import { Section } from './ui'

Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip)

export type Bucket = { label: string; count: number }

function Bars({ values, title, trend }: { values: Bucket[]; title: string; trend: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const axis = { ticks: { color: '#d4c9be' }, grid: { display: false } }
    const counts = { beginAtZero: true, ticks: { color: '#d4c9be', precision: 0 }, grid: { color: '#423832' } }
    const chart = new Chart(ref.current, {
      type: 'bar',
      data: {
        labels: values.map(({ label }) => label),
        datasets: [{
          label: 'Count', data: values.map(({ count }) => count),
          backgroundColor: '#e78739', hoverBackgroundColor: '#ffb34d', borderRadius: 3, maxBarThickness: 19,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: false, indexAxis: trend ? 'x' : 'y',
        scales: {
          x: trend ? { ...axis, ticks: { ...axis.ticks, maxTicksLimit: 8, maxRotation: 0 } } : counts,
          y: trend ? counts : {
            ...axis,
            ticks: {
              ...axis.ticks, autoSkip: false,
              callback: (_value, index) => {
                const label = values[index]?.label ?? ''
                return label.length > 23 ? label.slice(0, 21) + '…' : label
              },
            },
          },
        },
        plugins: { legend: { display: false } },
      },
    })
    return () => chart.destroy()
  }, [values, trend])

  return <div className="workspace-chart-scroll">
    <div className="workspace-chart-frame" style={{ height: trend ? 220 : Math.max(170, values.length * 33 + 32) }}>
      <canvas ref={ref} role="img" aria-label={`${title} chart. Exact counts are in the data table below.`} />
    </div>
  </div>
}

export function CountChart({ title, values, trend = false, children }: {
  title: string; values: Bucket[]; trend?: boolean; children?: string
}) {
  return <Section title={title}>
    {children && <p className="workspace-muted">{children}</p>}
    {values.some(({ count }) => count > 0) ? <>
      <Bars values={values} title={title} trend={trend} />
      <details className="workspace-chart-table">
        <summary>View chart data</summary>
        <table className="workspace-table" aria-label={`${title} data`}>
          <thead><tr><th scope="col">{trend ? 'Date (UTC)' : 'Group'}</th><th scope="col">Count</th></tr></thead>
          <tbody>{values.map(({ label, count }, index) => <tr key={`${label}-${index}`}><td>{label}</td><td>{count}</td></tr>)}</tbody>
        </table>
      </details>
    </> : <p>No data in this view.</p>}
  </Section>
}
