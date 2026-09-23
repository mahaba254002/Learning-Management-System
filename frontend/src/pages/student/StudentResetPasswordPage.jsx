import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiRequest, ApiError } from "../../api/client";
import { resetPasswordSchema } from "../auth/resetPasswordSchema";
import PasswordInput from "../../components/common/PasswordInput";
import AuthSplitLayout from "../../components/layout/AuthSplitLayout";
import "../auth/LoginPage.css";

export default function StudentResetPasswordPage() {
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
      // Student door — a code minted for a staff account is rejected here
      // even with the correct 6-digit code, since the backend checks the
      // code's stored role against this endpoint's allowed_roles.
      await apiRequest("/api/auth/student/reset-password", {
        method: "POST",
        body: { verification_id: verificationId, ...values },
      });
      setSuccess(true);
      setTimeout(() => navigate("/student/login", { replace: true }), 2000);
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
      <AuthSplitLayout heading="Invalid link" subheading="This reset link is missing required information.">
        <div className="auth-form auth-form--embedded">
          <h2>Invalid link</h2>
          <p style={{ color: "var(--color-ink-soft)", marginBottom: "1.5rem" }}>
            This password reset link is missing required information. Please request a new one.
          </p>
          <Link to="/student/forgot-password" className="forgot-link">Request a new reset link</Link>
        </div>
      </AuthSplitLayout>
    );
  }

  if (success) {
    return (
      <AuthSplitLayout heading="Password reset" subheading="Redirecting you to sign in...">
        <div className="auth-form auth-form--embedded">
          <h2>Password reset</h2>
          <p style={{ color: "var(--color-ink-soft)" }}>
            Your password has been changed. Redirecting you to sign in...
          </p>
        </div>
      </AuthSplitLayout>
    );
  }

  return (
    <AuthSplitLayout
      heading="Reset your password"
      subheading="Enter the 6-digit code we sent you and choose a new password."
    >
      <form className="auth-form auth-form--embedded" onSubmit={handleSubmit(onSubmit)} noValidate>
        <h2>Reset your password</h2>

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
    </AuthSplitLayout>
  );
}