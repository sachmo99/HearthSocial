import Modal from "./Modal";
import { stageLabel, stageThresholds } from "../useStages";

// Mirrors the stage set in backend/relationship_stages.json - update both together if stages change.
const TRUNK = ["stranger", "acquaintance", "friend", "confidant"];
const TRUNK_ICONS = { stranger: "🌫️", acquaintance: "🍵", friend: "🔥", confidant: "💫" };
const BRANCHES = [
  { key: "romantic", label: "💞 Romantic path", chain: ["partner", "spouse"] },
  { key: "family", label: "🏠 Family path", chain: ["family"] },
  { key: "taboo", label: "🌙 Taboo path", chain: ["taboo"] },
];

function subtitleFor(stages, id, status, live) {
  if (status === "current") return `Affection ${live.affection} · Closeness ${live.closeness}`;
  const { affection, closeness } = stageThresholds(stages, id);
  return status === "passed" ? `Cleared affection ${affection}+ · closeness ${closeness}+` : `Needs affection ${affection}+ · closeness ${closeness}+`;
}

// How far along the trunk (0-100%) toward the next mandatory stage, averaging the affection/
// closeness fractions - once branched off (or at confidant with nowhere left in the trunk to go),
// the trunk itself is fully walked, so this reads 100.
function trunkProgressPct(stages, currentStage, affection, closeness) {
  const idx = TRUNK.indexOf(currentStage);
  if (idx === -1 || idx === TRUNK.length - 1) return 100;
  const next = TRUNK[idx + 1];
  const cur = stageThresholds(stages, currentStage);
  const target = stageThresholds(stages, next);
  const affFrac = target.affection > cur.affection ? (affection - cur.affection) / (target.affection - cur.affection) : 1;
  const closeFrac = target.closeness > cur.closeness ? (closeness - cur.closeness) / (target.closeness - cur.closeness) : 1;
  return Math.max(0, Math.min(100, Math.round(((affFrac + closeFrac) / 2) * 100)));
}

function TrunkCard({ stages, id, status, live }) {
  return (
    <div className={`stage-map-trunk-card stage-map-status-${status}`}>
      <div className="stage-map-trunk-icon">{TRUNK_ICONS[id] || "•"}</div>
      <div className="stage-map-trunk-text">
        <div className="stage-map-trunk-name">{stageLabel(stages, id)}</div>
        <div className="stage-map-card-subtitle">{subtitleFor(stages, id, status, live)}</div>
      </div>
      {status === "current" && <div className="stage-map-here-now">here now</div>}
      {status === "passed" && <div className="stage-map-check">✓</div>}
    </div>
  );
}

function BranchCard({ stages, id, status, live }) {
  return (
    <div className={`stage-map-branch-card stage-map-status-${status}`}>
      <div className="stage-map-branch-name">
        {stageLabel(stages, id)}
        {status === "current" && <span className="stage-map-here-now-inline"> · here now</span>}
      </div>
      <div className="stage-map-card-subtitle">{subtitleFor(stages, id, status, live)}</div>
    </div>
  );
}

export default function RelationshipStageMap({ characterName, state, stages, onClose }) {
  const currentStage = state.relationship_stage;
  const live = { affection: state.character_affection, closeness: state.character_closeness };

  const trunkIdx = TRUNK.indexOf(currentStage);
  const currentTrunkIdx = trunkIdx === -1 ? TRUNK.length : trunkIdx;
  const trunkStatus = (i) => (i < currentTrunkIdx ? "passed" : i === currentTrunkIdx ? "current" : "ahead");
  const leadTrunk = TRUNK.slice(0, -1);
  const lastIdx = TRUNK.length - 1;
  const lastId = TRUNK[lastIdx];

  const progressPct = trunkProgressPct(stages, currentStage, state.character_affection, state.character_closeness);

  return (
    <Modal>
      <div className="stage-map-sheet">
        <div className="stage-map-header">
          <div className="stage-map-title">Relationship Path — {characterName}</div>
          <button className="stage-map-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="stage-map-stats-line">
          ❤️ {state.character_affection} affection · 🤝 {state.character_closeness} closeness
          {state.character_mood && <> · 🎭 {state.character_mood} mood</>}
        </div>
        <div className="stage-map-progress-track">
          <div className="stage-map-progress-fill" style={{ width: `${progressPct}%` }} />
        </div>

        <div className="stage-map-trunk">
          {leadTrunk.map((id, i) => (
            <div className="stage-map-trunk-step" key={id}>
              <TrunkCard stages={stages} id={id} status={trunkStatus(i)} live={live} />
              <div className="stage-map-trunk-connector" />
            </div>
          ))}

          {/* Branches nest directly under confidant in the DOM, not just centered under the row,
              so the fork always points from confidant regardless of trunk wrapping/width. */}
          <div className="stage-map-confidant-column">
            <TrunkCard stages={stages} id={lastId} status={trunkStatus(lastIdx)} live={live} />

            <div className="stage-map-fork-lead" />
            <div className="stage-map-fork-bar" />

            <div className="stage-map-branches">
              {BRANCHES.map((branch) => {
                const chainIdx = branch.chain.indexOf(currentStage);
                return (
                  <div className="stage-map-branch" key={branch.key}>
                    <div className="stage-map-branch-label">{branch.label}</div>
                    {branch.chain.map((id, i) => {
                      const status = id === currentStage ? "current" : chainIdx !== -1 ? (i < chainIdx ? "passed" : "ahead") : "alternate";
                      return (
                        <div className="stage-map-branch-step" key={id}>
                          <BranchCard stages={stages} id={id} status={status} live={live} />
                          {i < branch.chain.length - 1 && <div className="stage-map-branch-connector" />}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="stage-map-legend">Filled = reached · dashed = ahead on your current path · faded solid = a branch you haven't taken</div>
      </div>
    </Modal>
  );
}
