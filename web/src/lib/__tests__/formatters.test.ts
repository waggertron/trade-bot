import { describe, it, expect } from "vitest";
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  formatPnL,
  formatTimestamp,
  formatTimeAgo,
  cn,
} from "../formatters";

// -- formatCurrency ----------------------------------------------------------

describe("formatCurrency", () => {
  it("formats a number input", () => {
    expect(formatCurrency(1234.56)).toBe("$1,234.56");
  });

  it("formats a string input", () => {
    expect(formatCurrency("1234.56")).toBe("$1,234.56");
  });

  it("returns fallback for NaN", () => {
    expect(formatCurrency("abc")).toBe("$0.00");
  });

  it("supports custom decimals", () => {
    expect(formatCurrency(1234.5678, 4)).toBe("$1,234.5678");
  });
});

// -- formatNumber ------------------------------------------------------------

describe("formatNumber", () => {
  it("formats a number", () => {
    expect(formatNumber(1234.56)).toBe("1,234.56");
  });

  it("formats a string", () => {
    expect(formatNumber("1234.56")).toBe("1,234.56");
  });

  it("returns fallback for NaN", () => {
    expect(formatNumber("abc")).toBe("0");
  });

  it("supports custom decimals", () => {
    expect(formatNumber(1234.5, 0)).toBe("1,235");
  });
});

// -- formatPercent -----------------------------------------------------------

describe("formatPercent", () => {
  it("adds + prefix for positive", () => {
    expect(formatPercent(5.5)).toBe("+5.5%");
  });

  it("shows negative without + prefix", () => {
    expect(formatPercent(-3.2)).toBe("-3.2%");
  });

  it("shows zero as positive", () => {
    expect(formatPercent(0)).toBe("+0.0%");
  });

  it("supports custom decimals", () => {
    expect(formatPercent(5.55, 2)).toBe("+5.55%");
  });
});

// -- formatPnL ---------------------------------------------------------------

describe("formatPnL", () => {
  it("formats positive P&L", () => {
    const result = formatPnL(1234.56);
    expect(result).toMatch(/^\+\$/);
    expect(result).toContain("1,234.56");
  });

  it("formats negative P&L", () => {
    const result = formatPnL(-500);
    expect(result).toMatch(/^-\$/);
    expect(result).toContain("500.00");
  });

  it("formats zero as positive", () => {
    const result = formatPnL(0);
    expect(result).toMatch(/^\+\$/);
  });
});

// -- formatTimestamp ---------------------------------------------------------

describe("formatTimestamp", () => {
  it("formats a valid ISO string", () => {
    const result = formatTimestamp("2024-06-15T14:30:00Z");
    expect(result).toBeTruthy();
    // Should contain month and day parts
    expect(result).toMatch(/Jun/);
    expect(result).toMatch(/15/);
  });
});

// -- formatTimeAgo -----------------------------------------------------------

describe("formatTimeAgo", () => {
  it("returns 'just now' for < 1 min", () => {
    const now = new Date().toISOString();
    expect(formatTimeAgo(now)).toBe("just now");
  });

  it("returns minutes for < 60 min", () => {
    const past = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(formatTimeAgo(past)).toBe("5m ago");
  });

  it("returns hours for < 24 hours", () => {
    const past = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    expect(formatTimeAgo(past)).toBe("3h ago");
  });

  it("returns days for >= 24 hours", () => {
    const past = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatTimeAgo(past)).toBe("2d ago");
  });
});

// -- cn ----------------------------------------------------------------------

describe("cn", () => {
  it("combines classes", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("filters falsy values", () => {
    expect(cn("foo", false, undefined, null, "bar")).toBe("foo bar");
  });
});
