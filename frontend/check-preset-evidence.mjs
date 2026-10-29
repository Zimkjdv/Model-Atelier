import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'

const source = await readFile(new URL('./src/presetEvidence.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText
const { presetEvidence } = await import(
  'data:text/javascript;base64,' + Buffer.from(output).toString('base64')
)
const settings = {
  width: 1024,
  height: 1024,
  steps: 28,
  cfg: 5,
  sampler_name: 'euler_ancestral',
  scheduler: 'normal',
  denoise: 1,
}
const form = {
  ...settings,
  prompt: 'new subject',
  loras: [],
  reference_ids: [],
  workflow_mode: 'text2image',
}
for (const validation of [
  'Pony: RTX 3060 12GB，768² 單張風景歷史已驗。',
  'Animagine: RTX 3060 12GB，1024² 單張風景歷史已驗。',
  '尚未逐模型實測。',
]) {
  const preset = { settings, validation }
  const original = JSON.stringify({ preset, form })
  assert.equal(presetEvidence(preset, form).summary, validation)
  assert.equal(presetEvidence(preset, { ...form, steps: 20 }).summary, validation)
  assert.match(presetEvidence(preset, { ...form, steps: 20 }).changes.join(' '), /取樣參數已修改/)
  assert.match(
    presetEvidence(preset, { ...form, loras: [{ enabled: true }] }).changes.join(' '),
    /不包含此組合/,
  )
  assert.doesNotMatch(
    presetEvidence(preset, { ...form, loras: [{ enabled: false }] }).changes.join(' '),
    /啟用 LoRA/,
  )
  assert.match(
    presetEvidence(preset, { ...form, workflow_mode: 'image2image' }).changes.join(' '),
    /不包含此流程/,
  )
  assert.match(presetEvidence(preset, form).changes.join(' '), /未判定目前描述/)
  assert.equal(JSON.stringify({ preset, form }), original)
}
assert.match(presetEvidence(null, form).summary, /沒有可用/)
assert.match(presetEvidence({ settings, validation: '' }, form).summary, /沒有可用/)
console.log(
  'Preset evidence uses the same backend statement and keeps current settings outside historical claims.',
)
