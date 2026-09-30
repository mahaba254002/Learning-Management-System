import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ApiError } from "../../api/client";
import { changePasswordSchema } from "./changePasswordSchema";
import PasswordInput from "../../components/common/PasswordInput";
import { useAuth } from "../../context/useAuth";
import { getRoleLoginPath } from "../../routes/roleRoutes";
import AuthSplitLayout from "../../components/layout/AuthSplitLayout";

import "./LoginPage.css";

export default function ChangePasswordPage() {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState(null);
  const { user, changePassword } = useAuth();
  const portal = user.role === "TEACHER" ? "Teacher" : user.role === "STUDENT" ? "Student" : "Admin";

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(changePasswordSchema) });

  async function onSubmit(values) {
    setServerError(null);
    try {
      await changePassword(values);
      navigate(getRoleLoginPath(user.role), { replace: true, state: { passwordChanged: true } });
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError(err.message);
      } else {
        setServerError("Something went wrong. Please try again.");
      }
    }
  }

  return (
    <AuthSplitLayout heading="Set a new password" subheading="Keep your Rollcall account secure.">
      <form className="auth-form auth-form--embedded" onSubmit={handleSubmit(onSubmit)} noValidate>
        <h2>{portal} password change</h2>
        <p style={{ color: "var(--color-ink-soft)", marginBottom: "var(--space-6)", fontSize: "var(--text-sm)" }}>
          {user.must_change_password ? "Set a new password before continuing. " : "Choose a new password for your account. "}
          You will sign in again after saving.
        </p>

        <div className="form-field">
          <label htmlFor="current_password">{user.must_change_password ? "Current (temporary) password" : "Current password"}</label>
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
    </AuthSplitLayout>
  );
}
