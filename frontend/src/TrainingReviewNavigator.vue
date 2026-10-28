<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { trainingIssue, type Readiness, type TrainingImage } from './trainingTypes'

const props = defineProps<{
  datasetId: string
  images: TrainingImage[]
  report: Readiness | null
  selected: string
  busy: boolean
  dirty: boolean
  revision: number
}>()
const emit = defineEmits<{ select: [id: string, focus: boolean] }>()
const onlyPending = ref(true)
const search = ref(''),
  split = ref(''),
  code = ref(''),
  page = ref(0),
  issuePage = ref(0)
const issues = computed(() => [
  ...(props.report?.issues || []).map((v) => ({ ...v, blocking: true })),
  ...(props.report?.warnings || []).map((v) => ({ ...v, blocking: false })),
])
const codes = computed(() =>
  [...new Set(issues.value.filter((v) => v.image_id).map((v) => v.code))].sort(),
)
const byImage = computed(() => {
  const result = new Map<string, typeof issues.value>()
  for (const issue of issues.value) {
    if (issue.image_id) {
      const group = result.get(issue.image_id) || []
      group.push(issue)
      result.set(issue.image_id, group)
    }
  }
  return result
})
function matches(issue: (typeof issues.value)[number]) {
  return (
    !code.value ||
    (code.value === '__blocking'
      ? issue.blocking
      : code.value === '__warnings'
        ? !issue.blocking
        : issue.code === code.value)
  )
}
const filtered = computed(() => {
  const text = search.value.trim().toLocaleLowerCase()
  return props.images.filter(
    (row) =>
      (!onlyPending.value || byImage.value.has(row.id)) &&
      (!split.value || row.split === split.value) &&
      (!text ||
        [row.id, row.path, row.group_id].some((v) => v.toLocaleLowerCase().includes(text))) &&
      (!code.value || (byImage.value.get(row.id) || []).some(matches)),
  )
})
const visible = computed(() => filtered.value.slice(page.value * 20, (page.value + 1) * 20))
const filteredIds = computed(() => new Set(filtered.value.map((v) => v.id)))
const imageIssues = computed(() =>
  issues.value.filter((v) => v.image_id && filteredIds.value.has(v.image_id) && matches(v)),
)
const visibleIssues = computed(() =>
  imageIssues.value.slice(issuePage.value * 50, (issuePage.value + 1) * 50),
)
const globalIssues = computed(() => issues.value.filter((v) => !v.image_id))
const blockingImages = computed(() =>
  props.images.filter((row) => (byImage.value.get(row.id) || []).some((v) => v.blocking)),
)
watch([search, split, code, onlyPending], () => {
  page.value = 0
  issuePage.value = 0
})
watch(
  () => [filtered.value.length, imageIssues.value.length],
  () => {
    page.value = Math.min(page.value, Math.max(0, Math.ceil(filtered.value.length / 20) - 1))
    issuePage.value = Math.min(
      issuePage.value,
      Math.max(0, Math.ceil(imageIssues.value.length / 50) - 1),
    )
  },
)
function clear() {
  onlyPending.value = false
  search.value = ''
  split.value = ''
  code.value = ''
  page.value = 0
  issuePage.value = 0
}
async function locate(id: string) {
  const index = props.images.findIndex((v) => v.id === id)
  if (props.busy || index < 0) return
  clear()
  await nextTick()
  page.value = Math.floor(index / 20)
  emit('select', id, true)
}
watch(
  () => props.selected,
  (id) => {
    const index = filtered.value.findIndex((v) => v.id === id)
    if (index >= 0) page.value = Math.floor(index / 20)
  },
  { flush: 'post' },
)
function nextIssue() {
  const rows = blockingImages.value
  if (rows.length)
    locate(rows[(rows.findIndex((v) => v.id === props.selected) + 1) % rows.length]!.id)
}
</script>

<template>
  <section class="review-navigation" aria-label="圖片與缺項導覽">
    <div class="image-choices"
      ><button
        v-for="row in visible"
        :key="row.id"
        class="secondary"
        type="button"
        :disabled="busy"
        :aria-pressed="selected === row.id"
        @click="emit('select', row.id, false)"
        ><span v-if="byImage.has(row.id)" class="pending-dot" aria-hidden="true"></span
        ><img
          v-if="row.split !== 'test'"
          :src="
            '/api/training/datasets/' + datasetId + '/images/' + row.id + '?revision=' + revision
          "
          alt=""
          loading="lazy"
          class="review-thumb"
        />{{ row.id }} · {{ row.split }}</button
      ></div
    >
    <label class="pending-filter"
      ><input type="checkbox" v-model="onlyPending" :disabled="busy" />只顯示待補項目</label
    >
    <details class="review-navigation-details"
      ><summary>圖片篩選與完整缺項</summary> <h3>圖片與缺項導覽</h3
      ><div class="review-progress"
        ><span
          >{{ images.length - blockingImages.length }} / {{ images.length }} 已通過阻擋項檢查</span
        ><progress
          :max="images.length || 1"
          :value="images.length - blockingImages.length"
          aria-label="資料檢查進度"
        ></progress
      ></div>
      <p class="footnote"
        >缺項依已保存修訂 {{ revision }} 的後端檢查；{{
          dirty ? '目前編輯尚未保存，缺項不會隨輸入消失。' : '來源變更後仍需重新檢查。'
        }}篩選與定位不更改標註。</p
      >
      <fieldset :disabled="busy" class="filters">
        <legend>篩選圖片</legend>
        <label
          >搜尋圖片<input v-model="search" placeholder="圖片 ID、檔名或原作群組" maxlength="1024"
        /></label>
        <label
          >篩選圖片用途<select v-model="split" aria-label="篩選圖片用途"
            ><option value="">全部用途</option
            ><option value="train">訓練候選</option
            ><option value="validation">開發評估</option
            ><option value="test">最終評估</option
            ><option value="excluded">排除</option></select
          ></label
        >
        <label
          >缺項篩選<select v-model="code" aria-label="缺項篩選"
            ><option value="">全部圖片</option
            ><option value="__blocking">有阻擋缺項</option
            ><option value="__warnings">有提醒</option
            ><option v-for="value in codes" :key="value" :value="value">{{
              trainingIssue[value] || value
            }}</option></select
          ></label
        >
      </fieldset>
      <div class="actions"
        ><button class="secondary" type="button" :disabled="busy" @click="clear"
          >清除圖片篩選</button
        ><button
          class="secondary"
          type="button"
          :disabled="busy || !blockingImages.length"
          @click="nextIssue"
          >下一張有阻擋缺項</button
        ></div
      >
      <p role="status"
        >篩選結果 {{ filtered.length }} / {{ images.length }} 張 · 有阻擋缺項
        {{ blockingImages.length }} 張</p
      >
      <p v-if="!filtered.length">沒有符合條件的圖片；可清除篩選。已選圖片與未保存編輯仍保留。</p>
      <p v-if="selected && !filteredIds.has(selected)" class="footnote"
        >目前編輯 {{ selected }} 不在篩選結果內，標註仍保留。</p
      >
      <div class="actions"
        ><button class="secondary" type="button" :disabled="busy || page === 0" @click="page--"
          >上一頁圖片</button
        ><span>第 {{ page + 1 }} / {{ Math.max(1, Math.ceil(filtered.length / 20)) }} 頁圖片</span
        ><button
          class="secondary"
          type="button"
          :disabled="busy || (page + 1) * 20 >= filtered.length"
          @click="page++"
          >下一頁圖片</button
        ></div
      >
      <details v-if="globalIssues.length"
        ><summary>資料集層級問題（{{ globalIssues.length }}）</summary
        ><ul
          ><li v-for="(issue, index) in globalIssues" :key="index"
            >{{ issue.blocking ? '阻擋' : '提醒' }}：{{
              trainingIssue[issue.code] || issue.code
            }}</li
          ></ul
        ></details
      >
      <details>
        <summary>符合篩選的圖片缺項（{{ imageIssues.length }}）</summary>
        <ul class="issue-list"
          ><li v-for="(issue, index) in visibleIssues" :key="index"
            ><span
              >{{ issue.blocking ? '阻擋' : '提醒' }} · {{ issue.image_id }}：{{
                trainingIssue[issue.code] || issue.code
              }}</span
            ><button
              class="secondary"
              type="button"
              :disabled="busy"
              :aria-label="`定位 ${issue.image_id}：${trainingIssue[issue.code] || issue.code}`"
              @click="locate(issue.image_id!)"
              >定位圖片</button
            ></li
          ></ul
        >
        <p v-if="!imageIssues.length">此篩選下沒有圖片缺項；不代表整份資料出口或品質通過。</p>
        <div class="actions"
          ><button
            class="secondary"
            type="button"
            :disabled="busy || issuePage === 0"
            @click="issuePage--"
            >上一頁缺項</button
          ><span
            >第 {{ issuePage + 1 }} /
            {{ Math.max(1, Math.ceil(imageIssues.length / 50)) }} 頁缺項</span
          ><button
            class="secondary"
            type="button"
            :disabled="busy || (issuePage + 1) * 50 >= imageIssues.length"
            @click="issuePage++"
            >下一頁缺項</button
          ></div
        >
      </details>
    </details></section
  >
</template>

<style scoped>
.review-navigation {
  margin: 20px 0;
  min-width: 0;
}
.filters {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
label {
  display: grid;
  gap: 7px;
  font-size: 12px;
}
input,
select {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}
.actions,
.image-choices {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin: 14px 0;
}
.actions span,
p,
li {
  overflow-wrap: anywhere;
}
.issue-list {
  padding-left: 20px;
}
.issue-list li {
  margin: 10px 0;
}
.issue-list button {
  margin-left: 12px;
}
button[aria-pressed='true'] {
  outline: 2px solid #a7c296;
}
details {
  margin: 12px 0;
}
@media (max-width: 850px) {
  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
