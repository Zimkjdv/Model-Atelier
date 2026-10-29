import recipeSource from '../../models/simple-creation-templates-v1.json?raw'
import type { TemplateSelection } from './templateContext'
import ponySource from '../../models/pony-v6-xl.json?raw'
import animagineSource from '../../models/animagine-xl-4.0-opt.json?raw'
import fluxSource from '../../models/flux1-schnell-plan.json?raw'
import type { CreationForm } from './creationSettings'
import type { FluxForm } from './fluxSettings'

type Manifest = { filename: string; sha256: string }
export type SimpleTemplateId = 'animagine' | 'pony' | 'flux'
export type SimpleFamily = 'checkpoint' | 'flux'
export type SimpleTransfer = {
  token: number
  settings: CreationForm | FluxForm
  templateSelection?: TemplateSelection | null
}
export type SimpleTemplate = {
  id: SimpleTemplateId
  version: 1
  reference: string
  title: string
  model: string
  description: string
  note: string
  family: SimpleFamily
  presetId?: string
  manifest?: Manifest
  prompt: string
  negative: string
  seed: string
}

const manifests: Record<string, Manifest> = {
  'pony-v6-xl.json': JSON.parse(ponySource),
  'animagine-xl-4.0-opt.json': JSON.parse(animagineSource),
}
export const simpleTemplates: SimpleTemplate[] = JSON.parse(recipeSource).templates.map(
  (item: SimpleTemplate & { manifest_file?: string }) => ({
    ...item,
    manifest: item.manifest_file ? manifests[item.manifest_file] : undefined,
  }),
)

export const simpleFluxComponents: {
  role: 'diffusion_model' | 'clip_l' | 't5xxl' | 'vae'
  category: string
  filename: string
  sha256: string
}[] = JSON.parse(fluxSource).components

export type ListedModel = {
  name: string
  listed: boolean
  architecture?: string
  sha256?: string
}

// A filename alone must never select another model variant.
export function matchSimpleModel(
  models: ListedModel[],
  expected: Manifest,
  architecture?: string,
): ListedModel | undefined {
  const matches = models.filter(
    (model) =>
      model.listed &&
      model.sha256 === expected.sha256 &&
      (!architecture || model.architecture === architecture),
  )
  return (
    matches.find((model) => model.name === expected.filename) ||
    matches.sort((a, b) => a.name.localeCompare(b.name))[0]
  )
}
