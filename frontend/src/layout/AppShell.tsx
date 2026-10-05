import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAppStore } from "../state/appStore";

const NAV_ITEMS = [
  { to: "/", label: "Home", icon: "\u2302" },
  { to: "/mood", label: "My Mood", icon: "\u25CE" },
  { to: "/analytics", label: "Analytics", icon: "\u25A6" },
  { to: "/companion", label: "AI Companion", icon: "\u2726" },
  { to: "/messages", label: "Messages", icon: "\u2709" },
  { to: "/friends", label: "Friends", icon: "\u2637" },
  { to: "/journal", label: "Journal", icon: "\u270E" },
  { to: "/recommendations", label: "Recommendations", icon: "\u2725" },
  { to: "/goals", label: "Goals", icon: "\u2691" },
  { to: "/guardian", label: "Guardian", icon: "\u26E8" },
  { to: "/profile", label: "Profile", icon: "\u25A1" },
  { to: "/settings", label: "Settings", icon: "\u2699" },
];

export default function AppShell() {
  const user = useAppStore((s) => s.user);
  const logout = useAppStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="dot" />
          KeyMood AI
        </div>

        <ul className="nav-list">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                <span aria-hidden>{item.icon}</span>
                {item.label}
              </NavLink>
            </li>
          ))}
          <li>
            <NavLink to="/sos" className="nav-link sos-link">
              <span aria-hidden>&#9888;</span>
              SOS
            </NavLink>
          </li>
        </ul>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <span className="avatar">{user?.avatarInitials ?? "U"}</span>
            <div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{user?.name}</div>
              <div style={{ fontSize: "0.74rem", color: "var(--text-faint)" }}>
                <span className="online-dot" /> Online
              </div>
            </div>
          </div>
          <button className="logout-btn" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
