import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { errorMessage } from "./errors";

describe("errorMessage", () => {
  it("translates the API's codes, and says when it cannot be reached", () => {
    expect(errorMessage(new ApiError(401, "invalid_login"))).toBe("That username and password do not match.");
    expect(errorMessage(new ApiError(0, "Failed to fetch"))).toBe("The app cannot be reached; check the connection.");
  });

  it("passes on anything else", () => {
    expect(errorMessage(new ApiError(500, "boom"))).toBe("Something went wrong (boom).");
    expect(errorMessage("plain")).toBe("Something went wrong (plain).");
  });
});
