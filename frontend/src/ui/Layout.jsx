import { Link, useLocation } from "react-router-dom";
import { useAppState } from "../state/AppState";

export default function Layout({ children }) {
  const { playerName, house } = useAppState();
  const loc = useLocation();

  return (
    <div className="container">
      <header className="header">
        <div>
          <h2 className="title">ASL Spellcaster</h2>
          <div className="small">
            Welcome, <b>{playerName}</b> • House: <b>{house.name}</b>
          </div>
        </div>

        <nav className="nav">
          <NavLink to="/" active={loc.pathname === "/"}>Home</NavLink>
          <NavLink to="/learn" active={loc.pathname === "/learn"}>Learn</NavLink>
          <NavLink to="/leaderboard" active={loc.pathname === "/leaderboard"}>House Cup</NavLink>
        </nav>
      </header>

      {children}

      <footer className="footer small">
        {/* Demo mode UI now — backend CV can plug in later. */}
      </footer>
    </div>
  );
}

function NavLink({ to, active, children }) {
  return (
    <Link className={`navlink ${active ? "active" : ""}`} to={to}>
      {children}
    </Link>
  );
}