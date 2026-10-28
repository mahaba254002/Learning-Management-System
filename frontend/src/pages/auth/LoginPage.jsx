import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "../../context/useAuth";
import { ApiError } from "../../api/client";
import { loginSchema } from "./loginSchema";
import { studentLoginSchema } from "../student/studentLoginSchema";
import { getRoleHomePath, getRoleChangePasswordPath } from "../../routes/roleRoutes";
import PasswordInput from "../../components/common/PasswordInput";
import ProductEnquiryDialog from "../../components/common/ProductEnquiryDialog";
import { EDUCATION_SECTORS } from "../../components/common/educationSectors";
import logo from "../../assets/skynet-logo.png";
import "./LoginPage.css";
import "./SkynetLogin.css";

export default function LoginPage({ student = false }) {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { state, pathname } = useLocation();
  const [portal, setPortal] = useState(pathname === "/login" ? "admin" : "teacher");
  const [serverError, setServerError] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [enquirySector, setEnquirySector] = useState(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(student ? studentLoginSchema : loginSchema), defaultValues: { remember_me: false },
  });
  const audience = student ? "Student" : portal === "teacher" ? "Teacher" : "Admin";
  const prefix = student ? "/student" : portal === "teacher" ? "/teacher" : "";
  async function onSubmit(values) {
    setServerError(null);
    try {
      const result = await login(values.email, values.password, `/api/auth${prefix}/login`, values.remember_me);
      navigate(result.must_change_password ? getRoleChangePasswordPath(result.user.role) : getRoleHomePath(result.user.role), { replace: true });
    } catch (err) {
      setServerError(err instanceof ApiError
        ? err.status === 429 ? "Too many attempts. Please wait a few minutes and try again."
          : err.status === 401 ? "Incorrect sign-in details."
          : err.status === 403 ? err.message
          : err.status === 503 ? "Sign in is temporarily unavailable. Please try again shortly."
          : "Something went wrong. Please try again."
        : "Could not reach the server. Please check your connection.");
    }
  }
  return (
    <div className="skynet-page">
      <header className="skynet-header">
        <Link to="/" aria-label="Skynet home"><img src={logo} alt="Skynet - Innovative Online Solutions" /></Link>
        <button
          className="skynet-menu-toggle"
          type="button"
          aria-label={menuOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={menuOpen}
          aria-controls="education-navigation"
          onClick={() => setMenuOpen(open => !open)}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            {menuOpen ? <path d="m6 6 12 12M6 18 18 6" /> : <path d="M3 6h18M3 12h18M3 18h18" />}
          </svg>
        </button>
        <nav id="education-navigation" className={menuOpen ? "is-open" : ""} aria-label="Education sectors" onKeyDown={event => {
          if (event.key === "Escape") {
            setMenuOpen(false);
            document.querySelector(".skynet-menu-toggle")?.focus();
          }
        }}>
          {EDUCATION_SECTORS.map(sector => <button type="button" key={sector} aria-haspopup="dialog" onClick={() => {
            setMenuOpen(false);
            setEnquirySector(sector);
          }}>{sector}</button>)}
        </nav>
      </header>
      {enquirySector && <ProductEnquiryDialog sector={enquirySector} onClose={() => setEnquirySector(null)} />}
      <main className="skynet-main">
        <aside className="skynet-offer" aria-label="Your digital workspace">
          <div className="skynet-offer-copy"><h2>What we offer:</h2><ol>
            <li>Secure Institutional Control: Manage accounts and academic records in one workspace.</li>
            <li>Connected Learning: Access coursework, attendance, and results.</li>
            <li>Tools for Every Day: Keep classes, teaching materials, and assignments organised.</li>
          </ol></div>
          <div className="skynet-tagline"><p>Your Digital Workspace</p><h2>Smart Tools for<br /><span className="skynet-arrow" aria-hidden="true">↗</span> Smarter Work</h2></div>
        </aside>
        <section className="skynet-login" aria-labelledby="login-title">
          <h1 id="login-title">Welcome Back!</h1>
          <p className="skynet-intro">{student ? "Log in to access your subjects, complete assignments, and keep track of your progress." : "Log in to access your dashboard, manage your students, and continue securely with full control."}</p>
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            {!student &&
              <fieldset className="skynet-portals" disabled={isSubmitting}><legend className="skynet-sr-only">Choose your staff role</legend>
                {["teacher", "admin"].map(role => <label key={role} className={portal === role ? "selected" : ""}>
                  <input type="radio" name="portal" value={role} checked={portal === role} onChange={() => { setPortal(role); setServerError(null); }} />
                  {role === "teacher" ? "Teacher" : "Admin"}
                </label>)}
              </fieldset>}
            {!student && portal === "admin" && <p className="skynet-role-note">For platform and institution administrators.</p>}
            {state?.passwordChanged && <p className="skynet-notice" role="status">Your password has been changed. Sign in with your new password.</p>}
            <div className="skynet-field"><label htmlFor="identity">{student ? "Email or Student ID" : "Email Address"}</label>
              <input id="identity" type={student ? "text" : "email"} placeholder={student ? "Enter the email or ID your institution assigned" : "Enter your email"} autoComplete="username" autoCapitalize="none" spellCheck={false} aria-invalid={!!errors.email} aria-describedby={errors.email ? "identity-error" : undefined} {...register("email")} />
              {errors.email && <p id="identity-error" className="field-error" role="alert">{errors.email.message}</p>}
            </div>
            <div className="skynet-field"><label htmlFor="password">Password</label>
              <PasswordInput id="password" placeholder="Enter your password" autoComplete="current-password" aria-invalid={!!errors.password} aria-describedby={errors.password ? "password-error" : undefined} {...register("password")} />
              {errors.password && <p id="password-error" className="field-error" role="alert">{errors.password.message}</p>}
            </div>
            <div className="skynet-options"><label><input type="checkbox" {...register("remember_me")} /> Remember me</label><Link to={`${prefix}/forgot-password`}>Forgot Password?</Link></div>
            {serverError && <p className="form-error" role="alert">{serverError}</p>}
            <button className="skynet-submit" type="submit" disabled={isSubmitting}>{isSubmitting ? "Signing in..." : `Login as a${audience === "Admin" ? "n" : ""} ${audience}`}</button>
            <p className="skynet-switch">{student ? "Teacher or administrator?" : "Are you a student or pupil?"} <Link to={student ? "/" : "/student/login"}>{student ? "Staff login" : "Student login"}</Link></p>
          </form>
        </section>
      </main>
    </div>
  );
}
