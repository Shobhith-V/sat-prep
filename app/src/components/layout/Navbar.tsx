import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './Navbar.css';

export function Navbar() {
  const { profile, signOut } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await signOut();
    navigate('/login', { replace: true });
  }

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/dashboard" className="navbar-brand">
          SAT<span>Prep</span>
        </Link>
        <nav className="navbar-links">
          <Link to="/dashboard">Dashboard</Link>
          <Link to="/practice/setup">Practice</Link>
          <Link to="/flagged">Flagged</Link>
          {profile && <span className="navbar-user">{profile.name}</span>}
          <button className="btn btn-outline navbar-signout" onClick={handleSignOut}>
            Sign out
          </button>
        </nav>
      </div>
    </header>
  );
}
