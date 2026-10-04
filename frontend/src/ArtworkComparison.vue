<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ratingLabels, type ComparisonArtwork } from './artworkComparison'
const props = defineProps<{ items: ComparisonArtwork[] }>()
const emit = defineEmits<{ remove: [id: string]; inspect: [item: ComparisonArtwork]; clear: [] }>()
const missing = ref<string[]>([])
watch(() => props.items, () => { missing.value = [] })
const display = (v: unknown) => v === null || v === undefined || v === '' ? '未知／未設定' : typeof v === 'string' ? v : JSON.stringify(v)
const fields = computed(() => {
  const values = [
    ['流程', (v: ComparisonArtwork) => v.workflow_id || '舊紀錄／流程 ID 未知'],
    ['原引擎', (v: ComparisonArtwork) => v.engine_url], ['模型', (v: ComparisonArtwork) => v.checkpoint],
    ['提交時版本', (v: ComparisonArtwork) => v.model_version],
    ['輸出尺寸', (v: ComparisonArtwork) => `${v.width} × ${v.height}`],
    ['有序 LoRA／強度', (v: ComparisonArtwork) => v.lora_metadata?.map(l => `${l.name} (${l.version}) model ${l.strength_model} / CLIP ${l.strength_clip}`).join('\n') || '無／舊紀錄未知'],
    ...Object.entries({ seed: 'Seed', steps: 'Steps', cfg: 'CFG', sampler: 'Sampler', scheduler: 'Scheduler', denoise: 'Denoise', prompt: '畫面描述', negative_prompt: '負面提示詞' }).map(([key,label]) => [label, (v: ComparisonArtwork) => v.parameters[key as keyof ComparisonArtwork['parameters']]]),
  ] as [string, (v: ComparisonArtwork) => unknown][]
  return values.map(([label, get]) => { const entries = props.items.map(v => display(get(v))); return { label, entries, differs: new Set(entries).size > 1 } })
})
</script>
<template>
  <section v-if="items.length" class="panel comparison" aria-label="作品並排比較">
    <div class="comparison-heading"><h2>作品比較 · {{ items.length }} / 4</h2><button class="secondary" @click="emit('clear')">清空比較選擇</button></div>
    <p class="footnote">原圖等高完整顯示；不同輸出尺寸不代表相同 latent 尺寸。可跨模型比較，結果是人工觀察。篩選作品不會清除選擇，窄視窗可橫向捲動。</p>
    <p v-if="items.length < 2" role="status">再選一張作品即可查看差異。</p>
    <div class="comparison-scroll"><div class="comparison-images" :style="{ gridTemplateColumns: `repeat(${items.length}, minmax(240px, 1fr))` }">
      <article v-for="item in items" :key="item.id"><h3>{{ item.title }}</h3><img v-if="item.image_available && !missing.includes(item.id)" :src="`/api/artworks/${item.id}/image`" :alt="item.title" @error="missing.push(item.id)"><p v-else class="notice warning">原圖不可用；參數及評分仍保留。</p>
        <dl><template v-for="(label,key) in ratingLabels" :key="key"><dt>{{ label }}</dt><dd>{{ item.ratings[key] === null ? '未評分／不適用' : item.ratings[key] + ' / 5' }}</dd></template></dl>
        <button class="secondary" :aria-label="'預覽及評分：' + item.title" @click="emit('inspect',item)">預覽及評分</button><button class="secondary" :aria-label="'移出比較：' + item.title" @click="emit('remove',item.id)">移出比較</button>
      </article>
    </div><table><caption>完整參數差異；「不同」以文字標示</caption><thead><tr><th>欄位</th><th v-for="item in items" :key="item.id">{{ item.title }}</th></tr></thead><tbody><tr v-for="field in fields" :key="field.label"><th>{{ field.label }}{{ field.differs ? '（不同）' : '' }}</th><td v-for="(value,i) in field.entries" :key="i">{{ value }}</td></tr></tbody></table></div>
  </section>
</template>
<style scoped>
.comparison{margin:24px 0;min-width:0}.comparison-heading{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.comparison-scroll{overflow-x:auto}.comparison-images{display:grid;gap:16px;margin:18px 0}.comparison-images article{min-width:0;overflow-wrap:anywhere}.comparison-images h3{font-size:13px}.comparison-images img{width:100%;height:260px;object-fit:contain;background:var(--surface-input)}dl{display:grid;grid-template-columns:1fr auto;font-size:12px;gap:8px}dd{margin:0}button{margin:4px 8px 4px 0}table{width:100%;min-width:600px;table-layout:fixed;border-collapse:collapse;font-size:12px}caption{text-align:left;padding:14px 0}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--border-control);white-space:pre-wrap;overflow-wrap:anywhere;vertical-align:top}th{color:var(--text-notice)}
</style>
