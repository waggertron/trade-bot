import "@testing-library/jest-dom";
import { vi } from "vitest";

// Deterministic UUID for tests
let counter = 0;
vi.stubGlobal("crypto", {
  ...globalThis.crypto,
  randomUUID: () => `test-uuid-${++counter}` as `${string}-${string}-${string}-${string}-${string}`,
});
