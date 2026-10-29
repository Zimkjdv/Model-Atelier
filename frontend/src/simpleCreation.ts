import recipeSource from '../../models/simple-creation-templates-v1.json?raw'
import extraSource from '../../models/simple-creation-extra-templates-v1.json?raw'
import styleSource from '../../models/simple-style-templates-v1.json?raw'
import type {
  TemplateSelection,
  SimpleModelId,
  SimpleGroupId,
  SimpleTemplateId,
} from './templateContext'
import type { ReferenceForm } from './adapterSettings'
import loraSource from '../../models/pixel-art-lora-sdxl-comfy-v1.json?raw'
import adapterSource from '../../models/ip-adapter-plus-sdxl-vit-h.json?raw'
import visionSource from '../../models/clip-vision-vit-h.json?raw'
import ponySource from '../../models/pony-v6-xl.json?raw'
import animagineSource from '../../models/animagine-xl-4.0-opt.json?raw'
import fluxSource from '../../models/flux1-schnell-plan.json?raw'
import type { CreationForm } from './creationSettings'
import type { FluxForm } from './fluxSettings'

type Manifest = { filename: string; sha256: string }
export type { SimpleModelId, SimpleTemplateId } from './templateContext'
export type SimpleFamily = 'checkpoint' | 'flux' | 'reference'
export type SimpleTransfer = {
  token: number
  settings: CreationForm | FluxForm | ReferenceForm
  templateSelection?: TemplateSelection | null
}
export type SimpleTemplate = {
  id: SimpleTemplateId
  modelId: SimpleGroupId
  task?: 'lora' | 'reference'
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
export const simpleTemplates: SimpleTemplate[] = [
  ...JSON.parse(recipeSource).templates,
  ...JSON.parse(extraSource).templates,
  ...JSON.parse(styleSource).templates,
].map((item: SimpleTemplate & { manifest_file?: string; model_id?: SimpleGroupId }) => ({
  ...item,
  modelId: item.model_id || (item.id as SimpleModelId),
  manifest: item.manifest_file ? manifests[item.manifest_file] : undefined,
}))
export const simpleModelTemplates = simpleTemplates.filter((item) =>
  ['animagine', 'pony', 'flux'].includes(item.id),
)
export const simpleStyleTemplates = simpleTemplates.filter((item) => item.task)
export const simpleStyleLora: Manifest = JSON.parse(loraSource)
export const simpleReferenceParts: (Manifest & {
  role: 'ipadapter' | 'clip_vision'
  family: string
  architecture: string
})[] = [
  {
    ...JSON.parse(adapterSource),
    role: 'ipadapter',
    family: 'sdxl-plus-vit-h',
    architecture: 'sdxl',
  },
  {
    ...JSON.parse(visionSource),
    role: 'clip_vision',
    family: 'clip-vit-h-14',
    architecture: 'other',
  },
]

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
