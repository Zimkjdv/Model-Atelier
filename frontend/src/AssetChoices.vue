<script setup lang="ts">
import { onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { apiJson, ApiError } from './apiClient'
import { createRequestScope } from './requestScope'
import type { ReferenceAsset } from './referenceSettings'

const props = defineProps<{ selectedIds: string[] }>()
const emit = defineEmits<{ items: [items: ReferenceAsset[]] }>()
const search = ref(''), busy = ref(false), error = ref(''), total = ref(0)
const next = ref<string | null>(null), previous = ref<string | null>(null)
const scope = createRequestScope()
let timer: ReturnType<typeof setTimeout>, mounted = false, firstActivation = true
async function load(cursor: string | null = null) {
  const read = scope.begin(); busy.value = true; error.value = ''
  try {
    const query = new URLSearchParams({ limit: '40', q: search.value, scope: 'active' })
    if (cursor) query.set('cursor', cursor)
    const page = await apiJson<{ items: ReferenceAsset[]; total: number; next_cursor: string | null; previous_cursor: string | null }>('library/assets?' + query, { signal: read.signal })
    const missing = [...new Set(props.selectedIds)].filter(id => id && !page.items.some(item => item.id === id))
    const selected = await Promise.all(missing.map(async id => {
      try { return await apiJson<ReferenceAsset>('assets/' + id, { signal: read.signal }) }
      catch (e) { if (e instanceof ApiError && e.status === 404) return null; throw e }
    }))
    if (!read.isCurrent()) return
    emit('items', [...page.items, ...selected.filter((v): v is ReferenceAsset => v !== null)])
    total.value = page.total; next.value = page.next_cursor; previous.value = page.previous_cursor
  } catch (e) { if (read.isCurrent()) error.value = e instanceof Error ? e.message : '素材讀取失敗' }
  finally { if (read.isCurrent()) busy.value = false }
}
watch(search, () => { clearTimeout(timer); scope.cancel(); busy.value = true; timer = setTimeout(() => void load(), 250) })
watch(() => props.selectedIds.join(','), () => { if (mounted) void load() })
onMounted(() => { mounted = true; void load() })
onActivated(() => { if (firstActivation) firstActivation = false; else void load() })
onDeactivated(() => { clearTimeout(timer); scope.cancel(); busy.value = false })
onBeforeUnmount(() => { clearTimeout(timer); scope.dispose() })
</script>
<template>
  <section aria-label="素材選取清單" class="panel">
    <label>搜尋可選素材<input v-model="search" type="search" maxlength="200" placeholder="輸入素材名稱"></label>
    <div class="asset-page-actions"><button type="button" class="secondary" :disabled="busy || !previous" @click="load(previous)">上一批素材</button><button type="button" class="secondary" :disabled="busy || !next" @click="load(next)">下一批素材</button><button type="button" class="secondary" :disabled="busy" @click="load()">更新素材選項</button></div>
    <p class="footnote" role="status">{{ busy ? '讀取素材選項中…' : total + ' 張符合，每次最多顯示 40 張；已選素材跨頁保留。' }}</p>
    <p v-if="error" class="notice warning" role="alert">{{ error }}</p>
  </section>
</template>
<style scoped>
label{display:grid;gap:8px;font-size:12px}.asset-page-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
</style>
