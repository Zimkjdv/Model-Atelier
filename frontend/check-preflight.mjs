import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import ts from 'typescript'
const code = ts.transpileModule(
  await fs.readFile(new URL('./src/generationPreflight.ts', import.meta.url), 'utf8'),
  { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } },
).outputText
const { generationFieldProblems: check } = await import(
  'data:text/javascript;base64,' + Buffer.from(code).toString('base64')
)
const base = {
  title: 'Existing parameters',
  prompt: '',
  checkpoint: 'model',
  seed: '18446744073709551615',
  width: 1024,
  height: 1024,
  steps: 20,
  cfg: 7,
  denoise: 1,
  sampler_name: 'euler',
  scheduler: 'normal',
}
assert.deepEqual(check(base), {}) // Empty prompts and the full uint64 seed are supported by the API.
const before = JSON.stringify(base)
const bad = check({
  ...base,
  seed: '18446744073709551616',
  width: 899,
  height: 0,
  steps: 1.5,
  cfg: NaN,
})
assert.deepEqual(Object.keys(bad).sort(), ['cfg', 'height', 'seed', 'steps', 'width'])
assert.equal(JSON.stringify(base), before)
assert.equal(check({ ...base, seed: '01' }).seed, undefined)
assert.ok(check({ ...base, seed: '1e5' }).seed)
const limits = check(base, {
  bounds: { steps: { min: 1, max: 10 } },
  samplers: ['other'],
  schedulers: ['other'],
})
assert.deepEqual(Object.keys(limits).sort(), ['sampler_name', 'scheduler', 'steps'])
const flux = {
  ...base,
  diffusion_model: 'flux',
  clip_l: 'clip',
  t5xxl: 't5',
  vae: 'vae',
  steps: 4,
  width: 512,
  height: 512,
}
assert.deepEqual(check(flux), {})
assert.ok(check({ ...flux, width: 520, steps: 5 }).width)
assert.ok(check({ ...flux, clip_l: 'same', t5xxl: 'same' }).t5xxl)
assert.ok(
  check({
    ...flux,
    workflow_id: 'flux1-schnell-image2image-v1',
    image_asset_id: 'input',
    denoise: 1,
  }).denoise,
)
assert.ok(check({ ...base, mask_asset_id: 'same', image_asset_id: 'same' }).mask_asset_id)
const reference = check({
  ...base,
  ipadapter_name: '',
  clip_vision_name: '',
  image_asset_id: '',
  reference_start: 0.8,
  reference_end: 0.2,
  reference_weight: 3,
})
assert.deepEqual(Object.keys(reference).sort(), [
  'clip_vision_name',
  'image_asset_id',
  'ipadapter_name',
  'reference_end',
  'reference_weight',
])
const control = check({
  ...base,
  control_net_name: '',
  image_asset_id: '',
  control_start: 0,
  control_end: 1,
  control_strength: 0,
  canny_low: 0.9,
  canny_high: 0.1,
})
assert.deepEqual(Object.keys(control).sort(), [
  'canny_high',
  'control_net_name',
  'control_strength',
  'image_asset_id',
])
console.log(
  'Preflight preserves exact seeds, server limits, independent errors, capability bounds and workflow-specific fields.',
)
