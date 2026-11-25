type Coordinates = [x: number, y: number, z: number]

export type CityInstance = {
  position: Coordinates
  scale: Coordinates
  color: string
}

type Tower = { x: number; z: number; width: number; depth: number; height: number; color: string }

const towers: Tower[] = [
  { x: -5.25, z: -3.85, width: 1.6, depth: 1.5, height: 3.3, color: '#393836' },
  { x: -3.05, z: -3.65, width: 1.71, depth: 1.56, height: 5.25, color: '#303031' },
  { x: -4.53, z: -1.65, width: 2.18, depth: 1.22, height: 2.12, color: '#42403e' },
  { x: -1.71, z: -1.77, width: 1.26, depth: 1.2, height: 3.02, color: '#333232' },
  { x: 2.04, z: -3.83, width: 1.73, depth: 1.56, height: 4.17, color: '#383736' },
  { x: 4.13, z: -3.65, width: 1.76, depth: 1.82, height: 5.82, color: '#393939' },
  { x: 5.68, z: -2.34, width: 1.38, depth: 1.64, height: 2.88, color: '#44413e' },
  { x: 2.85, z: -1.55, width: 2.05, depth: 1.06, height: 1.57, color: '#3c3a38' },
  { x: -4.94, z: 2.19, width: 1.89, depth: 1.72, height: 3.36, color: '#403e3c' },
  { x: -2.57, z: 2.16, width: 1.38, depth: 1.64, height: 4.32, color: '#333333' },
  { x: -3.47, z: 4.35, width: 2.28, depth: 1.0, height: 1.32, color: '#4b4844' },
  { x: 4.77, z: 1.68, width: 1.92, depth: 1.05, height: 1.45, color: '#464441' },
]

const windowColors = ['#5a5650', '#99765a', '#ffca80', '#c29971', '#fff1da', '#756d62']

export function createCityModel(compact: boolean) {
  const surfaces: CityInstance[] = []
  const lights: CityInstance[] = []
  const trees: CityInstance[] = []
  const add = (array: CityInstance[], position: Coordinates, scale: Coordinates, color: string) =>
    array.push({ position, scale, color })

  add(surfaces, [0, -0.65, 0], [13.92, 0.45, 10.48], '#221e1b')
  add(surfaces, [0, -0.41, 0], [14.15, 0.06, 10.73], '#79503a')
  add(lights, [0, -0.38, 0], [14.19, 0.026, 10.78], '#bf713f')
  add(surfaces, [0, -0.24, 0], [14.4, 0.30, 10.96], '#36312d')
  add(surfaces, [0, -0.065, 0], [14.48, 0.13, 11.04], '#5e5750')
  add(surfaces, [0, 0.008, 0], [13.73, 0.016, 10.3], '#1d1d1d')
  add(lights, [0, -0.92, 0], [12.9, 0.026, 9.7], '#865035')

  for (const x of [-3.77, 3.77]) {
    for (const z of [-2.92, 2.92]) {
      add(surfaces, [x, 0.065, z], [6.00, 0.13, 4.46], '#605a54')
      add(surfaces, [x, 0.145, z], [5.72, 0.035, 4.18], '#484543')
    }
  }

  for (let x = -6.45; x < 6.65; x += 0.57) {
    if (Math.abs(x) > 1.34) add(lights, [x, 0.025, 0], [0.24, 0.009, 0.035], '#a29a8e')
  }
  for (let z = -4.8; z < 5; z += 0.57) {
    if (Math.abs(z) > 1.34) add(lights, [0, 0.025, z], [0.035, 0.009, 0.24], '#a29a8e')
  }
  for (const edge of [-1.03, 1.03]) {
    for (let stripe = -2; stripe <= 2; stripe++) {
      add(lights, [edge, 0.026, stripe * 0.2], [0.28, 0.009, 0.085], '#d0c7b9')
      add(lights, [stripe * 0.2, 0.026, edge], [0.085, 0.009, 0.28], '#d0c7b9')
    }
  }

  towers.forEach(({ x, z, width, depth, height, color }, building) => {
    const ground = 0.2
    add(surfaces, [x, ground, z], [width + 0.23, 0.12, depth + 0.2], '#69645d')
    add(surfaces, [x, ground + height / 2, z], [width, height, depth], color)
    add(surfaces, [x, ground + height, z], [width + 0.07, 0.085, depth + 0.07], '#79736c')
    add(surfaces, [x, ground + height + 0.065, z], [width * 0.82, 0.075, depth * 0.82], '#3f3c3a')
    add(surfaces, [x - width * 0.16, ground + height + 0.19, z - depth * 0.15], [width * 0.32, 0.24, depth * 0.29], '#726a63')
    if (height > 4) {
      add(lights, [x, ground + height + 0.02, z + depth / 2], [width, 0.019, 0.03], '#c77b4e')
      add(surfaces, [x + width * 0.22, ground + height + 0.35, z + depth * 0.14], [0.036, 0.64, 0.036], '#a89a87')
      add(lights, [x + width * 0.22, ground + height + 0.67, z + depth * 0.14], [0.075, 0.055, 0.075], '#ffdcb2')
    }

    const floorSpacing = compact ? 0.56 : 0.41
    const acrossFront = Math.max(2, Math.round(width / 0.34))
    const acrossSide = Math.max(2, Math.round(depth / 0.34))
    for (let floor = 0; ground + 0.43 + floor * floorSpacing < height + 0.03; floor++) {
      const y = ground + 0.43 + floor * floorSpacing
      for (let column = 0; column < acrossFront; column++) {
        const tint = windowColors[(building * 7 + floor * 3 + column * 5) % windowColors.length]
        add(lights, [x + ((column + 0.5) / acrossFront - 0.5) * width, y, z + depth / 2 + 0.009],
          [width / acrossFront * 0.57, 0.17, 0.022], tint)
      }
      for (let column = 0; column < acrossSide; column++) {
        const tint = windowColors[(building * 5 + floor * 5 + column * 7) % windowColors.length]
        add(lights, [x + width / 2 + 0.009, y, z + ((column + 0.5) / acrossSide - 0.5) * depth],
          [0.022, 0.17, depth / acrossSide * 0.57], tint)
      }
    }
  })

  add(surfaces, [3.66, 0.189, 3.61], [4.5, 0.061, 2.37], '#4f5739')
  add(surfaces, [3.66, 0.228, 3.55], [4.34, 0.018, 0.34], '#96927a')
  add(surfaces, [3.67, 0.227, 3.63], [0.31, 0.018, 2.2], '#96927a')
  add(surfaces, [3.68, 0.25, 3.56], [0.93, 0.065, 0.83], '#676451')
  add(lights, [3.68, 0.287, 3.56], [0.75, 0.011, 0.63], '#a5a38b')
  add(surfaces, [-5.81, 0.18, 4.18], [0.97, 0.055, 1.37], '#515b3c')

  const treePositions: [number, number][] = [
    [-6.1, 3.68], [-5.73, 4.46], [-5.8, -1.06], [-2.89, -0.97], [-1.13, 4.55],
    [1.82, 4.48], [2.73, 4.49], [4.61, 4.5], [5.53, 4.39],
    [1.78, 2.69], [2.73, 2.65], [4.63, 2.71], [5.5, 2.8], [6.13, -0.99], [1.01, -3.33],
  ]
  treePositions.forEach(([x, z], index) => {
    if (compact && index % 4 === 0) return
    const size = 0.24 + (index % 3) * 0.041
    add(surfaces, [x, 0.35, z], [0.065, 0.355, 0.065], '#817257')
    add(trees, [x, 0.61, z], [size, size * 1.34, size], index % 2 ? '#68784f' : '#89925c')
    if (!compact) add(trees, [x + 0.07, 0.78, z - 0.035], [size * 0.76, size, size * 0.76], '#828d5a')
  })

  const lamps: [number, number][] = [[-0.88, -4.4], [0.88, -2.6], [-0.88, 1.71], [0.88, 4.45], [-5.65, 0.86], [3.6, 0.86], [5.8, 0.86]]
  lamps.forEach(([x, z], index) => {
    if (compact && index % 3 === 0) return
    add(surfaces, [x, 0.56, z], [0.047, 0.89, 0.047], '#7f7368')
    const arm = x < 0 ? 0.1 : -0.1
    add(surfaces, [x + arm, 1.0, z], [0.22, 0.038, 0.057], '#7f7368')
    add(lights, [x + arm * 1.75, 0.977, z], [0.12, 0.028, 0.075], index === 0 ? '#5a534d' : '#ffe0b3')
  })

  for (const x of [-6.16, 6.16]) {
    add(lights, [x, 0.024, 5.34], [0.65, 0.025, 0.035], '#c18155')
    add(lights, [x, 0.024, -5.34], [0.65, 0.025, 0.035], '#c18155')
  }
  return { surfaces, lights, trees }
}
