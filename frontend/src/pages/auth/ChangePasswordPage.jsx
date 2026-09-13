import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiRequest, ApiError } from "../../api/client";
import { changePasswordSchema } from "./changePasswordSchema";
import PasswordInput from "../../components/common/PasswordInput"; import { useAuth } from "../../context/useAuth";
import { getRoleHomePath } from "../../routes/roleRoutes";

import "./LoginPage.css";

export default function ChangePasswordPage() {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState(null);
  const { user } = useAuth();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(changePasswordSchema) });

  async function onSubmit(values) {
    setServerError(null);
    try {
      await apiRequest("/api/auth/change-password", { method: "POST", body: values });
      navigate(getRoleHomePath(user.role), { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError(err.message);
      } else {
        setServerError("Something went wrong. Please try again.");
      }
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit(onSubmit)} noValidate>
        <h1>Set a new password</h1>
        <p style={{ color: "var(--color-ink-soft)", marginBottom: "1.5rem", fontSize: "var(--text-sm)" }}>
          For your security, you must set a new password before continuing.
        </p>

        <div className="form-field">
          <label htmlFor="current_password">Current (temporary) password</label>
          <PasswordInput id="current_password" autoComplete="current-password" {...register("current_password")} />
          {errors.current_password && <p className="field-error">{errors.current_password.message}</p>}
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
          {isSubmitting ? "Updating..." : "Update password"}
        </button>
      </form>
    </div>
  );
}