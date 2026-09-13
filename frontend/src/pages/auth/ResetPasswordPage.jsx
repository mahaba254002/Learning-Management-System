import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiRequest, ApiError } from "../../api/client";
import { resetPasswordSchema } from "./resetPasswordSchema";
import "./LoginPage.css";

import PasswordInput from "../../components/common/Passwordinput";

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const verificationId = searchParams.get("verification_id");
  const navigate = useNavigate();
  const [serverError, setServerError] = useState(null);
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(resetPasswordSchema) });

  async function onSubmit(values) {
    setServerError(null);
    try {
      await apiRequest("/api/auth/reset-password", {
        method: "POST",
        body: { verification_id: verificationId, ...values },
      });
      setSuccess(true);
      setTimeout(() => navigate("/login", { replace: true }), 2000);
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError(err.message);
      } else {
        setServerError("Something went wrong. Please try again.");
      }
    }
  }

  if (!verificationId) {
    return (
      <div className="auth-page">
        <div className="auth-form">
          <h1>Invalid link</h1>
          <p style={{ color: "var(--color-ink-soft)", marginBottom: "1.5rem" }}>
            This password reset link is missing required information. Please request a new one.
          </p>
          <Link to="/forgot-password" className="forgot-link">Request a new reset link</Link>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="auth-page">
        <div className="auth-form">
          <h1>Password reset</h1>
          <p style={{ color: "var(--color-ink-soft)" }}>
            Your password has been changed. Redirecting you to sign in...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit(onSubmit)} noValidate>
        <h1>Reset your password</h1>
        <p style={{ color: "var(--color-ink-soft)", marginBottom: "1.5rem", fontSize: "var(--text-sm)" }}>
          Enter the 6-digit code we sent you and choose a new password.
        </p>

        <div className="form-field">
          <label htmlFor="code">6-digit code</label>
          <input id="code" type="text" inputMode="numeric" maxLength={6} {...register("code")} />
          {errors.code && <p className="field-error">{errors.code.message}</p>}
        </div>

        <div className="form-field">
          <label htmlFor="new_password">New password</label>
          <PasswordInput id="new_password" autoComplete="new-password" {...register("new_password")} />
          {errors.new_password && <p className="field-error">{errors.new_password.message}</p>}
        </div>

        <div className="form-field">
          <label htmlFor="confirm_password">Confirm new password</label>
          <PasswordInput id="confirm_password" autoComplete="new-password" {...register("confirm_password")} />
          {errors.confirm_password && <p className="field-error">{errors.confirm_password.message}</p>}
        </div>

        {serverError && <p className="form-error" role="alert">{serverError}</p>}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Resetting..." : "Reset password"}
        </button>
      </form>
    </div>
  );
}