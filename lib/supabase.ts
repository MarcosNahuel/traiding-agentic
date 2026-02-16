import { createClient } from "@supabase/supabase-js";

function getEnvVar(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing environment variable: ${name}`);
  }
  return value;
}

// Server-side client with service role (full access, bypasses RLS)
export function createServerClient() {
  return createClient(
    getEnvVar("NEXT_PUBLIC_SUPABASE_URL"),
    getEnvVar("SUPABASE_SERVICE_ROLE_KEY"),
    {
      auth: { persistSession: false },
    }
  );
}

// Browser-side client (uses anon key, respects RLS)
export function createBrowserClient() {
  return createClient(
    getEnvVar("NEXT_PUBLIC_SUPABASE_URL"),
    getEnvVar("NEXT_PUBLIC_SUPABASE_ANON_KEY")
  );
}
