import type { IconName } from './Icon'

export type SceneIssue = {
  icon: IconName
  label: string
  color: string
  position: [x: number, y: number, z: number]
}

export const sceneIssues: SceneIssue[] = [
  { icon: 'road', label: 'Road damage', color: '#ff7a1a', position: [-1.23, 0.13, 0] },
  { icon: 'waste', label: 'Waste accumulation', color: '#ff9a4d', position: [5.65, 0.13, -0.25] },
  { icon: 'light', label: 'Broken streetlight', color: '#ffb34d', position: [-0.85, 0.13, -4.75] },
  { icon: 'water', label: 'Water leakage', color: '#ff8646', position: [0.2, 0.13, 3.9] },
]
