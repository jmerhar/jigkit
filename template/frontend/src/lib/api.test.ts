import { describe, expect, it } from "vitest";
import { fakeApi } from "../testing";

describe("Api", () => {
  it("names each endpoint the interface uses", async () => {
    const { api, calls } = fakeApi({});
    await api.setupState();
    await api.setUp({ name: "A", login: "a", password: "p", language: null });
    await api.logIn("a", "p");
    await api.logOut();
    await api.me();
    await api.updateAccount({ name: "A", language: null });
    await api.changePassword("old", "new");
    await api.testNotification();
    await api.passkeys();
    await api.passkeyOptions();
    await api.addPasskey("Phone", { id: "c" });
    await api.removePasskey(3);
    await api.passkeyLoginOptions();
    await api.passkeyLogIn({ id: "c" });
    await api.notes();
    await api.createNote({ title: "t", body: "" });
    await api.updateNote(4, { title: "t", body: "" });
    await api.deleteNote(4);

    expect(calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      "GET /setup",
      "POST /setup",
      "POST /auth/login",
      "POST /auth/logout",
      "GET /auth/me",
      "PUT /account",
      "PUT /account/password",
      "POST /account/test-notification",
      "GET /auth/passkeys",
      "POST /auth/passkeys/options",
      "POST /auth/passkeys",
      "DELETE /auth/passkeys/3",
      "POST /auth/passkey-login/options",
      "POST /auth/passkey-login",
      "GET /notes",
      "POST /notes",
      "PUT /notes/4",
      "DELETE /notes/4",
    ]);
    expect(calls[6]!.body).toEqual({ current: "old", new: "new" });
  });
});
