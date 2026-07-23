import { stageLabel } from "../theme";

export default function ChatStatsBar({ state }) {
  return (
    <div className="chat-stats-bar">
      <span className="stat" title="Affection">
        ❤️ {state.character_affection}
      </span>
      <span className="stat" title="Closeness">
        🤝 {state.character_closeness}
      </span>
      <span className="stat stat-mood" title={state.character_mood || "Mood"}>
        🎭 Mood: {state.character_mood || "—"}
      </span>
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
        {stageLabel(state.relationship_stage)}
      </span>
    </div>
  );
}
