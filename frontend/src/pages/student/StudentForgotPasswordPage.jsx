import { useState } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiRequest, ApiError } from "../../api/client";
import { forgotPasswordSchema } from "../auth/forgotPasswordSchema";
import AuthSplitLayout from "../../components/layout/AuthSplitLayout";
import "../auth/LoginPage.css";

export default function StudentForgotPasswordPage() {
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
      // Student door — matches STUDENT_ROLES on the backend. A staff email
      // submitted here is silently treated as "not found", same generic
      // response either way, so this never reveals which portal an email
      // belongs to.
      await apiRequest("/api/auth/student/forgot-password", { method: "POST", body: values });
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
      <AuthSplitLayout
        heading="Check your email."
        subheading="We've sent password reset instructions if an account exists for that address."
      >
        <div className="auth-form auth-form--embedded">
          <h2>Check your email</h2>
          <p style={{ color: "var(--color-ink-soft)", marginBottom: "1.5rem" }}>
            If an account with that email exists, we've sent password reset instructions.
          </p>
          <Link to="/student/login" className="forgot-link">Back to sign in</Link>
        </div>
      </AuthSplitLayout>
    );
  }

  return (
    <AuthSplitLayout
      heading="Forgot your password?"
      subheading="Enter your email and we'll send you a code to reset it."
    >
      <form className="auth-form auth-form--embedded" onSubmit={handleSubmit(onSubmit)} noValidate>
        <h2>Reset your password</h2>

        <div className="form-field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" {...register("email")} />
          {errors.email && <p className="field-error">{errors.email.message}</p>}
        </div>

        {serverError && <p className="form-error" role="alert">{serverError}</p>}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Sending..." : "Send reset code"}
        </button>

        <Link to="/student/login" className="forgot-link">Back to sign in</Link>
      </form>
    </AuthSplitLayout>
  );
}