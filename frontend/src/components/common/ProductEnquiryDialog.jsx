import { useEffect, useRef, useState } from "react";
import { apiRequest } from "../../api/client";
import { EDUCATION_SECTORS } from "./educationSectors";

export default function ProductEnquiryDialog({ sector, onClose }) {
  const dialogRef = useRef(null);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement;
    dialog.showModal();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.getClientRects().length) previousFocus.focus();
      else document.querySelector(".skynet-menu-toggle")?.focus();
    };
  }, []);

  async function submit(event) {
    event.preventDefault();
    if (submitting) return;
    setError("");
    setSubmitting(true);
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await apiRequest("/api/contact/enquiries", { method: "POST", body: values });
      setSent(true);
    } catch (err) {
      setError(err.status === 429
        ? "Too many enquiries. Please wait a few minutes before trying again."
        : "Your enquiry could not be sent. Please try again, or email mahaba955@gmail.com.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <dialog ref={dialogRef} className="skynet-enquiry" aria-labelledby="enquiry-title" onCancel={onClose}>
      <div className="skynet-enquiry-header">
        <h2 id="enquiry-title">Ask about Skynet</h2>
        <button type="button" onClick={onClose} aria-label="Close enquiry form">×</button>
      </div>
      {sent ? <div className="skynet-enquiry-success" role="status">
        <h3>Thank you for your enquiry.</h3>
        <p>Your message has been sent. We’ll reply to the email address you provided.</p>
        <button type="button" className="skynet-submit" onClick={onClose}>Done</button>
      </div> : <>
        <p className="skynet-enquiry-intro">Tell us what your institution needs and what you’d like to know about the product.</p>
        <form onSubmit={submit}>
          <div className="skynet-enquiry-grid">
            <label>Your name<input name="name" autoComplete="name" required maxLength={120} /></label>
            <label>Email address<input name="email" type="email" autoComplete="email" required maxLength={255} /></label>
          </div>
          <label>Institution name<input name="institution" autoComplete="organization" required maxLength={160} /></label>
          <label>Education category<select name="sector" defaultValue={sector} required>
            {EDUCATION_SECTORS.map(value => <option key={value}>{value}</option>)}
          </select></label>
          <label>How can we help?<textarea name="message" rows={4} required minLength={10} maxLength={4000} placeholder="Ask about the product or tell us what you’re looking for." /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit" className="skynet-submit" disabled={submitting}>{submitting ? "Sending…" : "Send enquiry"}</button>
          <p className="skynet-enquiry-contact">Or email <a href="mailto:mahaba955@gmail.com">mahaba955@gmail.com</a></p>
        </form>
      </>}
    </dialog>
  );
}
