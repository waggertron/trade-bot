export const MOCK_ENABLED = process.env.NEXT_PUBLIC_MOCK === "true";

export { getMockResponse } from "./router";
export { MockWebSocket } from "./websocket";

// Import all data modules to register their routes (side effects)
if (MOCK_ENABLED) {
  import("./data/portfolio");
  import("./data/trading");
  import("./data/trades");
  import("./data/strategies");
  import("./data/analytics");
  import("./data/risk");
  import("./data/backtest");
  import("./data/news");
  import("./data/ml");
  import("./data/config");
  import("./data/system");
}
