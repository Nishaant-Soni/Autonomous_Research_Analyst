import { act } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { createRoot, type Root } from "react-dom/client";
import { ReportMarkdown } from "./ReportMarkdown";

// The report incorporates web/document content, so it is partially attacker-influenced.
// These tests lock the safe-render contract: a future change (e.g. adding rehype-raw) that
// reintroduced XSS would fail here.

let container: HTMLDivElement;
let root: Root;

function render(md: string) {
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => {
    root.render(<ReportMarkdown reportMd={md} onCiteClick={() => {}} />);
  });
}

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

describe("ReportMarkdown safe rendering", () => {
  it("does not render raw HTML (e.g. <script>) embedded in the report", () => {
    render("# Title\n\nfindings\n\n<script>window.__pwned = true</script>\n");
    // No raw-HTML plugin => the script is escaped to text, never a real <script> element.
    expect(container.querySelector("script")).toBeNull();
  });

  it("neutralizes javascript: links", () => {
    render("A [bad link](javascript:alert(1)) here.");
    for (const a of Array.from(container.querySelectorAll("a"))) {
      expect(a.getAttribute("href") ?? "").not.toMatch(/^javascript:/i);
    }
  });

  it("renders safe external links with rel=noreferrer and target=_blank", () => {
    render("See [example](https://example.com) for details.");
    const a = container.querySelector("a");
    expect(a).not.toBeNull();
    expect(a!.getAttribute("href")).toMatch(/^https:\/\/example\.com/);
    expect(a!.getAttribute("rel")).toContain("noreferrer");
    expect(a!.getAttribute("target")).toBe("_blank");
  });
});
