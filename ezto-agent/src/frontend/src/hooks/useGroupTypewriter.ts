import { useEffect, useRef, useState } from "react";

export interface TypewriterItem {
  id: string;
  text: string;
  kind: string;
}

const TICK_MS = 18;

function charsPerTick(item: TypewriterItem): number {
  if (item.kind === "note") return item.text.length > 80 ? 8 : 4;
  if (item.kind === "phase") return item.text.length;
  if (item.text.length > 200) return 10;
  if (item.text.length > 80) return 5;
  return 2;
}

export function useGroupTypewriter(
  items: TypewriterItem[],
  options: { animate: boolean },
) {
  const revealedRef = useRef<Record<string, number>>({});
  const [revision, setRevision] = useState(0);

  const signature = items.map((i) => `${i.id}:${i.text.length}`).join("|");

  useEffect(() => {
    if (!options.animate) {
      for (const item of items) {
        revealedRef.current[item.id] = item.text.length;
      }
      setRevision((n) => n + 1);
      return;
    }

    const timer = window.setInterval(() => {
      let changed = false;

      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (i > 0) {
          const prev = items[i - 1];
          if ((revealedRef.current[prev.id] ?? 0) < prev.text.length) break;
        }

        const cur = revealedRef.current[item.id] ?? 0;
        if (cur < item.text.length) {
          revealedRef.current[item.id] = Math.min(
            item.text.length,
            cur + charsPerTick(item),
          );
          changed = true;
          break;
        }
      }

      if (changed) setRevision((n) => n + 1);
    }, TICK_MS);

    return () => clearInterval(timer);
  }, [signature, options.animate]);

  const isItemVisible = (index: number): boolean => {
    if (!options.animate) return true;
    if (index === 0) return true;
    const prev = items[index - 1];
    return (revealedRef.current[prev.id] ?? 0) >= prev.text.length;
  };

  const displayText = (item: TypewriterItem): string => {
    if (!options.animate) return item.text;
    const n = revealedRef.current[item.id] ?? 0;
    return item.text.slice(0, n);
  };

  const isTyping = (item: TypewriterItem, index: number): boolean => {
    if (!options.animate) return false;
    if (!isItemVisible(index)) return false;
    return (revealedRef.current[item.id] ?? 0) < item.text.length;
  };

  const isStreaming = options.animate && items.some((item, i) => isTyping(item, i));

  return { displayText, isTyping, isItemVisible, isStreaming, revision };
}
