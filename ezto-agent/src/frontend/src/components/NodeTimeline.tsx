interface Props {
  completedNodes: string[];
}

const NODE_LABELS: Record<string, string> = {
  wv_identify_input: "识别用户输入",
  wv_prepare_source_files: "产出初稿",
  wv_validate_script: "Script 自检",
  wv_repair_script: "Script 修复",
  wv_validate_outline: "Outline 自检",
  wv_repair_outline: "Outline 修复",
  wv_checkpoint_plan: "Checkpoint Plan",
  wv_scaffold_presentation: "页面初始化",
  wv_build_chapter_1: "构建第一章页面",
  wv_validate_chapter_1: "第 1 章自检",
  wv_repair_chapter_1: "第 1 章修复",
  wv_checkpoint_chapter_1: "第 1 章验收",
  wv_select_development_mode: "选择开发模式",
  wv_build_chapter_n: "构建完整页面",
  wv_validate_chapter_n: "第 N 章自检",
  wv_repair_chapter_n: "第 N 章修复",
  wv_checkpoint_chapter_n: "第 N 章验收",
  wv_checkpoint_remaining_batch: "批量验收",
  wv_transition_to_phase3: "进入 Phase 3",
  wv_checkpoint_audio: "Checkpoint Audio",
  wv_extract_narrations: "提取 Narrations",
  wv_checkpoint_audio_segments: "检查音频分段",
  wv_synthesize_audio: "合成音频",
  wv_report_audio_anomalies: "音频异常报告",
  wv_recording_guidance: "录屏指引",
};

export default function NodeTimeline({ completedNodes }: Props) {
  if (completedNodes.length === 0) return null;

  return (
    <div className="node-timeline">
      <h4 className="nt-title">节点执行记录</h4>
      <div className="nt-list">
        {completedNodes.map((node, i) => (
          <div key={node} className="nt-item">
            <span className="nt-index">{i + 1}</span>
            <span className="nt-name">{NODE_LABELS[node] || node}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
