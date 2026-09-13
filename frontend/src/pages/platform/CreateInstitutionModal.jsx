import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest, ApiError } from "../../api/client";
import { institutionDetailsSchema, codeSchema, INSTITUTION_TYPES } from "./createInstitutionSchema";
import Modal from "../../components/common/Modal";

const STEPS = {
  DETAILS: "details",
  VERIFY: "verify",
  SUCCESS: "success",
};

export default function CreateInstitutionModal({ onClose }) {
  const [step, setStep] = useState(STEPS.DETAILS);
  const [verificationId, setVerificationId] = useState(null);
  const [serverError, setServerError] = useState(null);
  const [createdInstitution, setCreatedInstitution] = useState(null);
  const queryClient = useQueryClient();

  const detailsForm = useForm({ resolver: zodResolver(institutionDetailsSchema) });
  const codeForm = useForm({ resolver: zodResolver(codeSchema) });

  const requestMutation = useMutation({
    mutationFn: (values) => {
      // Strip empty-string optional fields so we send undefined instead,
      // matching what the backend's Optional fields expect more cleanly.
      const cleaned = Object.fromEntries(
        Object.entries(values).filter(([, v]) => v !== "")
      );
      return apiRequest("/api/platform/institutions/request-create", {
        method: "POST",
        body: cleaned,
      });
    },
    onSuccess: (data) => {
      setVerificationId(data.verification_id);
      setServerError(null);
      setStep(STEPS.VERIFY);
    },
    onError: (err) => {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (values) =>
      apiRequest("/api/platform/institutions/confirm-create", {
        method: "POST",
        body: { verification_id: verificationId, code: values.code },
      }),
    onSuccess: (data) => {
      setCreatedInstitution(data);
      setServerError(null);
      setStep(STEPS.SUCCESS);
      queryClient.invalidateQueries({ queryKey: ["platform-institutions"] });
      queryClient.invalidateQueries({ queryKey: ["platform-stats"] });
    },
    onError: (err) => {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    },
  });

  if (step === STEPS.SUCCESS) {
    return (
      <Modal isOpen title="Institution created" onClose={onClose}>
        <p style={{ marginBottom: "1.5rem" }}>
          <strong>{createdInstitution.name}</strong> has been created and is now active.
          You can create its first administrator from the institutions list.
        </p>
        <button className="btn btn--primary" style={{ width: "100%" }} onClick={onClose}>
          Done
        </button>
      </Modal>
    );
  }

  if (step === STEPS.VERIFY) {
    return (
      <Modal isOpen title="Enter verification code" onClose={onClose}>
        <p style={{ marginBottom: "1.5rem", color: "var(--color-ink-soft)", fontSize: "var(--text-sm)" }}>
          We've sent a 6-digit code to your email. Enter it below to confirm creating this institution.
        </p>
        <form onSubmit={codeForm.handleSubmit((values) => confirmMutation.mutate(values))} noValidate>
          <div className="form-field">
            <label htmlFor="code">6-digit code</label>
            <input
              id="code"
              type="text"
              inputMode="numeric"
              maxLength={6}
              {...codeForm.register("code")}
            />
            {codeForm.formState.errors.code && (
              <p className="field-error">{codeForm.formState.errors.code.message}</p>
            )}
          </div>

          {serverError && <p className="form-error" role="alert">{serverError}</p>}

          <button
            type="submit"
            className="btn btn--primary"
            style={{ width: "100%" }}
            disabled={confirmMutation.isPending}
          >
            {confirmMutation.isPending ? "Confirming..." : "Confirm and create"}
          </button>
        </form>
      </Modal>
    );
  }

  return (
    <Modal isOpen title="Create institution" onClose={onClose}>
      <form onSubmit={detailsForm.handleSubmit((values) => requestMutation.mutate(values))} noValidate>
        <div className="form-field">
          <label htmlFor="name">Institution name</label>
          <input id="name" type="text" {...detailsForm.register("name")} />
          {detailsForm.formState.errors.name && (
            <p className="field-error">{detailsForm.formState.errors.name.message}</p>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="code">Institution code</label>
          <input id="code" type="text" placeholder="e.g. khs" {...detailsForm.register("code")} />
          {detailsForm.formState.errors.code && (
            <p className="field-error">{detailsForm.formState.errors.code.message}</p>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="type">Institution type</label>
          <select id="type" {...detailsForm.register("type")}>
            <option value="">Select a type</option>
            {INSTITUTION_TYPES.map((t) => (
              <option key={t} value={t}>{t.replace("_", " ")}</option>
            ))}
          </select>
          {detailsForm.formState.errors.type && (
            <p className="field-error">{detailsForm.formState.errors.type.message}</p>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="country">Country</label>
          <input id="country" type="text" {...detailsForm.register("country")} />
          {detailsForm.formState.errors.country && (
            <p className="field-error">{detailsForm.formState.errors.country.message}</p>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="address">Address (optional)</label>
          <input id="address" type="text" {...detailsForm.register("address")} />
        </div>

        <div className="form-field">
          <label htmlFor="official_email">Official email (optional)</label>
          <input id="official_email" type="email" {...detailsForm.register("official_email")} />
          {detailsForm.formState.errors.official_email && (
            <p className="field-error">{detailsForm.formState.errors.official_email.message}</p>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="phone">Phone (optional)</label>
          <input id="phone" type="text" {...detailsForm.register("phone")} />
        </div>

        <div className="form-field">
          <label htmlFor="website">Website (optional)</label>
          <input id="website" type="text" {...detailsForm.register("website")} />
        </div>

        {serverError && <p className="form-error" role="alert">{serverError}</p>}

        <button
          type="submit"
          className="btn btn--primary"
          style={{ width: "100%" }}
          disabled={requestMutation.isPending}
        >
          {requestMutation.isPending ? "Sending code..." : "Send verification code"}
        </button>
      </form>
    </Modal>
  );
}