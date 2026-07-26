import { useState } from "react";
import FeedAvatar from "./FeedAvatar";
import TypingIndicator from "./TypingIndicator";
import ImageLightbox from "./ImageLightbox";
import { useStages, stageLabel } from "../useStages";
import { reactToFeedPost, commentOnFeedPost, generateFeedPostImage } from "../api";

function timeAgo(iso) {
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "yesterday" : `${days}d ago`;
}

export default function FeedPostCard({ post, comments, characters, onChanged, imageGenEnabled }) {
  const stages = useStages();
  const [reactorId, setReactorId] = useState("");
  const [reacting, setReacting] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [commenting, setCommenting] = useState(false);
  const [error, setError] = useState("");
  const [generatingImage, setGeneratingImage] = useState(false);
  const [imageError, setImageError] = useState("");
  const [imageExpanded, setImageExpanded] = useState(false);

  const author = characters.find((c) => c.id === post.character_id);
  const reactorOptions = characters.filter((c) => c.id !== post.character_id);
  const reactingCharacter = characters.find((c) => c.id === reactorId);

  const handleReact = async () => {
    if (!reactorId) return;
    setReacting(true);
    setError("");
    try {
      await reactToFeedPost(post.id, reactorId);
      await onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setReacting(false);
    }
  };

  const handleGenerateImage = async () => {
    setGeneratingImage(true);
    setImageError("");
    try {
      await generateFeedPostImage(post.id);
      await onChanged();
    } catch (e) {
      setImageError(e.message);
    } finally {
      setGeneratingImage(false);
    }
  };

  const handleComment = async (e) => {
    e.preventDefault();
    if (!commentText.trim()) return;
    setCommenting(true);
    setError("");
    try {
      await commentOnFeedPost(post.id, commentText.trim());
      setCommentText("");
      await onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setCommenting(false);
    }
  };

  return (
    <div className="feed-post-card">
      <div className="feed-post-header">
        <FeedAvatar name={post.character_name} />
        <div className="feed-post-header-info">
          <div className="feed-post-header-top">
            <span className="feed-post-author">{post.character_name || "You"}</span>
            {author && <span className="feed-stage-badge">{stageLabel(stages, author.relationship_stage)}</span>}
          </div>
          <div className="feed-post-time">{timeAgo(post.created_at)}</div>
        </div>
      </div>
      <p className="feed-post-content">{post.content}</p>

      {post.image_path && (
        <details className="chat-reasoning" open>
          <summary>Generated image</summary>
          <img
            className="feed-post-image feed-post-image-clickable"
            src={post.image_path}
            alt="Generated scene"
            onClick={() => setImageExpanded(true)}
          />
          {imageExpanded && (
            <ImageLightbox name="Generated scene" src={post.image_path} onClose={() => setImageExpanded(false)} />
          )}
        </details>
      )}
      {imageGenEnabled && (
        <div className="feed-post-image-action">
          <button className="message-image-button" onClick={handleGenerateImage} disabled={generatingImage}>
            {generatingImage ? "Generating…" : post.image_path ? "🔄 Regenerate image" : "🖼️ Generate image"}
          </button>
          {imageError && <span className="message-image-error">{imageError}</span>}
        </div>
      )}

      <div className="feed-post-meta">
        <span>💬 {comments.length}</span>
      </div>

      {(comments.length > 0 || reacting) && (
        <div className="feed-comments">
          {comments.map((c) => (
            <div key={c.id} className="feed-comment">
              <FeedAvatar name={c.character_name} />
              <div>
                <span className="feed-comment-author">{c.character_name || "You"}</span>{" "}
                <span className="feed-comment-content">{c.content}</span>
              </div>
            </div>
          ))}
          {reacting && (
            <div className="feed-comment feed-comment-pending">
              <FeedAvatar name={reactingCharacter?.name} />
              <div>
                <span className="feed-comment-author">{reactingCharacter?.name}</span>
                <TypingIndicator />
              </div>
            </div>
          )}
        </div>
      )}

      {error && <p className="feed-error">{error}</p>}

      <div className="feed-post-actions">
        <select value={reactorId} onChange={(e) => setReactorId(e.target.value)} disabled={reacting}>
          <option value="">React as...</option>
          {reactorOptions.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button onClick={handleReact} disabled={reacting || !reactorId}>
          {reacting ? "Reacting…" : "React"}
        </button>
      </div>

      <form className="feed-comment-form" onSubmit={handleComment}>
        <input
          value={commentText}
          onChange={(e) => setCommentText(e.target.value)}
          placeholder="Add a comment..."
          disabled={commenting}
        />
        <button type="submit" disabled={commenting || !commentText.trim()}>
          {commenting ? "…" : "Comment"}
        </button>
      </form>
    </div>
  );
}
