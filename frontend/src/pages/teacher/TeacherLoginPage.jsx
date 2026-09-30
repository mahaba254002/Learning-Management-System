import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "../../context/useAuth";
import { ApiError } from "../../api/client";
import { loginSchema } from "../auth/loginSchema";
import PasswordInput from "../../components/common/PasswordInput";
import AuthSplitLayout from "../../components/layout/AuthSplitLayout";
import "../auth/LoginPage.css";

export default function TeacherLoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { state } = useLocation();
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
      const result = await login(values.username, values.password, "/api/auth/teacher/login");

      if (result.must_change_password) {
        navigate("/teacher/change-password", { replace: true });
        return;
      }

      navigate("/teacher/dashboard", { replace: true });
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
      heading="Welcome back, educators."
      subheading="Sign in to manage your classes, attendance, and grading."
    >
      <form className="auth-form auth-form--embedded" onSubmit={handleSubmit(onSubmit)} noValidate>
        <h2>Teacher sign in</h2>
        {state?.passwordChanged && <p className="form-field" role="status">Your password has been changed. Sign in with your new password.</p>}

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

        <Link to="/teacher/forgot-password" className="forgot-link">Forgot your password?</Link>
      </form>
    </AuthSplitLayout>
  );
}
