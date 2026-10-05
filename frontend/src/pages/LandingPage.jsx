import { useState } from "react";
import { Link } from "react-router-dom";
import "./LandingPage.css";

const roles = [
  { name: "Students", path: "/student/login", text: "Your subjects, in one place.", details: "Read course materials, submit assignments, and follow your attendance, marks and teacher feedback." },
  { name: "Teachers", path: "/teacher/login", text: "More time for teaching.", details: "Take attendance, share resources, set coursework and record scores. Class supervisors also manage their student roster." },
  { name: "Administrators", path: "/login", text: "A clear view of your institution.", details: "Organise classes and subjects, onboard teachers, manage accounts and review administrative activity." },
];

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="landing-page">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="landing-header">
        <Link to="/" className="landing-header__brand"><span className="landing-header__logo" aria-hidden="true">r.</span>Rollcall</Link>
        <button className="landing-header__menu-btn" aria-expanded={menuOpen} aria-controls="landing-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? "Close" : "Menu"}</button>
        <nav id="landing-navigation" aria-label="Main navigation" className={`landing-nav ${menuOpen ? "is-open" : ""}`} onClick={() => setMenuOpen(false)}>
          <a href="#learning">Learning</a><a href="#workspaces">Who it’s for</a><a href="#getting-started">Getting started</a>
          <Link className="landing-header__signin" to="/sign-in">Sign in <span aria-hidden="true">↗</span></Link>
        </nav>
      </header>
      <main id="main-content">
        <section className="landing-intro landing-container">
          <div>
            <p className="landing-eyebrow">THE EVERYDAY LEARNING WORKSPACE</p>
            <h1>A place for every lesson.<br /><em>A record of every step.</em></h1>
            <p className="landing-lead">Connect what happens in class with what comes next. Attendance, course materials, assignments and results — together in Rollcall.</p>
            <div className="landing-actions"><Link className="btn btn--primary" to="/sign-in">Open your workspace <span aria-hidden="true">↗</span></Link><a href="#learning">Explore the platform <span aria-hidden="true">↓</span></a></div>
            <p className="landing-caption">For students, teachers and the people supporting them.</p>
          </div>
          <aside className="lesson-preview" aria-label="Illustrative learning workspace">
            <div className="lesson-preview__top"><span>ROLLCALL / LEARNING</span><span>Illustrative view</span></div>
            <p className="landing-eyebrow">FORM 1 · MATHEMATICS</p><h2>Small steps.<br />Steady progress.</h2>
            <div className="lesson-preview__row"><span className="lesson-number">01</span><div><strong>Before the lesson</strong><p>Read the introduction to algebra</p></div><span aria-hidden="true">↗</span></div>
            <div className="lesson-preview__row"><span className="lesson-number">02</span><div><strong>Put it into practice</strong><p>Complete your coursework</p></div><span aria-hidden="true">↗</span></div>
            <div className="lesson-preview__row"><span className="lesson-number">03</span><div><strong>See how you’re doing</strong><p>Review marks and feedback</p></div><span aria-hidden="true">↗</span></div>
            <div className="lesson-preview__bottom">Learn. Practise. Reflect.</div>
          </aside>
        </section>
        <section id="learning" className="learning-section">
          <div className="landing-container">
            <div className="section-heading"><p className="landing-eyebrow">FROM THE FIRST REGISTER TO THE FINAL MARK</p><h2>The school day,<br />with the details connected.</h2></div>
            <div className="learning-columns">
              <article><span className="section-number">01 / ATTENDANCE</span><h3>Every lesson counts.</h3><p>Teachers record class or subject attendance. Students can follow their own attendance for each subject.</p></article>
              <article><span className="section-number">02 / COURSEWORK</span><h3>Keep the learning moving.</h3><p>Publish materials and assignments with clear deadlines. Students save drafts and submit written work or document links.</p></article>
              <article><span className="section-number">03 / FEEDBACK</span><h3>Make progress visible.</h3><p>Record assessment scores and share feedback, so learners know where they stand and what to work on next.</p></article>
            </div>
          </div>
        </section>
        <section id="workspaces" className="landing-container workspace-section">
          <div className="section-heading"><p className="landing-eyebrow">ONE PLATFORM, DIFFERENT RESPONSIBILITIES</p><h2>Your role. Your workspace.</h2><p>Start with the tools you need for your day.</p></div>
          {roles.map(role => <article className="workspace-row" key={role.name}><p className="landing-eyebrow">{role.name}</p><div><h3>{role.text}</h3><p>{role.details}</p></div><Link to={role.path}>{role.name} sign in <span aria-hidden="true">↗</span></Link></article>)}
          <p className="workspace-note">Platform administrators use the administrator portal to manage institutions, account status and platform usage.</p>
        </section>
        <section id="getting-started" className="landing-container getting-started">
          <div><p className="landing-eyebrow">GETTING STARTED</p><h2>A simple start.<br />A shared routine.</h2><p>Rollcall uses institution-managed accounts. Your administrator or class supervisor will help you get access.</p><Link className="btn btn--primary" to="/sign-in">Choose your portal <span aria-hidden="true">↗</span></Link></div>
          <div className="landing-faq">
            <details open><summary>How do I get an account?</summary><p>Ask your institution’s administrator. Teachers join through an invitation, and student accounts are created by an administrator or authorised class supervisor. Public self-registration is not available.</p></details>
            <details><summary>Which sign-in page should I use?</summary><p>Choose Student or Teacher for your learning workspace. Both institution and platform administrators use the Admin portal.</p></details>
            <details><summary>Can students change their records?</summary><p>Students can submit their work and view their own attendance, marks and profile. Profile corrections and enrollment changes are handled by authorised staff.</p></details>
            <details><summary>What if I cannot sign in?</summary><p>Use the password recovery link in your portal. If your account is suspended or you do not have access to your registered email, contact your institution’s administrator.</p></details>
          </div>
        </section>
      </main>
      <footer className="landing-footer landing-container"><Link to="/" className="landing-header__brand">Rollcall</Link><p>A clearer connection between teaching and learning.</p><a href="https://github.com/mahaba254002/Learning-Management-System">Project & documentation <span aria-hidden="true">↗</span></a></footer>
    </div>
  );
}
