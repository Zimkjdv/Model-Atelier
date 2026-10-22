import type { ExecutionDevice } from './environmentTypes'
export type RuntimeMetadata = {
  execution_device?: ExecutionDevice
  execution_context?: ExecutionContext
  schema_version: number; captured_at: string
  workflow: { id: string; sha256: string; nodes: string[]; node_versions: null; note: string }
  platform: { source: string; python: string; packages: { name: string; version: string | null }[] }
  engine: { status: string; source: string; comfyui: string | null; python: string | null; pytorch: string | null
    packages: { name: string; installed: string | null; required: string | null }[]
    cuda: string | null; driver: string | null; git_revision: string | null; note: string }
}

export type ExecutionContext={schema_version:1;workload:'inference';workflow_id:string
  geometry:{width:number|null;height:number|null;batch_size:number|null;source:string}
  parameters:{node_id:string;class_type:string;settings:Record<string,string|number>}[]
  models:{role:string;name:string|null;version:string|null;architecture:string|null;sha256:string|null}[]
  loras:unknown[]|null
  launch_policy:{source:string;reported:boolean;precision_flags:string[];memory_flags:string[]}
  actual_precision:null;actual_offload:null;cache_state:'unknown';note:string}
