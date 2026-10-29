import source from '../../models/simple-creation-examples-v1.json?raw'
import animagine from '../../docs/guide/images/examples/animagine.png?url'
import pony from '../../docs/guide/images/examples/pony.png?url'
import flux from '../../docs/guide/images/examples/flux.png?url'
import animagineRecipe from '../../docs/guide/examples/animagine-v1.json?url'
import ponyRecipe from '../../docs/guide/examples/pony-v1.json?url'
import fluxRecipe from '../../docs/guide/examples/flux-v1.json?url'
import type { SimpleTemplateId } from './simpleCreation'

type Example = {
  template_id: SimpleTemplateId
  template_version: number
  recipe_sha256: string
  image_sha256: string
  generated_at: string
  environment: string
  observations: string[]
}
const images = { animagine, pony, flux }
const recipes = { animagine: animagineRecipe, pony: ponyRecipe, flux: fluxRecipe }
export const simpleExamples = Object.fromEntries(
  (JSON.parse(source).examples as Example[]).map((item) => [
    item.template_id,
    { ...item, image: images[item.template_id], download: recipes[item.template_id] },
  ]),
) as Record<SimpleTemplateId, Example & { image: string; download: string }>
