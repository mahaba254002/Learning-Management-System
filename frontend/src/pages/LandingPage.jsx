import { useState } from "react";
import { Link } from "react-router-dom";
import "./LandingPage.css";

const INSTITUTION_TYPES = [
  "University",
  "College",
  "High School",
  "Primary School",
  "Training Institution",
];

const NAV_LINKS = [
  { to: "/pricing", label: "Pricing" },
  { to: "/how-it-works", label: "How it works" },
  { to: "/contact", label: "Contact us" },
];

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div>
      <header className="landing-header">
        <Link to="/" className="landing-header__brand">
          <span className="landing-header__logo" aria-hidden="true" />
          Rollcall
        </Link>

        <nav className="landing-header__nav landing-header__nav--desktop">
          {NAV_LINKS.map((link) => (
            <Link key={link.to} to={link.to} className="landing-header__link">
              {link.label}
            </Link>
          ))}
          <Link to="/login" className="landing-header__signin">Sign in</Link>
        </nav>

        <button
          className="landing-header__menu-btn"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className="landing-header__menu-icon" />
        </button>
      </header>

      {menuOpen && (
        <nav className="landing-header__nav--mobile">
          {NAV_LINKS.map((link) => (
            <Link key={link.to} to={link.to} className="landing-header__link--mobile">
              {link.label}
            </Link>
          ))}
          <Link to="/login" className="landing-header__signin--mobile">Sign in</Link>
        </nav>
      )}

      <main className="hero">
        <h1 className="hero__headline">One record system. Every kind of institution.</h1>
        <p className="hero__subhead">
          Rollcall brings admissions, attendance, coursework, and results into one
          place — built to fit a university, a training center, or a primary school
          without forcing any of them into the wrong shape.
        </p>

        <div className="hero__actions">
          <Link to="/request-access" className="btn btn--primary">Request access</Link>
        </div>

        <div className="hero__showcase">
          <div className="institution-showcase">
            <p className="institution-showcase__label">Built for</p>
            <ul className="institution-list">
              {INSTITUTION_TYPES.map((type) => (
                <li key={type} className="institution-list__item">
                  {type}
                  <span className="institution-list__marker">—</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="video-placeholder">
            <button className="video-placeholder__play" aria-label="Play product demo video">
              ▶
            </button>
            <p className="video-placeholder__caption">See Rollcall in two minutes</p>
          </div>
        </div>
      </main>
    </div>
  );
}