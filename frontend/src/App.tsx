import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import ProtectedRoute from "./layout/ProtectedRoute";
import AppShell from "./layout/AppShell";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import LiveMood from "./pages/LiveMood";
import Analytics from "./pages/Analytics";
import Companion from "./pages/Companion";
import Messages from "./pages/Messages";
import Friends from "./pages/Friends";
import Journal from "./pages/Journal";
import Recommendations from "./pages/Recommendations";
import Goals from "./pages/Goals";
import SOS from "./pages/SOS";
import GuardianPage from "./pages/Guardian";
import Profile from "./pages/Profile";
import Settings from "./pages/Settings";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/mood" element={<LiveMood />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/companion" element={<Companion />} />
            <Route path="/messages" element={<Messages />} />
            <Route path="/friends" element={<Friends />} />
            <Route path="/journal" element={<Journal />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="/goals" element={<Goals />} />
            <Route path="/sos" element={<SOS />} />
            <Route path="/guardian" element={<GuardianPage />} />
            <Route path="/profile" element={<Profile />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
