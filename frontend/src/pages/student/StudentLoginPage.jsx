import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "../../context/useAuth";
import { ApiError } from "../../api/client";
import { loginSchema } from "../auth/loginSchema";
import PasswordInput from "../../components/common/PasswordInput";
import AuthSplitLayout from "../../components/layout/AuthSplitLayout";
import "../auth/LoginPage.css";

export default function StudentLoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(loginSchema),
  });

  async function onSubmit(values) {
    setServerError(null);
    try {
      const result = await login(values.username, values.password, "/api/auth/student/login");

      if (result.must_change_password) {
        navigate("/student/change-password", { replace: true });
        return;
      }

      navigate("/student/dashboard", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setServerError("Too many attempts. Please wait a few minutes and try again.");
        } else if (err.status === 401) {
          setServerError("Incorrect username or password.");
        } else if (err.status === 403) {
          setServerError(err.message);
        } else {
          setServerError("Something went wrong. Please try again.");
        }
      } else {
        setServerError("Could not reach the server. Please check your connection.");
      }
    }
  }

  return (
    <AuthSplitLayout
      heading="Welcome back."
      subheading="Sign in to see your courses, attendance, and results."
    >
      <form className="auth-form auth-form--embedded" onSubmit={handleSubmit(onSubmit)} noValidate>
        <h2>Student sign in</h2>

        <div className="form-field">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            type="text"
            autoComplete="username"
            {...register("username")}
          />
          {errors.username && <p className="field-error">{errors.username.message}</p>}
        </div>

        <div className="form-field">
          <label htmlFor="password">Password</label>
          <PasswordInput
            id="password"
            autoComplete="current-password"
            {...register("password")}
          />
          {errors.password && <p className="field-error">{errors.password.message}</p>}
        </div>

        {serverError && <p className="form-error" role="alert">{serverError}</p>}

        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Signing in..." : "Sign in"}
        </button>

        <Link to="/student/forgot-password" className="forgot-link">Forgot your password?</Link>
      </form>
    </AuthSplitLayout>
  );
}