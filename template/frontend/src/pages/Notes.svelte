<script lang="ts">
  import { onMount } from "svelte";
  import type { Api, Note } from "../lib/api";
  import { errorMessage } from "../lib/errors";
  import { moment } from "../lib/format";
  import { m } from "../paraglide/messages.js";

  let { api, confirmDelete = (question: string) => confirm(question) }: {
    api: Api;
    confirmDelete?: (question: string) => boolean;
  } = $props();

  let notes = $state<Note[]>([]);
  let error = $state("");
  /** The note being written: null when none is, 0 for a new one. */
  let editing = $state<number | null>(null);
  let title = $state("");
  let body = $state("");
  let busy = $state(false);

  async function load(): Promise<void> {
    try {
      notes = await api.notes();
    } catch (failure) {
      error = errorMessage(failure);
    }
  }

  function edit(note: Note | null): void {
    editing = note?.id ?? 0;
    title = note?.title ?? "";
    body = note?.body ?? "";
    error = "";
  }

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    busy = true;
    error = "";
    try {
      if (editing) await api.updateNote(editing, { title, body });
      else await api.createNote({ title, body });
      editing = null;
      await load();
    } catch (failure) {
      error = errorMessage(failure);
    } finally {
      busy = false;
    }
  }

  async function remove(note: Note): Promise<void> {
    if (!confirmDelete(m.confirm_delete_note())) return;
    try {
      await api.deleteNote(note.id);
      notes = notes.filter((other) => other.id !== note.id);
    } catch (failure) {
      error = errorMessage(failure);
    }
  }

  onMount(load);
</script>

<h1>{m.notes_title()}</h1>
{#if error}<p role="alert">{error}</p>{/if}
{#if editing === null}
  <button type="button" onclick={() => edit(null)}>{m.note_new()}</button>
{:else}
  <form class="card" onsubmit={save}>
    <label>{m.field_title()}<input bind:value={title} required maxlength="200" /></label>
    <label>{m.field_body()}<textarea bind:value={body} rows="6" maxlength="20000"></textarea></label>
    <div class="actions">
      <button type="submit" disabled={busy}>{busy ? m.saving() : m.save()}</button>
      <button type="button" class="secondary" onclick={() => (editing = null)}>{m.cancel()}</button>
    </div>
  </form>
{/if}
<ul class="list">
  {#each notes as note (note.id)}
    <li>
      <span class="what">
        <strong>{note.title}</strong>
        <small>{m.note_updated({ when: moment(note.updated_at) })}</small>
        {#if note.body}<span class="body">{note.body}</span>{/if}
      </span>
      <button type="button" class="link" onclick={() => edit(note)}>{m.edit()}</button>
      <button type="button" class="link" onclick={() => remove(note)}>{m.delete()}</button>
    </li>
  {:else}
    <li class="muted">{m.notes_empty()}</li>
  {/each}
</ul>
