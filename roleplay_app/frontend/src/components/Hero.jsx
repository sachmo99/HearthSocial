import { Link } from "react-router-dom";

export default function Hero() {
  return (
    <div className="hero">
      <div className="hero-glow" />
      <div className="hero-wordmark">
        <img className="brand-icon" src="/hearth-social-icon-512.png" alt="" />
        Hearth·Social.ai
      </div>
      <h2 className="hero-kicker">Role-Play</h2>
      <div className="hero-body">
        <h1 className="hero-headline">Come in from the cold. Someone kept the fire going.</h1>
        <p className="hero-sub">Warm, patient, always glad you came back.</p>
        <Link className="hero-feed-link" to="/feed">
          Visit the social feed &rarr;
        </Link>
      </div>
    </div>
  );
}
