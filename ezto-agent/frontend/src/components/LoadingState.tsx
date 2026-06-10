interface Props {
  message?: string;
}

export default function LoadingState({ message = "加载中…" }: Props) {
  return (
    <div className="loading-state">
      <div className="loading-spinner" />
      <p className="loading-message">{message}</p>
    </div>
  );
}
