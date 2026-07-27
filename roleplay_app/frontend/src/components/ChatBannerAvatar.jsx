import { useState } from "react";
import { portraitStyle, portraitImageSrc, portraitImageSrcSet, initial } from "../theme";
import ImageLightbox from "./ImageLightbox";

export default function ChatBannerAvatar({ name }) {
  const [failed, setFailed] = useState(false);
  const [expanded, setExpanded] = useState(false);

  if (failed) {
    return (
      <div className="chat-banner-avatar chat-banner-avatar-fallback" style={portraitStyle(name)}>
        {initial(name)}
      </div>
    );
  }

  const src = portraitImageSrc(name);

  return (
    <>
      <img
        className="chat-banner-avatar chat-banner-avatar-clickable"
        src={src}
        srcSet={portraitImageSrcSet(name)}
        alt={name}
        onError={() => setFailed(true)}
        onClick={() => setExpanded(true)}
      />
      {expanded && <ImageLightbox name={name} src={src} onClose={() => setExpanded(false)} />}
    </>
  );
}
