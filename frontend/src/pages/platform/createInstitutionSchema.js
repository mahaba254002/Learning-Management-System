import { z } from "zod";

export const INSTITUTION_TYPES = [
  "UNIVERSITY",
  "COLLEGE",
  "HIGH_SCHOOL",
  "PRIMARY_SCHOOL",
  "TRAINING_INSTITUTION",
  "OTHER",
];

export const institutionDetailsSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  code: z
    .string()
    .min(2, "Code must be at least 2 characters")
    .max(20, "Code must be at most 20 characters")
    .regex(/^[a-zA-Z0-9-]+$/, "Code can only contain letters, numbers, and hyphens"),
  type: z.enum(INSTITUTION_TYPES, { message: "Select an institution type" }),
  country: z.string().min(2, "Country is required"),
  address: z.string().optional().or(z.literal("")),
  official_email: z.string().email("Enter a valid email").optional().or(z.literal("")),
  phone: z.string().optional().or(z.literal("")),
  website: z.string().optional().or(z.literal("")),
});

export const codeSchema = z.object({
  code: z.string().length(6, "Code must be exactly 6 digits"),
});