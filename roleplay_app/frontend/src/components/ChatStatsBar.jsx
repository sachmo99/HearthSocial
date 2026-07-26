import { useEffect, useRef, useState } from "react";
import { useStages, stageLabel } from "../useStages";

function MoodStat({ mood }) {
  const windowRef = useRef(null);
  const measureRef = useRef(null);
  const [marquee, setMarquee] = useState(false);
  const label = mood || "—";

  useEffect(() => {
    const windowEl = windowRef.current;
    const measureEl = measureRef.current;
    if (!windowEl || !measureEl) return;
    setMarquee(measureEl.scrollWidth > windowEl.clientWidth);
  }, [label]);

  return (
    <span className="stat stat-mood" title={mood || "Mood"}>
      🎭 Mood:
      <span className="stat-mood-window" ref={windowRef}>
        <span className="stat-mood-measure" ref={measureRef} aria-hidden="true">
          {label}
        </span>
        <span className={`stat-mood-track${marquee ? " stat-mood-track-marquee" : ""}`}>
          <span className="stat-mood-text">{label}</span>
          {marquee && (
            <span className="stat-mood-text" aria-hidden="true">
              {label}
            </span>
          )}
        </span>
      </span>
    </span>
  );
}

export default function ChatStatsBar({ state }) {
  const stages = useStages();
  return (
    <div className="chat-stats-bar">
      <span className="stat" title="Affection">
        ❤️ {state.character_affection}
      </span>
      <span className="stat" title="Closeness">
        🤝 {state.character_closeness}
      </span>
      <MoodStat mood={state.character_mood} />
      {typeof state.messages_until_summary === "number" && (
        <span className="stat" title="Messages until the next memory summary update">
          📝 {state.messages_until_summary}
        </span>
      )}
      {state.summarizing && (
        <span className="stat summarizing-badge" title="Updating memory/mood from recent conversation">
          ✍️ Summarizing…
        </span>
      )}
      <span className="stat stage-badge" title="Relationship stage">
        {stageLabel(stages, state.relationship_stage)}
      </span>
    </div>
  );
}
