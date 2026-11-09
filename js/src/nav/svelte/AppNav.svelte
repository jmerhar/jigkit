<!--
  @component
  The application's navigation: the brand, its pages, a drop-down per menu, the application's own
  tools (a search box) and the account's menu. Where it all fits on one line it is one bar across
  the top; where it does not, as on a phone, the pages become a tab bar along the bottom, where
  the thumb is, with a "More" tab that opens upwards and lists the pages kept off the tab bar and
  every menu's entries. The bar measures itself, so each application switches at its own width. One menu is
  open at a time, and it closes on Escape, on a click outside it, and when one of its entries is
  chosen. Styled by base.css through the `app-*` classes.
-->
<script lang="ts">
  import { tick, type Snippet } from "svelte";
  import type { NavAccount, NavItem, NavLabels, NavMenu } from "./types.js";

  interface Props {
    /** The application's name, linking to `home`. */
    brand: string;
    home: string;
    pages: NavItem[];
    menus?: NavMenu[];
    account?: NavAccount;
    labels: NavLabels;
    /** Shown in the bar between the pages and the account's menu, such as a search box. */
    tools?: Snippet;
  }

  let { brand, home, pages, menus = [], account, labels, tools }: Props = $props();

  const id = $props.id();
  let open = $state<string | null>(null);

  /** Whether the bar has no room for the pages, which then go to the tab bar. */
  let compact = $state(false);
  let inner = $state<HTMLElement>();
  /** The width the bar needed when it last overflowed, which it must have again to widen. */
  let needed = 0;

  function fit(): void {
    if (!inner) return;
    if (!compact && inner.scrollWidth > inner.clientWidth) {
      needed = inner.scrollWidth;
      compact = true;
    } else if (compact && inner.clientWidth >= needed) {
      compact = false;
      // Wide again: check once drawn, in case the entries have grown since.
      void tick().then(fit);
    }
  }

  $effect(() => {
    if (!inner || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(fit);
    observer.observe(inner);
    return () => observer.disconnect();
  });

  // Entries that change (a name, a count, a language) may no longer fit.
  $effect(() => {
    void [brand, pages, menus, account];
    if (!compact) void tick().then(fit);
  });

  /** What the phone's "More" lists: the pages kept off the tab bar, then each menu. */
  const more = $derived(
    [
      { label: "", items: pages.filter((page) => page.tab === false) },
      ...menus.map((menu) => ({ label: menu.label, items: menu.items })),
    ].filter((section) => section.items.length > 0),
  );

  const anyCurrent = (items: NavItem[]) => items.some((item) => item.current);
  const anyBadge = (items: NavItem[]) => items.some((item) => item.badge !== undefined && item.badge !== "");

  function toggle(menu: string): void {
    open = open === menu ? null : menu;
  }

  /** Close the menu once one of its entries is chosen. */
  function chosen(event: MouseEvent): void {
    if ((event.target as Element | null)?.closest("a, button")) open = null;
  }

  function outside(event: MouseEvent): void {
    if (open && !(event.target as Element | null)?.closest?.("[data-app-menu]")) open = null;
  }
</script>

<svelte:window onkeydown={(event) => event.key === "Escape" && (open = null)} onclick={outside} />

{#snippet entry(item: NavItem)}
  {#if item.href !== undefined}
    <a href={item.href} aria-current={item.current ? "page" : undefined}>
      {#if item.icon}<item.icon aria-hidden="true" />{/if}<span>{item.label}</span>
      {#if item.badge !== undefined && item.badge !== ""}<span class="app-badge">{item.badge}</span>{/if}
    </a>
  {:else}
    <button type="button" onclick={item.onclick}>
      {#if item.icon}<item.icon aria-hidden="true" />{/if}<span>{item.label}</span>
    </button>
  {/if}
{/snippet}

{#snippet panel(key: string, sections: { label: string; items: NavItem[] }[], end = false)}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
  <ul class="app-menu-panel" class:end id="{id}-{key}" onclick={chosen}>
    {#each sections as section, i (i)}
      {#if sections.length > 1 && section.label}<li class="app-menu-heading">{section.label}</li>{/if}
      {#each section.items as item (item.label)}<li>{@render entry(item)}</li>{/each}
    {/each}
  </ul>
{/snippet}

<header class="app-bar" data-compact={compact || undefined}>
  <div class="app-bar-inner" bind:this={inner}>
    <a class="brand" href={home} title={brand}>{brand}</a>
    <nav class="app-pages" aria-label={labels.nav}>
      {#each pages as page (page.label)}
        <a
          href={page.href}
          class:app-wide-only={page.tab === false}
          aria-current={page.current ? "page" : undefined}
        >
          {#if page.icon}<page.icon aria-hidden="true" />{/if}<span>{page.label}</span>
          {#if page.badge !== undefined && page.badge !== ""}<span class="app-badge">{page.badge}</span>{/if}
        </a>
      {/each}
      {#each menus as menu, i (menu.label)}
        <div class="app-menu app-wide-only" data-app-menu>
          <button
            type="button"
            class="app-menu-button"
            class:current={anyCurrent(menu.items)}
            class:marked={anyBadge(menu.items)}
            aria-expanded={open === `menu-${i}`}
            aria-controls="{id}-menu-{i}"
            onclick={() => toggle(`menu-${i}`)}
          >
            {#if menu.icon}<menu.icon aria-hidden="true" />{/if}<span>{menu.label}</span><span
              class="app-chevron"
              aria-hidden="true"
            ></span>
          </button>
          {#if open === `menu-${i}`}{@render panel(`menu-${i}`, [{ label: "", items: menu.items }])}{/if}
        </div>
      {/each}
      {#if more.length > 0}
        <div class="app-menu app-more" data-app-menu>
          <button
            type="button"
            class="app-menu-button"
            class:current={more.some((section) => anyCurrent(section.items))}
            class:marked={more.some((section) => anyBadge(section.items))}
            aria-expanded={open === "more"}
            aria-controls="{id}-more"
            onclick={() => toggle("more")}
          >
            {#if labels.moreIcon}<labels.moreIcon aria-hidden="true" />{/if}<span>{labels.more}</span>
          </button>
          {#if open === "more"}{@render panel("more", more, true)}{/if}
        </div>
      {/if}
    </nav>
    {#if tools}<div class="app-tools">{@render tools()}</div>{/if}
    {#if account}
      <div class="app-menu app-account" data-app-menu>
        <button
          type="button"
          class="app-menu-button"
          class:current={anyCurrent(account.items ?? [])}
          aria-expanded={open === "account"}
          aria-controls="{id}-account"
          onclick={() => toggle("account")}
        >
          {#if account.icon}<account.icon aria-hidden="true" />{/if}<span class="app-name">{account.name}</span><span
            class="app-chevron"
            aria-hidden="true"
          ></span>
        </button>
        {#if open === "account"}
          <ul class="app-menu-panel end" id="{id}-account">
            {#each account.items ?? [] as item (item.label)}
              <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
              <li onclick={chosen}>{@render entry(item)}</li>
            {/each}
            {#each account.switches ?? [] as choice (choice.label)}
              <li class="app-switch" role="group" aria-label={choice.label}>
                {#each choice.options as option (option.value)}
                  <button
                    type="button"
                    aria-pressed={choice.value === option.value}
                    aria-label={option.icon ? option.label : undefined}
                    title={option.icon ? option.label : undefined}
                    onclick={() => choice.onchange(option.value)}
                  >
                    {#if option.icon}<option.icon aria-hidden="true" />{:else}{option.label}{/if}
                  </button>
                {/each}
              </li>
            {/each}
            {#if account.logOut}
              <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
              <li onclick={chosen}>{@render entry(account.logOut)}</li>
            {/if}
          </ul>
        {/if}
      </div>
    {/if}
  </div>
</header>
