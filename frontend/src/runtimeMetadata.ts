export type RuntimeMetadata = {
  schema_version: number; captured_at: string
  workflow: { id: string; sha256: string; nodes: string[]; node_versions: null; note: string }
  platform: { source: string; python: string; packages: { name: string; version: string | null }[] }
  engine: { status: string; source: string; comfyui: string | null; python: string | null; pytorch: string | null
    packages: { name: string; installed: string | null; required: string | null }[]
    cuda: string | null; driver: string | null; git_revision: string | null; note: string }
}
