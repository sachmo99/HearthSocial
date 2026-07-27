import { useState } from "react";
import { portraitStyle, portraitImageSrc, portraitImageSrcSet, initial } from "../theme";

export default function FeedAvatar({ name }) {
  const [failed, setFailed] = useState(false);
  if (!name) {
    return <div className="feed-avatar feed-avatar-user">🧑</div>;
  }
  if (failed) {
    return (
      <div className="feed-avatar feed-avatar-fallback" style={portraitStyle(name)}>
        {initial(name)}
      </div>
    );
  }
  return (
    <img
      className="feed-avatar"
      src={portraitImageSrc(name)}
      srcSet={portraitImageSrcSet(name)}
      alt={name}
      onError={() => setFailed(true)}
    />
  );
}
