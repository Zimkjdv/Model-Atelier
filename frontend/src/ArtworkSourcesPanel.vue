<script setup lang="ts">
import type { Artwork } from './artworkRecord'
import ComponentSnapshot from './ComponentSnapshot.vue'
import ControlEdgePreview from './ControlEdgePreview.vue'
import ControlSnapshot from './ControlSnapshot.vue'
import ExperimentSnapshot from './ExperimentSnapshot.vue'
import JobMeasurements from './JobMeasurements.vue'
import LoraSnapshot from './LoraSnapshot.vue'
import ReferenceComponentsSnapshot from './ReferenceComponentsSnapshot.vue'
import ReferenceSnapshot from './ReferenceSnapshot.vue'
import RuntimeSnapshot from './RuntimeSnapshot.vue'
import StructureOutput from './StructureOutput.vue'
import TemplateSnapshot from './TemplateSnapshot.vue'
import { referenceWorkflowId } from './adapterSettings'
import { controlEdgeWorkflowId, isControlWorkflow, structureWorkflowId } from './controlSettings'
import { isFluxExtension } from './fluxExtensions'
import { fluxWorkflowId } from './fluxSettings'
import { isInpaintWorkflow } from './inpaintSettings'
import {
  architectureLabel,
  fileHash,
  fileSize,
  metadataTime,
  safeMetadataUrl,
} from './modelMetadata'
import { imageWorkflowId } from './referenceSettings'

defineProps<{ artwork: Readonly<Artwork> }>()
</script>

<template>
  <section
    id="artwork-panel-sources"
    role="tabpanel"
    aria-labelledby="artwork-tab-sources"
    tabindex="0"
    class="artwork-extra"
  >
    <div class="artwork-source-actions">
      <a :href="`/api/artworks/${artwork.id}/workflow`">下載完整工作流程</a>
      <a :href="`/api/jobs/${artwork.job_id}`" target="_blank" rel="noopener">原始任務 JSON ↗</a>
    </div>
    <h3>生成設定</h3>
    <dl
      ><dt>Checkpoint</dt><dd>{{ artwork.checkpoint }}</dd
      ><dt>模型版本（提交時登記）</dt><dd>{{ artwork.model_version }}</dd
      ><dt>圖片尺寸</dt><dd>{{ artwork.width }} × {{ artwork.height }}</dd
      ><dt>Seed</dt><dd>{{ artwork.parameters.seed ?? '未知' }}</dd
      ><dt>Steps / CFG</dt
      ><dd>{{ artwork.parameters.steps ?? '未知' }} / {{ artwork.parameters.cfg ?? '未知' }}</dd
      ><dt>Sampler / Scheduler</dt
      ><dd
        >{{ artwork.parameters.sampler ?? '未知' }} /
        {{ artwork.parameters.scheduler ?? '未知' }}</dd
      ><dt>Denoise</dt><dd>{{ artwork.parameters.denoise ?? '未知' }}</dd></dl
    >
    <TemplateSnapshot :item="artwork.template_context" />
    <p v-if="!artwork.template_context" class="footnote"
      >此作品未記錄起始模板；不依圖片、檔名或目前模型推定來源。</p
    >
    <h3>畫面描述</h3>
    <p class="prompt">{{
      artwork.parameters.prompt ?? '無法從此工作流程解析，請查看完整 JSON。'
    }}</p>
    <h3>負面提示詞</h3>
    <p class="prompt">{{ artwork.parameters.negative_prompt || '未設定或無法解析' }}</p>
    <details class="model-snapshot"
      ><summary>提交時模型資料</summary>
      <template v-if="artwork.model_metadata"
        ><p class="footnote"
          >保留任務提交時的使用者登記，不隨模型庫後續編輯改動；不代表平台已驗證檔案、授權或相容性。</p
        ><dl>
          <dt>模型檔名</dt><dd>{{ artwork.model_metadata.name || '未知' }}</dd> <dt>登記版本</dt
          ><dd>{{ artwork.model_metadata.version?.trim() || '未知' }}</dd> <dt>登記架構</dt
          ><dd>{{ architectureLabel(artwork.model_metadata.architecture) }}</dd>
          <dt>模型檔案大小</dt><dd>{{ fileSize(artwork.model_metadata.size_bytes) }}</dd>
          <dt>模型檔案 SHA-256</dt
          ><dd class="file-hash">{{ fileHash(artwork.model_metadata.sha256) }}</dd> <dt>模型來源</dt
          ><dd
            ><a
              v-if="safeMetadataUrl(artwork.model_metadata.source_url)"
              :href="safeMetadataUrl(artwork.model_metadata.source_url)"
              target="_blank"
              rel="noopener noreferrer"
              >查看當時登記來源 ↗</a
            ><span v-else>未知</span></dd
          >
          <dt>授權名稱／標記</dt
          ><dd>{{ artwork.model_metadata.license_name?.trim() || '未知' }}</dd> <dt>授權條款網址</dt
          ><dd
            ><a
              v-if="safeMetadataUrl(artwork.model_metadata.license_url)"
              :href="safeMetadataUrl(artwork.model_metadata.license_url)"
              target="_blank"
              rel="noopener noreferrer"
              >查看當時登記條款 ↗</a
            ><span v-else>未知</span></dd
          >
          <dt>登記資料更新</dt
          ><dd>{{ metadataTime(artwork.model_metadata.metadata_updated_at) }}</dd> <dt>快照保存</dt
          ><dd>{{ metadataTime(artwork.model_metadata.captured_at) }}</dd>
        </dl></template
      >
      <p v-else class="footnote"
        >此作品尚無提交時的模型資料快照，當時架構、檔案識別及授權資訊未知。</p
      >
    </details>
    <LoraSnapshot
      v-if="
        !artwork.workflow_id ||
        artwork.workflow_id === 'checkpoint-text2image-v1' ||
        isFluxExtension(artwork.workflow_id) ||
        artwork.workflow_id === imageWorkflowId ||
        isInpaintWorkflow(artwork.workflow_id) ||
        isControlWorkflow(artwork.workflow_id)
      "
      :items="artwork.lora_metadata"
    />
    <a
      v-if="
        !artwork.workflow_id ||
        ['checkpoint-text2image-v1', imageWorkflowId, fluxWorkflowId].includes(artwork.workflow_id)
      "
      :href="`/api/artworks/${artwork.id}/settings-export`"
      >匯出創作設定（含來源快照）</a
    >
    <a
      v-if="
        isInpaintWorkflow(artwork.workflow_id) ||
        isControlWorkflow(artwork.workflow_id) ||
        artwork.workflow_id === referenceWorkflowId
      "
      :href="`/api/specialized/artworks/${artwork.id}/settings`"
      >匯出專用設定（含來源快照）</a
    >
    <ControlSnapshot
      v-if="isControlWorkflow(artwork.workflow_id)"
      :items="artwork.component_metadata"
    />
    <ReferenceComponentsSnapshot
      v-else-if="artwork.workflow_id === referenceWorkflowId"
      :items="artwork.component_metadata"
    />
    <ComponentSnapshot v-else :items="artwork.component_metadata" />
    <ExperimentSnapshot :item="artwork.experiment_context" />
    <RuntimeSnapshot :item="artwork.runtime_metadata" />
    <JobMeasurements :item="artwork.measurements" />
    <StructureOutput v-if="artwork.workflow_id === structureWorkflowId" :job-id="artwork.job_id" />
    <ControlEdgePreview
      v-if="artwork.workflow_id === controlEdgeWorkflowId"
      :key="artwork.id"
      :job-id="artwork.job_id"
      :artwork-id="artwork.id"
    />
    <p
      v-else-if="
        artwork.workflow_id !== structureWorkflowId && isControlWorkflow(artwork.workflow_id)
      "
      class="footnote"
      >舊版 v1 沒有保存同次邊緣輸出，不會重新計算歷史圖。</p
    >
    <ReferenceSnapshot
      :items="artwork.reference_metadata"
      :job-id="artwork.job_id"
      :processed-ready="true"
    />
    <details
      ><summary>作品來源紀錄</summary><p>原引擎：{{ artwork.engine_url }}</p
      ><p>任務：{{ artwork.job_id }}</p
      ><p>提交：{{ new Date(artwork.created_at).toLocaleString() }}</p
      ><p>匯入：{{ new Date(artwork.imported_at).toLocaleString() }}</p
      ><p class="file-hash">作品原圖 SHA-256：{{ artwork.sha256 }}</p></details
    ></section
  >
</template>

<style scoped>
.artwork-extra h3 {
  font-size: 13px;
  margin-top: 20px;
}
.artwork-extra dl {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 10px;
}
.artwork-extra dt {
  color: #9fb1a5;
}
.artwork-extra dd {
  margin: 0;
}
.prompt {
  white-space: pre-wrap;
  max-height: 220px;
  overflow: auto;
}
.artwork-extra details {
  margin-top: 24px;
}
.artwork-extra summary {
  cursor: pointer;
}
.model-snapshot a {
  color: #c5dfba;
}
.file-hash {
  font-family: monospace;
  line-height: 1.7;
}
</style>
