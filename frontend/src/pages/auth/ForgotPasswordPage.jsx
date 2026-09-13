import { useState } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiRequest, ApiError } from "../../api/client";
import { forgotPasswordSchema } from "./forgotPasswordSchema";
import "./LoginPage.css";

export default function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false);
  const [serverError, setServerError] = useState(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(forgotPasswordSchema) });

  async function onSubmit(values) {
    setServerError(null);
    try {
      await apiRequest("/api/auth/forgot-password", { method: "POST", body: values });
      // Always show the same success state, regardless of whether the
      // email actually exists — matches the backend's enumeration-safe
      // design. We never learn from this UI whether the account exists.
      setSubmitted(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setServerError("Too many attempts. Please wait a few minutes and try again.");
      } else {
        setServerError("Something went wrong. Please try again.");
      }
    }
  }

  if (submitted) {
    return (
      <div className="auth-page">
        <div className="auth-form">
          <h1>Check your email</h1>
          <p style={{ color: "var(--color-ink-soft)", marginBottom: "1.5rem" }}>
            If an account with that email exists, we've sent password reset instructions.
          </p>
          <Link to="/login" className="forgot-link">Back to sign in</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit(onSubmit)} noValidate>
        <h1>Forgot your password?</h1>
        <p style={{ color: "var(--color-ink-soft)", marginBottom: "1.5rem", fontSize: "var(--text-sm)" }}>
          Enter your email and we'll send you a code to reset your password.
        </p>

        <div className="form-field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" {...register("email")} />
          {errors.email && <p className="field-error">{errors.email.message}</p>}
        </div>

        {serverError && <p className="form-error" role="alert">{serverError}</p>}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Sending..." : "Send reset code"}
        </button>

        <Link to="/login" className="forgot-link">Back to sign in</Link>
      </form>
    </div>
  );
}