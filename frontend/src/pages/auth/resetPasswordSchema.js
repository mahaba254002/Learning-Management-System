import { z } from "zod";

export const resetPasswordSchema = z
  .object({
    code: z.string().min(6, "Code must be 6 digits").max(6, "Code must be 6 digits"),
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });