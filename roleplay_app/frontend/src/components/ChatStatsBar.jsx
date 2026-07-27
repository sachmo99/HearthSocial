import { useEffect, useRef, useState } from "react";
import { useStages, stageLabel } from "../useStages";
import { triggerSummarize } from "../api";
import RelationshipStageMap from "./RelationshipStageMap";

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

function SummarizeButton({ sessionId, summarizing, onRefresh }) {
  const [triggering, setTriggering] = useState(false);

  const handleClick = async () => {
    setTriggering(true);
    try {
      await triggerSummarize(sessionId);
      await onRefresh();
    } finally {
      setTriggering(false);
    }
  };

  return (
    <button
      className="summarize-now-button"
      onClick={handleClick}
      disabled={triggering || summarizing}
      title="Update memory/mood from the conversation so far, without waiting for the next automatic summary - useful before generating an image so it reflects the latest state"
    >
      🔄 Update memory
    </button>
  );
}

export default function ChatStatsBar({ state, sessionId, onRefresh, characterName }) {
  const stages = useStages();
  const [showStageMap, setShowStageMap] = useState(false);
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
      {sessionId && onRefresh && (
        <SummarizeButton sessionId={sessionId} summarizing={state.summarizing} onRefresh={onRefresh} />
      )}
      <button className="stat stage-badge" title="Relationship stage - click to see the possible paths" onClick={() => setShowStageMap(true)}>
        {stageLabel(stages, state.relationship_stage)}
      </button>
      {showStageMap && (
        <RelationshipStageMap characterName={characterName} state={state} stages={stages} onClose={() => setShowStageMap(false)} />
      )}
    </div>
  );
}
