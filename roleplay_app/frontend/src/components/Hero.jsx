import { Link } from "react-router-dom";

export default function Hero() {
  return (
    <div className="hero">
      <div className="hero-glow" />
      <div className="hero-wordmark">ROLE·PLAY</div>
      <div className="hero-body">
        <h1 className="hero-headline">Come in from the cold. Someone kept the fire going.</h1>
        <p className="hero-sub">Warm, patient, always glad you came back.</p>
        <Link className="hero-feed-link" to="/feed">
          See the feed &rarr;
        </Link>
      </div>
    </div>
  );
}
