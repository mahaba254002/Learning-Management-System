import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiRequest, ApiError } from "../../api/client";
import { inviteSubmissionSchema, GENDER_OPTIONS, EMPLOYMENT_TYPE_OPTIONS } from "./inviteSubmissionSchema";
import "../auth/LoginPage.css";
import "./InvitePage.css";

export default function InvitePage() {
  const { token } = useParams();
  const [submitted, setSubmitted] = useState(false);
  const [serverError, setServerError] = useState(null);

  const invitationQuery = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => apiRequest(`/api/invitations/${token}`),
    retry: false,
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(inviteSubmissionSchema) });

  const submitMutation = useMutation({
    mutationFn: (values) =>
      apiRequest(`/api/invitations/${token}/submit`, { method: "POST", body: values }),
    onSuccess: () => setSubmitted(true),
    onError: (err) => {
      setServerError(err instanceof ApiError ? err.message : "Something went wrong.");
    },
  });

  if (invitationQuery.isLoading) {
    return <div className="invite-page"><p>Loading invitation...</p></div>;
  }

  if (invitationQuery.isError) {
    const status = invitationQuery.error instanceof ApiError ? invitationQuery.error.status : null;
    return (
      <div className="invite-page">
        <div className="invite-card">
          <h1>Invitation not found</h1>
          <p className="invite-card__subtext">
            {status === 404
              ? "This invitation link is invalid or no longer exists."
              : "We couldn't load this invitation. Please try again later."}
          </p>
        </div>
      </div>
    );
  }

  const invitation = invitationQuery.data;

  if (invitation.status === "EXPIRED") {
    return (
      <div className="invite-page">
        <div className="invite-card">
          <h1>This invitation has expired</h1>
          <p className="invite-card__subtext">
            Please ask {invitation.institution_name} to send you a new invitation.
          </p>
        </div>
      </div>
    );
  }

  if (invitation.status === "SUBMITTED" || invitation.status === "APPROVED" || submitted) {
    return (
      <div className="invite-page">
        <div className="invite-card">
          <h1>{submitted ? "Thank you!" : "Already submitted"}</h1>
          <p className="invite-card__subtext">
            {submitted
              ? `Your information has been sent to ${invitation.institution_name}. They will review it and send you login credentials once approved.`
              : "This invitation has already been submitted and is awaiting review."}
          </p>
        </div>
      </div>
    );
  }

  if (invitation.status === "REJECTED") {
    return (
      <div className="invite-page">
        <div className="invite-card">
          <h1>Invitation no longer active</h1>
          <p className="invite-card__subtext">
            Please contact {invitation.institution_name} for more information.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="invite-page">
      <div className="invite-card">
        <h1>Join {invitation.institution_name}</h1>
        <p className="invite-card__subtext">
          You've been invited as a {invitation.invited_role.toLowerCase()}. Fill in your
          details below — an administrator will review and approve your account.
        </p>

        <form onSubmit={handleSubmit((values) => submitMutation.mutate(values))} noValidate>
          <div className="form-row">
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
          </div>

          <div className="form-row">
            <div className="form-field">
              <label htmlFor="gender">Gender</label>
              <select id="gender" {...register("gender")}>
                <option value="">Select</option>
                {GENDER_OPTIONS.map((g) => (
                  <option key={g} value={g}>{g.replace(/_/g, " ")}</option>
                ))}
              </select>
              {errors.gender && <p className="field-error">{errors.gender.message}</p>}
            </div>

            <div className="form-field">
              <label htmlFor="date_of_birth">Date of birth</label>
              <input id="date_of_birth" type="date" {...register("date_of_birth")} />
              {errors.date_of_birth && <p className="field-error">{errors.date_of_birth.message}</p>}
            </div>
          </div>

          <div className="form-field">
            <label htmlFor="phone">Phone (optional)</label>
            <input id="phone" type="text" {...register("phone")} />
          </div>

          <div className="form-field">
            <label htmlFor="qualification">Highest qualification</label>
            <input id="qualification" type="text" placeholder="e.g. BEd Mathematics" {...register("qualification")} />
            {errors.qualification && <p className="field-error">{errors.qualification.message}</p>}
          </div>

          <div className="form-field">
            <label htmlFor="specialization">Specialization (optional)</label>
            <input id="specialization" type="text" {...register("specialization")} />
          </div>

          <div className="form-field">
            <label htmlFor="employment_type">Employment type</label>
            <select id="employment_type" {...register("employment_type")}>
              <option value="">Select</option>
              {EMPLOYMENT_TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
              ))}
            </select>
            {errors.employment_type && <p className="field-error">{errors.employment_type.message}</p>}
          </div>

          {serverError && <p className="form-error" role="alert">{serverError}</p>}

          <button type="submit" className="btn btn--primary" disabled={isSubmitting} style={{ width: "100%" }}>
            {isSubmitting ? "Submitting..." : "Submit application"}
          </button>
        </form>
      </div>
    </div>
  );
}