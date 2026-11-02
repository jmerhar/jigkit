import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import { fakeApi, refuse } from "../testing";
import Notes from "./Notes.svelte";

const NOTE = { id: 7, title: "Groceries", body: "milk", created_at: "2026-10-18T14:05:00Z", updated_at: "2026-10-18T14:05:00Z" };

describe("Notes", () => {
  it("lists notes, and says when there are none", async () => {
    render(Notes, { api: fakeApi({ "GET /notes": [NOTE] }).api });
    expect(await screen.findByText("Groceries")).toBeInTheDocument();
    expect(screen.getByText("milk")).toBeInTheDocument();
    document.body.innerHTML = "";

    render(Notes, { api: fakeApi({ "GET /notes": [] }).api });
    expect(await screen.findByText("No notes yet.")).toBeInTheDocument();
  });

  it("keeps a new note", async () => {
    let saved = false;
    const { api, calls } = fakeApi({
      "GET /notes": () => (saved ? [NOTE] : []),
      "POST /notes": () => ((saved = true), NOTE),
    });
    render(Notes, { api });
    await fireEvent.click(await screen.findByRole("button", { name: "New note" }));
    await fireEvent.input(screen.getByLabelText("Title"), { target: { value: "Groceries" } });
    await fireEvent.input(screen.getByLabelText("Note"), { target: { value: "milk" } });
    await fireEvent.submit(screen.getByRole("button", { name: "Save" }).closest("form")!);

    expect(await screen.findByText("Groceries")).toBeInTheDocument();
    expect(calls.find((call) => call.method === "POST")!.body).toEqual({ title: "Groceries", body: "milk" });
  });

  it("changes a note, or leaves it as it was", async () => {
    const { api, calls } = fakeApi({ "GET /notes": [NOTE], "PUT /notes/7": { ...NOTE, title: "Shopping" } });
    render(Notes, { api });
    await fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    expect(screen.getByLabelText("Title")).toHaveValue("Groceries");
    await fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText("Title")).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    await fireEvent.input(screen.getByLabelText("Title"), { target: { value: "Shopping" } });
    await fireEvent.submit(screen.getByRole("button", { name: "Save" }).closest("form")!);
    await waitFor(() => expect(calls.some((call) => call.method === "PUT")).toBe(true));
    expect(calls.find((call) => call.method === "PUT")!.body).toEqual({ title: "Shopping", body: "milk" });
  });

  it("deletes a note once confirmed", async () => {
    const { api, calls } = fakeApi({ "GET /notes": [NOTE] });
    const { unmount } = render(Notes, { api, confirmDelete: () => false });
    await fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(calls.some((call) => call.method === "DELETE")).toBe(false);
    unmount();

    render(Notes, { api, confirmDelete: () => true });
    await fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.queryByText("Groceries")).not.toBeInTheDocument());
  });

  it("says what went wrong", async () => {
    render(Notes, { api: fakeApi({ "GET /notes": refuse(500, "boom") }).api });
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong (boom).");
    document.body.innerHTML = "";

    const { api } = fakeApi({ "GET /notes": [NOTE], "POST /notes": refuse(422, "invalid"), "DELETE /notes/7": refuse(404, "not_found") });
    render(Notes, { api, confirmDelete: () => true });
    await fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That is no longer here.");
    await fireEvent.click(screen.getByRole("button", { name: "New note" }));
    await fireEvent.input(screen.getByLabelText("Title"), { target: { value: "x" } });
    await fireEvent.submit(screen.getByRole("button", { name: "Save" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Some of that is not valid.");
  });
});
