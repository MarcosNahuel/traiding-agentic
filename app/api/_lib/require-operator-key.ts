import { requireApiKey } from "./require-api-key";

export function requireOperatorKey(request: Request) {
  return requireApiKey(
    request,
    "OPERATOR_API_KEY",
    "X-Operator-Key",
    "Operational endpoints require OPERATOR_API_KEY in production"
  );
}
