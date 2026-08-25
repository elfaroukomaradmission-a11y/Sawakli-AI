import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}));

import { redirect } from "next/navigation";
import Home from "../src/app/page";

describe("Home page", () => {
  it("redirects to /dashboard", () => {
    Home();
    expect(redirect).toHaveBeenCalledWith("/dashboard");
  });
});
