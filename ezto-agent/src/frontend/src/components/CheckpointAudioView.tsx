interface Props {
  interrupt: Record<string, unknown>;
  threadId: string;
  onResume: (confirmations: Record<string, unknown>) => void;
}

export default function CheckpointAudioView({ interrupt, onResume }: Props) {
  const context = interrupt?.context as
    | { total_chapters?: number; total_steps?: number }
    | undefined;

  return (
    <div className="ca-view">
      <h3>Checkpoint Audio — 是否合成口播音频？</h3>

      <p className="ca-context">
        网页已完成，{context?.total_chapters ?? "?"} 章{' '}
        {context?.total_steps ?? "?"} 步。
      </p>

      <div className="ca-options">
        <div className="ca-option">
          <div className="ca-option-header">
            <span className="ca-option-icon">✓</span>
            <span>合成音频</span>
          </div>
          <p className="ca-option-desc">
            扫所有章节 narrations.ts → 生成 audio-segments.json →
            调 TTS provider 合成每步 mp3
          </p>
          <ul className="ca-features">
            <li>自动播放录屏，音视频天然同步</li>
            <li>内置 minimax (默认) + OpenAI TTS</li>
            <li>可换 ElevenLabs / edge-tts / Azure 等</li>
          </ul>
          <button
            className="btn btn-primary"
            onClick={() => onResume({ choice: "yes" })}
          >
            合成音频
          </button>
        </div>

        <div className="ca-option">
          <div className="ca-option-header">
            <span className="ca-option-icon">✗</span>
            <span>跳过合成</span>
          </div>
          <p className="ca-option-desc">
            不生成音频文件，手动录屏 + 后期配音
          </p>
          <button
            className="btn btn-secondary"
            onClick={() => onResume({ choice: "no" })}
          >
            跳过
          </button>
        </div>
      </div>
    </div>
  );
}
