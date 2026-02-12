import { mockDelay } from "./delay";

type MockHandler = (path: string, options?: RequestInit) => unknown | Promise<unknown>;

interface Route {
  pattern: RegExp;
  method: string;
  handler: MockHandler;
}

const routes: Route[] = [];

/** Register a mock route handler */
export function registerRoute(
  method: string,
  pattern: RegExp,
  handler: MockHandler,
) {
  routes.push({ pattern, method: method.toUpperCase(), handler });
}

/** Dispatch a request path+method to a registered mock handler */
export async function getMockResponse<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  await mockDelay();

  const method = (options?.method ?? "GET").toUpperCase();
  const pathOnly = path.split("?")[0];

  for (const route of routes) {
    if (route.method === method && route.pattern.test(pathOnly)) {
      const result = await route.handler(path, options);
      return result as T;
    }
  }

  console.warn(`[mock] No handler for ${method} ${path}`);
  return {} as T;
}
