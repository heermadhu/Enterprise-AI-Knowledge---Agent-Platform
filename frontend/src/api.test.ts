import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API client", () => {
  it("sends JSON requests and returns decoded response data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: "ok" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await api<{ status: string }>("/api/health", {
      method: "POST",
      body: JSON.stringify({ query: "health" }),
    });

    expect(response.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/health$/),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({}),
      }),
    );
    const requestHeaders = fetchMock.mock.calls[0][1].headers as Headers;
    expect(requestHeaders.get("Content-Type")).toBe("application/json");
  });

  it("preserves safe API error details and status codes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 413,
        json: async () => ({ detail: "Upload exceeds the configured size limit." }),
      }),
    );

    await expect(api("/api/documents", { method: "POST" })).rejects.toMatchObject({
      name: "ApiError",
      message: "Upload exceeds the configured size limit.",
      status: 413,
    } satisfies Partial<ApiError>);
  });

  it("leaves multipart content type to the browser boundary encoder", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: 1 }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const form = new FormData();
    form.append("file", new Blob(["sample"], { type: "text/plain" }), "sample.txt");

    await api("/api/documents", { method: "POST", body: form });

    const requestHeaders = fetchMock.mock.calls[0][1].headers as Headers;
    expect(requestHeaders.has("Content-Type")).toBe(false);
  });
});
