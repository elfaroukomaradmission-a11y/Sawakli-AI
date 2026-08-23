import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Home from "../src/app/page";

describe("Home page", () => {
  it("renders the Sawakli AI heading", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", { name: "Sawakli AI" }),
    ).toBeInTheDocument();
  });

  it("renders the frontend skeleton message", () => {
    render(<Home />);

    expect(
      screen.getByText("Frontend skeleton ready."),
    ).toBeInTheDocument();
  });
});
