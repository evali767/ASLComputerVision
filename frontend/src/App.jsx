import { Routes, Route, Navigate } from "react-router-dom";
import { AppProvider } from "./state/AppState";
import Layout from "./ui/Layout";
import Home from "./pages/Home";
import Learn from "./pages/Learn";
import Leaderboard from "./pages/Leaderboard";
import SparkleTrail from "./src/SparkleTrail";


export default function App() {
  return (
    <AppProvider>
    <>
      <SparkleTrail />
      {/* the rest of your app */}
    </>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/learn" element={<Learn />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </AppProvider>
  );
}