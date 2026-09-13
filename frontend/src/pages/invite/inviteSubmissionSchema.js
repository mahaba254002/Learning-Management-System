import { z } from "zod";

export const GENDER_OPTIONS = ["MALE", "FEMALE", "OTHER", "PREFER_NOT_TO_SAY"];
export const EMPLOYMENT_TYPE_OPTIONS = ["FULL_TIME", "PART_TIME", "CONTRACT", "VISITING"];

export const inviteSubmissionSchema = z.object({
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  gender: z.enum(GENDER_OPTIONS, { message: "Select a gender" }),
  date_of_birth: z.string().min(1, "Date of birth is required"),
  phone: z.string().optional().or(z.literal("")),
  qualification: z.string().min(1, "Qualification is required"),
  specialization: z.string().optional().or(z.literal("")),
  employment_type: z.enum(EMPLOYMENT_TYPE_OPTIONS, { message: "Select an employment type" }),
});