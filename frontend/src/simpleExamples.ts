import source from '../../models/simple-creation-examples-v1.json?raw'
import extraSource from '../../models/simple-creation-extra-examples-v1.json?raw'
import animaginePreview from './assets/simple-example-previews/animagine.webp?url'
import ponyPreview from './assets/simple-example-previews/pony.webp?url'
import fluxPreview from './assets/simple-example-previews/flux.webp?url'
import type { SimpleTemplateId } from './simpleCreation'

export const simpleExamplePreviews: Partial<Record<SimpleTemplateId, string>> = {
  animagine: animaginePreview,
  pony: ponyPreview,
  flux: fluxPreview,
}

type Example = {
  template_id: SimpleTemplateId
  template_version: number
  recipe_sha256: string
  image_sha256: string
  generated_at: string
  seed?: string
  environment: string
  observations: string[]
}
const images = import.meta.glob<string>('../../docs/guide/images/examples/*.png', {
  eager: true,
  query: '?url',
  import: 'default',
})
const recipes = import.meta.glob<string>('../../docs/guide/examples/*-v1.json', {
  eager: true,
  query: '?url',
  import: 'default',
})
export const simpleExamples = Object.fromEntries(
  ([...JSON.parse(source).examples, ...JSON.parse(extraSource).examples] as Example[]).map(
    (item) => [
      item.template_id,
      {
        ...item,
        image: images['../../docs/guide/images/examples/' + item.template_id + '.png'],
        download: recipes['../../docs/guide/examples/' + item.template_id + '-v1.json'],
      },
    ],
  ),
) as Partial<Record<SimpleTemplateId, Example & { image: string; download: string }>>
