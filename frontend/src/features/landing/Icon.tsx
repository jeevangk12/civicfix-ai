import type { ReactNode } from 'react'

const paths = {
  arrow: <path d="M4.5 12h14m-5-5 5 5-5 5" />,
  map: <><path d="m3.5 6.5 5.7-2.2 5.6 2.2 5.7-2.2v13.2l-5.7 2.2-5.6-2.2-5.7 2.2zM9.2 4.3v13.2m5.6-11v13.2" /></>,
  pin: <><path d="M19 10c0 5.1-7 9.5-7 9.5S5 15.1 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2.2" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  pause: <path d="M9 6v12m6-12v12" />,
  play: <path d="m9 6 9 6-9 6z" />,
  report: <><path d="M14 4H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6M9 9h2m-2 5h6m-6 3h4m4-13v6m-3-3h6" /></>,
  review: <><path d="M8 6H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-2" /><path d="M9 4h6v4H9zm0 10 2 2 4-4" /></>,
  track: <><path d="M4 17.5h16M6 14l4-4 3 2.8L19 6m-4 0h4v4" /></>,
  info: <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5m0-8h.01" /></>,
  road: <path d="M6 5 4 19M18 5l2 14m-8-14v3m0 3v2m0 3v3" />,
  waste: <><path d="M5 7h14M9 7V4h6v3m2 0-1 13H8L7 7m3 4v5m4-5v5" /></>,
  light: <><path d="M9 17h6m-5 3h4M8.6 13.7A5.6 5.6 0 1 1 15.4 13.7L14 16h-4z" /></>,
  water: <path d="M12 3.5C9.7 7.3 6.5 10.4 6.5 14a5.5 5.5 0 1 0 11 0c0-3.6-3.2-6.7-5.5-10.5Z" />,
} satisfies Record<string, ReactNode>

export type IconName = keyof typeof paths

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      {paths[name]}
    </svg>
  )
}
