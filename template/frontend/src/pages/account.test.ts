import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LANGUAGE_KEY } from "../lib/language";
import { ME, fakeApi, fakeAuthenticator, refuse } from "../testing";
import Account from "./Account.svelte";

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

function account(answers: Record<string, unknown>, me = ME) {
  const { api, calls } = fakeApi({ "GET /auth/passkeys": [], ...answers });
  const reload = vi.fn();
  render(Account, { api, authenticator: fakeAuthenticator(), reload, me });
  return { calls, reload };
}

describe("Account", () => {
  it("saves the name, and reloads into a newly chosen language", async () => {
    const { calls, reload } = account({ "PUT /account": { ...ME, name: "Ana Silva", language: "pt-PT" } });
    await fireEvent.input(screen.getByLabelText("Name"), { target: { value: "Ana Silva" } });
    await fireEvent.change(screen.getByLabelText("Language"), { target: { value: "pt-PT" } });
    await fireEvent.submit(screen.getByRole("button", { name: "Save" }).closest("form")!);

    expect(await screen.findByRole("status")).toHaveTextContent("Saved.");
    expect(calls.find((call) => call.method === "PUT")!.body).toEqual({ name: "Ana Silva", language: "pt-PT" });
    expect(reload).toHaveBeenCalledOnce();
    expect(localStorage.getItem(LANGUAGE_KEY)).toBe("pt-PT");
  });

  it("keeps the language as it is when it did not change", async () => {
    const { reload } = account({ "PUT /account": ME });
    await fireEvent.submit(screen.getByRole("button", { name: "Save" }).closest("form")!);
    expect(await screen.findByRole("status")).toHaveTextContent("Saved.");
    expect(reload).not.toHaveBeenCalled();
  });

  it("chooses a theme on this browser", async () => {
    account({});
    await fireEvent.change(screen.getByLabelText("Theme"), { target: { value: "dark" } });
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("changes the password", async () => {
    const { calls } = account({});
    await fireEvent.input(screen.getByLabelText("Current password"), { target: { value: "correct horse battery" } });
    await fireEvent.input(screen.getByLabelText(/^New password/), { target: { value: "a new password" } });
    await fireEvent.submit(screen.getByRole("button", { name: "Change the password" }).closest("form")!);

    expect(await screen.findByRole("status")).toHaveTextContent("every other browser is logged out");
    expect(calls.find((call) => call.path === "/account/password")!.body).toEqual({
      current: "correct horse battery",
      new: "a new password",
    });
  });

  it("explains a refusal", async () => {
    account({ "PUT /account/password": refuse(403, "wrong_password") });
    await fireEvent.input(screen.getByLabelText("Current password"), { target: { value: "x" } });
    await fireEvent.input(screen.getByLabelText(/^New password/), { target: { value: "a new password" } });
    await fireEvent.submit(screen.getByRole("button", { name: "Change the password" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("The current password is not right.");
  });

  it("sends a test notification where notifications are set up", async () => {
    account({});
    await fireEvent.click(screen.getByRole("button", { name: "Send a test notification" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Test notification sent.");
    document.body.innerHTML = "";

    account({ "POST /account/test-notification": refuse(502, "notification_failed") });
    await fireEvent.click(screen.getByRole("button", { name: "Send a test notification" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The notification could not be sent.");
    document.body.innerHTML = "";

    account({}, { ...ME, notifications: false });
    expect(screen.queryByRole("button", { name: "Send a test notification" })).not.toBeInTheDocument();
  });

  it("lists the passkeys, or says why it could not", async () => {
    account({ "GET /auth/passkeys": [{ id: 1, label: "Phone", created_at: "2026-10-18T14:05:00Z", last_used_at: null }] });
    expect(await screen.findByText("Phone")).toBeInTheDocument();
    document.body.innerHTML = "";

    account({ "GET /auth/passkeys": refuse(500, "boom") });
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong (boom).");
  });

  it("says why the account could not be saved", async () => {
    account({ "PUT /account": refuse(422, "invalid") });
    await fireEvent.submit(screen.getByRole("button", { name: "Save" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Some of that is not valid.");
  });

  it("adds and removes passkeys", async () => {
    const passkey = { id: 1, label: "Phone", created_at: "2026-10-18T14:05:00Z", last_used_at: "2026-10-19T08:00:00Z" };
    vi.spyOn(window, "prompt").mockReturnValue("Laptop");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { calls } = account({
      "GET /auth/passkeys": [passkey],
      "POST /auth/passkeys/options": { challenge: "c" },
      "POST /auth/passkeys": { ...passkey, id: 2, label: "Laptop", last_used_at: null },
    });
    expect(await screen.findByText(/Last used/)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole("button", { name: "Add a passkey" }));
    expect(await screen.findByText("Laptop")).toBeInTheDocument();
    await fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]!);
    await waitFor(() => expect(screen.queryByText("Phone")).not.toBeInTheDocument());
    expect(calls.some((call) => call.method === "DELETE" && call.path === "/auth/passkeys/1")).toBe(true);
    vi.restoreAllMocks();
  });

  it("explains a passkey that could not be added", async () => {
    account({ "POST /auth/passkeys/options": refuse(400, "passkey_expired") });
    await fireEvent.click(await screen.findByRole("button", { name: "Add a passkey" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That took too long; try again.");
  });
});
