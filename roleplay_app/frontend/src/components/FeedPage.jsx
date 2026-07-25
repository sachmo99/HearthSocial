import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import BackButton from "./BackButton";
import FeedAvatar from "./FeedAvatar";
import FeedPostCard from "./FeedPostCard";
import TypingIndicator from "./TypingIndicator";
import { getCharacters, getFeed, createFeedPost } from "../api";

export default function FeedPage() {
  const navigate = useNavigate();
  const [characters, setCharacters] = useState([]);
  const [posts, setPosts] = useState([]);
  const [composerCharacterId, setComposerCharacterId] = useState("");
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState("");

  const refresh = () => getFeed().then(setPosts);

  useEffect(() => {
    getCharacters().then((cs) => {
      setCharacters(cs);
      if (cs.length > 0) setComposerCharacterId(cs[0].id);
    });
    refresh();
  }, []);

  const handleNewPost = async () => {
    if (!composerCharacterId) return;
    setPosting(true);
    setError("");
    try {
      await createFeedPost(composerCharacterId);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setPosting(false);
    }
  };

  const topLevel = posts
    .filter((p) => p.parent_id === null)
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  const commentsByParent = {};
  for (const p of posts) {
    if (p.parent_id !== null) {
      (commentsByParent[p.parent_id] ||= []).push(p);
    }
  }

  const composerCharacter = characters.find((c) => c.id === composerCharacterId);

  return (
    <div className="app app-feed">
      <div className="feed-nav">
        <div className="feed-wordmark">ROLE·PLAY</div>
        <BackButton onClick={() => navigate("/")}>&larr; Back to characters</BackButton>
      </div>
      <div className="section-eyebrow">
        <span>Feed</span>
        <div className="section-eyebrow-line" />
      </div>

      <div className="feed-composer">
        <FeedAvatar name={composerCharacter?.name} />
        <select
          value={composerCharacterId}
          onChange={(e) => setComposerCharacterId(e.target.value)}
          disabled={posting}
        >
          {characters.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button onClick={handleNewPost} disabled={posting || !composerCharacterId}>
          {posting ? "Posting…" : "New post"}
        </button>
      </div>
      {error && <p className="feed-error">{error}</p>}

      <div className="feed-list">
        {posting && (
          <div className="feed-post-card feed-post-card-pending">
            <div className="feed-post-header">
              <FeedAvatar name={composerCharacter?.name} />
              <div className="feed-post-header-info">
                <div className="feed-post-header-top">
                  <span className="feed-post-author">{composerCharacter?.name}</span>
                </div>
                <div className="feed-post-time">Writing a post…</div>
              </div>
            </div>
            <TypingIndicator />
          </div>
        )}
        {topLevel.map((post) => (
          <FeedPostCard
            key={post.id}
            post={post}
            comments={(commentsByParent[post.id] || []).sort((a, b) => (a.created_at > b.created_at ? 1 : -1))}
            characters={characters}
            onChanged={refresh}
          />
        ))}
        {topLevel.length === 0 && <p className="feed-empty">No posts yet - write the first one.</p>}
      </div>
    </div>
  );
}
