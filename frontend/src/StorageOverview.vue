<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
type Volume = { id: string; path: string; total: number | null; free: number | null; status: string }
type Directory = { role: string; path: string; resolved_path: string | null; volume_id: string | null; status: string; error: string | null }
type Report = { checked_at: string; warnings: string[]; volumes: Volume[]; directories: Directory[]; totals: { total: number | null; free: number | null; volume_count: number; partial: boolean } }
const report = ref<Report | null>(null), busy = ref(false), error = ref('')
let controller: AbortController | null = null, alive = true
const gib = (value: number | null) => value === null ? '未知' : `${(value / 1024 ** 3).toFixed(2)} GiB`
async function refresh() {
  if (busy.value) return
  busy.value = true; error.value = ''; report.value = null; controller = new AbortController()
  try {
    const response = await fetch('/api/storage', { signal: controller.signal })
    if (!response.ok) throw new Error('磁碟容量無法更新，請稍後重試。')
    const value = await response.json()
    if (alive) report.value = value
  } catch (e) { if (alive) error.value = e instanceof Error ? e.message : '查詢失敗' }
  finally { if (alive) busy.value = false }
}
onMounted(refresh)
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <section class="panel storage-overview" aria-label="目錄與磁碟容量">
    <header><h2>目錄與磁碟容量</h2><button class="secondary" :disabled="busy" @click="refresh">{{ busy ? '讀取中…' : '更新磁碟容量' }}</button></header>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="report">
      <p>{{ report.totals.partial ? '部分可讀磁碟區' : '已去重磁碟區' }}：{{ report.totals.volume_count }} 個 · 可用 {{ gib(report.totals.free) }} / 總計 {{ gib(report.totals.total) }}</p>
      <small>{{ new Date(report.checked_at).toLocaleString() }} · 本機目錄快照</small>
      <article v-for="volume in report.volumes" :key="volume.id">
        <h3>{{ volume.path }}</h3><p>可用 {{ gib(volume.free) }} / 總計 {{ gib(volume.total) }}</p>
        <ul><li v-for="entry in report.directories.filter(d => d.volume_id === volume.id)" :key="entry.role + entry.path">
          <strong>{{ entry.role }}</strong><code>{{ entry.path }}</code><small v-if="entry.resolved_path !== entry.path">實際位置：{{ entry.resolved_path }}</small><span v-if="entry.error">{{ entry.error }}</span>
        </li></ul>
      </article>
      <article v-if="report.directories.some(d => !d.volume_id)"><h3>容量未知的目錄</h3>
        <ul><li v-for="entry in report.directories.filter(d => !d.volume_id)" :key="entry.role + entry.path"><strong>{{ entry.role }}</strong><code>{{ entry.path }}</code><span>{{ entry.error }}</span></li></ul>
      </article>
      <p v-for="warning in report.warnings" :key="warning" class="muted">{{ warning }}</p>
    </template>
  </section>
</template>
<style scoped>
.storage-overview { margin-top: 20px; } header { height:auto; padding:0; background:transparent; border:0; display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px; }
article { border-top:1px solid #303639; margin-top:16px; padding-top:8px; } li { margin:12px 0; } code, small, li span { display:block; overflow-wrap:anywhere; } p { line-height:1.6; }
</style>
