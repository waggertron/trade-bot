import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StatCard from "../StatCard";

describe("StatCard", () => {
  it("renders title and value", () => {
    render(<StatCard title="Total Value" value="$50,000" />);
    expect(screen.getByText("Total Value")).toBeInTheDocument();
    expect(screen.getByText("$50,000")).toBeInTheDocument();
  });

  it("renders subtitle when provided", () => {
    render(<StatCard title="P&L" value="+$500" subtitle="+2.5% today" />);
    expect(screen.getByText("+2.5% today")).toBeInTheDocument();
  });

  it("applies profit color class for trend up", () => {
    render(<StatCard title="P&L" value="+$500" trend="up" />);
    const valueEl = screen.getByText("+$500");
    expect(valueEl.className).toContain("text-profit");
  });

  it("applies loss color class for trend down", () => {
    render(<StatCard title="P&L" value="-$300" trend="down" />);
    const valueEl = screen.getByText("-$300");
    expect(valueEl.className).toContain("text-loss");
  });
});
