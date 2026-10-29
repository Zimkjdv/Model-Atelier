export type SimpleModelId = 'animagine' | 'pony' | 'flux'
export type SimpleGroupId = SimpleModelId | 'style-lora' | 'style-reference'
export type SimpleTemplateId =
  | SimpleModelId
  | 'animagine-cafe'
  | 'animagine-adventurer'
  | 'animagine-kimono'
  | 'animagine-library'
  | 'pony-traveler'
  | 'pony-station'
  | 'pony-cat'
  | 'pony-city'
  | 'flux-workshop'
  | 'flux-island'
  | 'flux-traveler'
  | 'flux-robot'
  | 'style-lora'
  | 'style-reference'
export type TemplateSelection = {
  template_id: SimpleTemplateId
  template_version: 1
}
export type TemplateContext = {
  schema_version: 1
  origin: 'builtin_recipe'
  selection: TemplateSelection
  title: string
  model: string
  source: string
  reference: string
  quality_note: string
  recipe_sha256: string
  modified: boolean
  changed_fields: string[]
  baseline: Record<string, unknown>
}
export function templateSelection(context?: TemplateContext | null): TemplateSelection | null {
  return context?.selection ? { ...context.selection } : null
}
