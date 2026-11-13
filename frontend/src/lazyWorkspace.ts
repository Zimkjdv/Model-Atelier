import { defineAsyncComponent, type Component } from 'vue'
import WorkspaceLoadNotice from './WorkspaceLoadNotice.vue'

export function lazyWorkspace<T extends Component>(loader: () => Promise<{ default: T }>): T {
  return defineAsyncComponent<T>({
    loader,
    loadingComponent: WorkspaceLoadNotice,
    errorComponent: WorkspaceLoadNotice,
    timeout: 15000,
  })
}
