import { z } from "zod";

export const passwordSchema = z.string()
  .min(8, "Use at least 8 characters")
  .regex(/\p{Lu}/u, "Include an uppercase letter")
  .regex(/\p{Ll}/u, "Include a lowercase letter")
  .regex(/\p{Nd}/u, "Include a number")
  .regex(/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?`~]/, "Include a symbol, such as ! or @");
