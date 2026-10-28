import { z } from "zod";

export const studentLoginSchema = z.object({
  email: z.string().trim().min(1, "Enter your email or student ID").max(255).refine(
    value => value.includes("@") ? /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) : /^[A-Za-z0-9._/-]{1,60}$/.test(value),
    "Enter a valid email or student ID",
  ),
  password: z.string().min(1, "Enter your password"),
  remember_me: z.boolean().default(false),
});
