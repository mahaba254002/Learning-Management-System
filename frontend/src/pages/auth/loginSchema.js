import { z } from "zod";
export const loginSchema = z.object({
  email: z.string().trim().email("Enter a valid email address").max(255),
  password: z.string().min(1, "Password is required").max(1024),
  remember_me: z.boolean().default(false),
});
