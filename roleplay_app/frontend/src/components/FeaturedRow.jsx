import { useState } from "react";
import { portraitStyle, portraitImageSrc, portraitImageSrcSet, blurbFromPersona, initial } from "../theme";
import { useStages, stageLabel } from "../useStages";

function FeaturedPortrait({ name }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div className="featured-portrait featured-portrait-fallback" style={portraitStyle(name)}>
        <span>{initial(name)}</span>
      </div>
    );
  }
  return (
    <img
      className="featured-portrait"
      src={portraitImageSrc(name)}
      srcSet={portraitImageSrcSet(name)}
      alt={name}
      onError={() => setFailed(true)}
    />
  );
}

export default function FeaturedRow({ characters, onSelect }) {
  const stages = useStages();
  const featured = [...characters]
    .sort((a, b) => (b.message_count ?? 0) - (a.message_count ?? 0))
    .slice(0, 3);
  if (featured.length === 0) return null;

  return (
    <div className="featured-row">
      <div className="section-eyebrow">
        <span>Featured tonight</span>
      </div>
      <div className="featured-list">
        {featured.map((c, i) => (
          <button
            key={c.id}
            className={`featured-card${i % 2 === 1 ? " featured-card-reverse" : ""}`}
            onClick={() => onSelect(c)}
          >
            <FeaturedPortrait name={c.name} />
            <div className="featured-info">
              <div className="featured-info-top">
                <span className="featured-name">{c.name}</span>
                <span className="featured-stage-badge">{stageLabel(stages, c.relationship_stage)}</span>
              </div>
              <p className="featured-blurb">{blurbFromPersona(c.name, c.persona)}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
