export type TemplateSelection = {
  template_id: 'animagine' | 'pony' | 'flux'
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
