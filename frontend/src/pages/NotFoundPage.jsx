import { Link } from "react-router-dom";
import "./LandingPage.css";

export default function NotFoundPage() {
  return <main className="hero"><p className="landing-eyebrow">PAGE NOT FOUND</p><h1 className="hero__headline">Let’s get you back on track.</h1><p className="hero__subhead">This page may have moved, or the address may be incorrect.</p><div className="landing-actions"><Link className="btn btn--primary" to="/">Back to home</Link><Link to="/sign-in">Choose your portal</Link></div></main>;
}
