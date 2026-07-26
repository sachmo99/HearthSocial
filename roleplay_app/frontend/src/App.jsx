import { Routes, Route } from "react-router-dom";
import HomePage from "./components/HomePage";
import ChatPage from "./components/ChatPage";
import FeedPage from "./components/FeedPage";
import HealthIndicator from "./components/HealthIndicator";
import UpdateBanner from "./components/UpdateBanner";
import "./App.css";

export default function App() {
  return (
    <>
      <HealthIndicator />
      <UpdateBanner />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat/:characterId" element={<ChatPage />} />
        <Route path="/feed" element={<FeedPage />} />
        <Route path="*" element={<HomePage />} />
      </Routes>
    </>
  );
}
