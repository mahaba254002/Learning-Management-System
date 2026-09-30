import { Link } from "react-router-dom";
import { getRoleLoginPath } from "../routes/roleRoutes";
import "./LandingPage.css";
import "./PortalPickerPage.css";

const PORTALS = [
  { role: "INSTITUTION_ADMIN", title: "Admin", description: "For institution and platform administrators." },
  { role: "TEACHER", title: "Teacher", description: "For teachers and teaching staff." },
  { role: "STUDENT", title: "Student", description: "For students and learners." },
];

export default function PortalPickerPage() {
  return (
    <div>
      <header className="landing-header">
        <Link to="/" className="landing-header__brand" aria-label="Rollcall home">
          <span className="landing-header__logo" aria-hidden="true" />
          Rollcall
        </Link>
        <Link to="/" className="landing-header__link">Back to home</Link>
      </header>
      <main className="hero portal-picker">
        <h1 className="hero__headline">Sign in to Rollcall</h1>
        <p className="hero__subhead">Choose the portal for your role at your institution.</p>
        <nav className="portal-picker__cards" aria-label="Sign-in portals">
          {PORTALS.map(({ role, title, description }) => (
            <Link key={role} to={getRoleLoginPath(role)} className="feature-card portal-picker__card">
              <span className="feature-card__marker" aria-hidden="true" />
              <h2 className="feature-card__title">{title}</h2>
              <p className="feature-card__description">{description}</p>
              <span className="portal-picker__action">{title} sign in <span aria-hidden="true">→</span></span>
            </Link>
          ))}
        </nav>
        <p className="portal-picker__help">Not sure which portal to use? Ask your institution’s administrator.</p>
      </main>
    </div>
  );
}
