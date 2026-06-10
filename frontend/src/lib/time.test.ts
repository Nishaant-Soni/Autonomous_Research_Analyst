import { describe, it, expect } from "vitest";
import { relativeTime } from "./time";

describe("relativeTime", () => {
  const now = new Date("2024-06-01T12:00:00Z");

  it("returns the original string for an invalid date", () => {
    expect(relativeTime("not-a-date", now)).toBe("not-a-date");
  });

  it("returns 'just now' for < 10s ago", () => {
    expect(relativeTime("2024-06-01T11:59:55Z", now)).toBe("just now");
  });

  it("returns seconds for 10–59s ago", () => {
    expect(relativeTime("2024-06-01T11:59:10Z", now)).toBe("50s ago");
  });

  it("returns minutes for 1–59m ago", () => {
    expect(relativeTime("2024-06-01T11:55:00Z", now)).toBe("5m ago");
  });

  it("returns hours for 1–23h ago", () => {
    expect(relativeTime("2024-06-01T10:00:00Z", now)).toBe("2h ago");
  });

  it("returns 'yesterday' for exactly 1 day ago", () => {
    expect(relativeTime("2024-05-31T12:00:00Z", now)).toBe("yesterday");
  });

  it("returns days for 2–5 days ago", () => {
    expect(relativeTime("2024-05-28T12:00:00Z", now)).toBe("4d ago");
  });

  it("returns a locale date string for >= 6 days ago", () => {
    const iso = "2024-05-24T12:00:00Z";
    expect(relativeTime(iso, now)).toBe(new Date(iso).toLocaleDateString());
  });
});
