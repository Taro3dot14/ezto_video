import { useState } from "react";

interface Props {
  interrupt: Record<string, unknown>;
  threadId: string;
  onResume: (confirmations: Record<string, unknown>) => void;
}

const DEFAULT_CHECKLIST = [
  "视觉气质是否符合选定主题？",
  "节奏是否合适？信息密度是否恰当？",
  "内容驱动动画是否到位？",
  "双源原则：画面是否回了原文章抽细节？",
  "反 AI 味：有无紫粉渐变 / 圆角彩色边框 / emoji / 假数据？",
];

export default function ChapterReviewView({ interrupt, onResume }: Props) {
  const [checks, setChecks] = useState<Record<number, boolean>>({});
  const [feedback, setFeedback] = useState("");

  const checklist = (interrupt.checklist as string[]) || DEFAULT_CHECKLIST;
  const chapterId = interrupt.chapter_id as string | undefined;
  const chapterIdx = interrupt.chapter_index as number | undefined;
  const chapterLabel = chapterId || `第 ${chapterIdx ?? "?"} 章`;
  const isBatch = interrupt.type === "checkpoint_remaining_batch";
  const previewUrl = interrupt.preview_url as string | undefined;

  const allChecked = checklist.every((_, i) => checks[i]);
  const checkedCount = Object.values(checks).filter(Boolean).length;

  const handleConfirm = (approved: boolean) => {
    onResume({
      approved,
      feedback: approved ? null : feedback,
      checklist_results: checks,
    });
  };

  return (
    <div className="cr-view">
      <h3>
        {isBatch ? "批量验收" : "章节验收"}
        {!isBatch && <span className="cr-chapter">{chapterLabel}</span>}
      </h3>

      {previewUrl && (
        <div className="cr-preview">
          <a
            className="btn btn-primary btn-lg"
            href={previewUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            在新窗口预览 {chapterLabel} →
          </a>
        </div>
      )}

      <div className="cr-checklist">
        <h4>
          验收清单 <span className="cr-count">({checkedCount}/{checklist.length})</span>
        </h4>
        {checklist.map((item, i) => (
          <label key={i} className="check-item">
            <input
              type="checkbox"
              checked={!!checks[i]}
              onChange={() =>
                setChecks((prev) => ({ ...prev, [i]: !prev[i] }))
              }
            />
            <span>{item}</span>
          </label>
        ))}
      </div>

      <div className="cr-feedback">
        <h4>修改反馈（不通过时填写）</h4>
        <textarea
          className="np-textarea"
          placeholder="描述需要修改的内容…"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          rows={4}
        />
      </div>

      <div className="cr-actions">
        <button
          className="btn btn-primary"
          onClick={() => handleConfirm(true)}
        >
          通过，继续
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => handleConfirm(false)}
          disabled={!feedback.trim()}
        >
          不通过，返回修改
        </button>
      </div>
    </div>
  );
}
