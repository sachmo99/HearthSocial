import { Routes, Route } from "react-router-dom";
import HomePage from "./components/HomePage";
import ChatPage from "./components/ChatPage";
import "./App.css";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/chat/:characterId" element={<ChatPage />} />
      <Route path="*" element={<HomePage />} />
    </Routes>
  );
}
