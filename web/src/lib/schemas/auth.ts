import { z } from "zod";

export const UserSchema = z.object({
  id: z.string(),
  email: z.string(),
  name: z.string(),
  is_active: z.boolean(),
  is_verified: z.boolean(),
});

export const AuthResponseSchema = z.object({
  user: UserSchema,
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.string(),
});

export const OAuthAuthResponseSchema = z.object({
  user: UserSchema,
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.string(),
  is_new_user: z.boolean(),
});

export const RefreshResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
});

export const LoginResponseSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.string(),
});

export type User = z.infer<typeof UserSchema>;
export type AuthResponse = z.infer<typeof AuthResponseSchema>;
export type LoginResponse = z.infer<typeof LoginResponseSchema>;
export type RefreshResponse = z.infer<typeof RefreshResponseSchema>;
