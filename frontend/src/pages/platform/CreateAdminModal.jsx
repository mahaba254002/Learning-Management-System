import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest, ApiError } from "../../api/client";
import { createAdminSchema } from "./createAdminSchema";
import Modal from "../../components/common/Modal";

export default function CreateAdminModal({ institution, onClose }) {
  const [result, setResult] = useState(null);
  const [serverError, setServerError] = useState(null);
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(createAdminSchema) });

  const mutation = useMutation({
    mutationFn: (values) =>
      apiRequest(`/api/platform/institutions/${institution.id}/admins`, {
        method: "POST",
        body: values,
      }),
    onSuccess: (data) => {
      setResult(data);
      // Invalidate the institutions list so any future admin-count display
      // stays in sync — harmless no-op right now, useful once we show
      // per-institution admin counts later.
      queryClient.invalidateQueries({ queryKey: ["platform-institutions"] });
    },
    onError: (err) => {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    },
  });

  function onSubmit(values) {
    setServerError(null);
    mutation.mutate(values);
  }

  if (result) {
    return (
      <Modal isOpen title="Admin account created" onClose={onClose}>
        <div className="credential-result">
          <p className="credential-warning">
            Save these credentials now — the temporary password will not be shown again.
          </p>
          <div className="credential-row">
            <span className="credential-label">Username</span>
            <code className="credential-value">{result.username}</code>
          </div>
          <div className="credential-row">
            <span className="credential-label">Temporary password</span>
            <code className="credential-value">{result.temporary_password}</code>
          </div>
          <button className="btn btn--primary" style={{ marginTop: "1.5rem", width: "100%" }} onClick={onClose}>
            Done
          </button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal isOpen title={`Create admin for ${institution.name}`} onClose={onClose}>
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="form-field">
          <label htmlFor="first_name">First name</label>
          <input id="first_name" type="text" {...register("first_name")} />
          {errors.first_name && <p className="field-error">{errors.first_name.message}</p>}
        </div>

        <div className="form-field">
          <label htmlFor="last_name">Last name</label>
          <input id="last_name" type="text" {...register("last_name")} />
          {errors.last_name && <p className="field-error">{errors.last_name.message}</p>}
        </div>

        <div className="form-field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" {...register("email")} />
          {errors.email && <p className="field-error">{errors.email.message}</p>}
        </div>

        {serverError && <p className="form-error" role="alert">{serverError}</p>}

        <button type="submit" className="btn btn--primary" disabled={isSubmitting} style={{ width: "100%" }}>
          {isSubmitting ? "Creating..." : "Create admin account"}
        </button>
      </form>
    </Modal>
  );
}