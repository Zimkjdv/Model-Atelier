// The four desktop ratios approved in docs/ui-redesign/preview.html.
export function outputPresets(family: string): number[][] {
  if (family === 'sd1')
    return [
      [512, 512],
      [576, 768],
      [768, 576],
      [768, 432],
    ]
  if (family === 'flux')
    return [
      [512, 512],
      [576, 768],
      [768, 576],
      [1024, 576],
    ]
  if (family === 'sdxl')
    return [
      [1024, 1024],
      [864, 1152],
      [1152, 864],
      [1536, 864],
    ]
  return []
}
