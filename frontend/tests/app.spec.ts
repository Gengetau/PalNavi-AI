import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../src/App.vue";
import type {
  BreedingCallResult,
  BreedingClient,
} from "../src/api/breedingContract";
import type {
  SpeciesCatalogCallResult,
  SpeciesCatalogClient,
} from "../src/api/breedingCatalogContract";
import type {
  ExplainCallResult,
  KnowledgeClient,
  SearchCallResult,
} from "../src/api/contract";
import {
  syntheticCitation,
  syntheticExplainCitation,
  syntheticSearchItem,
} from "./fixtures";
import {
  breedingGenderRequired,
  breedingRequest,
  breedingSuccess,
  breedingUnreachable,
  breedingZeroStepSuccess,
  speciesCatalogSuccess,
} from "./breeding-fixtures";

let wrapper: VueWrapper | undefined;

afterEach(() => {
  wrapper?.unmount();
  wrapper = undefined;
});

function clientWith(
  overrides: Partial<KnowledgeClient> = {},
): KnowledgeClient {
  return {
    search: vi.fn(async (): Promise<SearchCallResult> => ({
      kind: "search-success",
      results: [],
      message: null,
    })),
    explain: vi.fn(async (): Promise<ExplainCallResult> => ({
      kind: "unsupported",
      message: "No usable synthetic evidence.",
    })),
    ...overrides,
  };
}

async function enterQuestion(
  value = "fictional signal route",
): Promise<void> {
  await wrapper!.get("textarea[name=query]").setValue(value);
}

describe("synthetic knowledge UI", () => {
  it("starts accessible, idle, synthetic-only, and makes no request on mount", () => {
    const client = clientWith();
    wrapper = mount(App, { props: { client } });

    expect(wrapper.get("h1").text()).toBe("Synthetic Knowledge Navigator");
    expect(wrapper.text()).toContain("Ready to navigate");
    expect(wrapper.get('label[for="knowledge-query"]').text()).toContain(
      "Question",
    );
    expect(wrapper.get('label[for="synthetic-only"]').text()).toContain(
      "Synthetic knowledge only",
    );
    const checkbox = wrapper.get<HTMLInputElement>("#synthetic-only");
    expect(checkbox.element.checked).toBe(true);
    expect(wrapper.get('label[for="synthetic-only"]').text()).toContain("ON");
    expect(wrapper.get<HTMLInputElement>("#knowledge-limit").element.value).toBe(
      "5",
    );
    expect(wrapper.get('button[type="submit"]').text()).toBe(
      "Search knowledge",
    );
    expect(wrapper.get("#knowledge-query").attributes("aria-describedby")).toBe(
      "query-help query-count",
    );
    expect(client.search).not.toHaveBeenCalled();
    expect(client.explain).not.toHaveBeenCalled();
  });

  it("validates all fields, focuses the first error, and does not call the client", async () => {
    const client = clientWith();
    wrapper = mount(App, { props: { client }, attachTo: document.body });
    await wrapper.get("#knowledge-language").setValue("bad tag");
    await wrapper.get("#knowledge-limit").setValue("21");
    await wrapper.get("form").trigger("submit");

    expect(client.search).not.toHaveBeenCalled();
    expect(wrapper.get('[role="alert"]').text()).toContain(
      "Check the highlighted fields",
    );
    expect(wrapper.get("#knowledge-query").attributes("aria-invalid")).toBe(
      "true",
    );
    expect(wrapper.get("#knowledge-query").attributes("aria-describedby")).toContain(
      "query-error",
    );
    expect(document.activeElement).toBe(wrapper.get("#knowledge-query").element);

    await wrapper.get("#knowledge-query").setValue("fixed query");
    expect(wrapper.find("#query-error").exists()).toBe(false);
    expect(wrapper.find("#language-error").exists()).toBe(true);
  });

  it("omits blank optionals and sends the visible synthetic request", async () => {
    const client = clientWith();
    wrapper = mount(App, { props: { client } });
    await enterQuestion("  fictional   signal  ");
    await wrapper.get("#knowledge-language").setValue("  ");
    await wrapper.get("#knowledge-version").setValue("\n");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(client.search).toHaveBeenCalledTimes(1);
    expect(client.search).toHaveBeenCalledWith(
      {
        query: "fictional   signal",
        synthetic_only: true,
        limit: 5,
      },
      { signal: expect.any(AbortSignal) },
    );
    expect(wrapper.text()).toContain("No knowledge results matched this query");
  });

  it("sends complete filters and visibly represents synthetic OFF", async () => {
    const client = clientWith();
    wrapper = mount(App, { props: { client } });
    await enterQuestion();
    await wrapper.get("#knowledge-language").setValue("en-US");
    await wrapper.get("#knowledge-version").setValue("synthetic-0.0.0");
    await wrapper.get("#knowledge-limit").setValue("3");
    await wrapper.get("#synthetic-only").setValue(false);
    expect(wrapper.get('label[for="synthetic-only"]').text()).toContain("OFF");
    await wrapper
      .get("button[type=button]")
      .trigger("keydown", { key: "Enter" });
    await wrapper.get("button[type=button]").trigger("click");
    await flushPromises();

    expect(client.explain).toHaveBeenCalledWith(
      {
        query: "fictional signal route",
        language: "en-US",
        exact_game_version: "synthetic-0.0.0",
        synthetic_only: false,
        limit: 3,
      },
      { signal: expect.any(AbortSignal) },
    );
  });

  it("renders ordered search results and canonical citation details", async () => {
    const client = clientWith({
      search: vi.fn(
        async (): Promise<SearchCallResult> => ({
          kind: "search-success",
          results: [
            syntheticSearchItem({ title: "First synthetic result" }),
          syntheticSearchItem({
            document_id: "synthetic-document-beta",
            chunk_id: "synthetic-document-beta-0002",
            title: "Second synthetic result",
            score: 0.5,
            citation: syntheticCitation({
              document_id: "synthetic-document-beta",
              chunk_id: "synthetic-document-beta-0002",
              title: "Second synthetic result",
            }),
          }),
          ],
          message: "Synthetic corpus only.",
        }),
      ),
    });
    wrapper = mount(App, { props: { client } });
    await enterQuestion();
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    const cards = wrapper.findAll(".knowledge-card");
    expect(cards).toHaveLength(2);
    expect(cards[0]!.text()).toContain("First synthetic result");
    expect(cards[1]!.text()).toContain("Second synthetic result");
    expect(cards[0]!.text()).toContain("score 0.875");
    expect(cards[0]!.find("details").exists()).toBe(true);
    expect(cards[0]!.get(".knowledge-text").attributes("lang")).toBe("en");
    expect(cards[0]!.get("h3").text()).toBe("First synthetic result");
    expect(cards[0]!.get(".citation-details").text()).toContain(
      "First synthetic result",
    );
    expect(cards[0]!.get(".citation-details").text()).toContain(
      "synthetic-document-alpha",
    );
    expect(cards[1]!.get("h3").text()).toBe("Second synthetic result");
    expect(cards[1]!.get(".citation-details").text()).toContain(
      "Second synthetic result",
    );
    expect(cards[1]!.get(".citation-details").text()).toContain(
      "synthetic-document-beta",
    );
    expect(wrapper.get(".submitted-scope").text()).toContain(
      "Synthetic knowledge only",
    );
    expect(wrapper.get('[role="status"]').text()).toContain(
      "Submitted scope: synthetic knowledge only",
    );
    expect(wrapper.text()).toContain("Synthetic corpus only");
  });

  it("announces and preserves the immutable submitted mixed scope", async () => {
    let resolveSearch!: (value: SearchCallResult) => void;
    const pending = new Promise<SearchCallResult>((resolve) => {
      resolveSearch = resolve;
    });
    const client = clientWith({
      search: vi.fn(() => pending),
    });
    wrapper = mount(App, { props: { client } });
    await enterQuestion("mixed fictional scope");
    await wrapper.get("#synthetic-only").setValue(false);
    await wrapper.get("form").trigger("submit");

    expect(wrapper.text()).toContain("Searching available knowledge");
    expect(wrapper.get('[role="status"]').text()).toContain(
      "synthetic-only filter off",
    );

    resolveSearch({
      kind: "search-success",
      results: [],
      message: null,
    });
    await flushPromises();
    expect(wrapper.get(".submitted-scope").text()).toContain(
      "Synthetic-only filter off",
    );
    expect(wrapper.get('[role="status"]').text()).toContain(
      "Submitted scope: synthetic-only filter off",
    );

    await wrapper.get("#synthetic-only").setValue(true);
    expect(wrapper.get('label[for="synthetic-only"]').text()).toContain("ON");
    expect(wrapper.get(".submitted-scope").text()).toContain(
      "Synthetic-only filter off",
    );
  });

  it("renders explanation and hostile-looking backend values as inert text", async () => {
    const hostileLocator = "javascript:alert('synthetic')";
    const client = clientWith({
      explain: vi.fn(
        async (): Promise<ExplainCallResult> => ({
          kind: "explain-success",
          answer: "<img src=x onerror=alert(1)> Fictional answer. [K1]",
          citations: [
            syntheticExplainCitation(
              "[K1]",
              syntheticCitation({
                title: "<script>synthetic title</script>",
                source_locator: hostileLocator,
              }),
            ),
          ],
          usage: { input_tokens: 0, total_tokens: 7 },
        }),
      ),
    });
    wrapper = mount(App, { props: { client } });
    await enterQuestion();
    await wrapper.get("button[type=button]").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("<img src=x onerror=alert(1)>");
    expect(wrapper.text()).toContain("<script>synthetic title</script>");
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find("script").exists()).toBe(false);
    expect(wrapper.find(`a[href^="javascript:"]`).exists()).toBe(false);
    expect(wrapper.find("code.source-locator").text()).toBe(hostileLocator);
    expect(wrapper.get(".answer-text").attributes("lang")).toBeUndefined();
    expect(wrapper.text()).toContain("Input");
    expect(wrapper.text()).toContain("0");
  });

  it.each([
    {
      result: {
        kind: "unsupported",
        message: "No usable evidence.",
      } satisfies ExplainCallResult,
      copy: "Grounded explanation unavailable",
      alert: false,
    },
    {
      result: {
        kind: "backend-error",
        errorCategory: "configuration_invalid",
        message: "Provider setup is unavailable.",
        httpStatus: 503,
      } satisfies ExplainCallResult,
      copy: "Provider setup is unavailable",
      alert: true,
    },
    {
      result: {
        kind: "http-invalid",
        reason: "response-shape",
        message: "Invalid response.",
        httpStatus: 200,
      } satisfies ExplainCallResult,
      copy: "Service response could not be used",
      alert: true,
    },
    {
      result: {
        kind: "network-error",
        message: "Service offline.",
      } satisfies ExplainCallResult,
      copy: "Knowledge service could not be reached",
      alert: true,
    },
  ])("renders typed state for $copy", async ({ result, copy, alert }) => {
    wrapper = mount(App, {
      props: {
        client: clientWith({ explain: vi.fn(async () => result) }),
      },
    });
    await enterQuestion();
    await wrapper.get("button[type=button]").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain(copy);
    expect(wrapper.get(".submitted-scope").text()).toContain(
      "Synthetic knowledge only",
    );
    expect(wrapper.find('[role="alert"]').exists()).toBe(alert);
  });

  it("retries the same request without clearing form input", async () => {
    const explain = vi
      .fn<KnowledgeClient["explain"]>()
      .mockResolvedValueOnce({
        kind: "network-error",
        message: "Service offline.",
      })
      .mockResolvedValueOnce({
        kind: "unsupported",
        message: "Still no evidence.",
      });
    wrapper = mount(App, { props: { client: clientWith({ explain }) } });
    await enterQuestion("retry this fictional query");
    await wrapper.get("button[type=button]").trigger("click");
    await flushPromises();
    const retry = wrapper
      .findAll("button")
      .find((button) => button.text() === "Retry last request");
    expect(retry).toBeDefined();
    await retry!.trigger("click");
    await flushPromises();

    expect(explain).toHaveBeenCalledTimes(2);
    expect(explain.mock.calls[1]?.[0]).toEqual(explain.mock.calls[0]?.[0]);
    expect(
      wrapper.get<HTMLTextAreaElement>("#knowledge-query").element.value,
    ).toBe("retry this fictional query");
  });

  it("aborts search and prevents a stale late response from replacing explanation", async () => {
    let resolveSearch!: (value: SearchCallResult) => void;
    let resolveExplain!: (value: ExplainCallResult) => void;
    const searchPromise = new Promise<SearchCallResult>((resolve) => {
      resolveSearch = resolve;
    });
    const explainPromise = new Promise<ExplainCallResult>((resolve) => {
      resolveExplain = resolve;
    });
    let searchSignal: AbortSignal | undefined;
    const client = clientWith({
      search: vi.fn((_request, options) => {
        searchSignal = options.signal;
        return searchPromise;
      }),
      explain: vi.fn(() => explainPromise),
    });
    wrapper = mount(App, { props: { client } });
    await enterQuestion("first fictional query");
    await wrapper.get("form").trigger("submit");
    await wrapper.get("#knowledge-query").setValue("new fictional query");
    await wrapper.get("button[type=button]").trigger("click");
    expect(searchSignal?.aborted).toBe(true);

    resolveExplain({
      kind: "explain-success",
      answer: "Newest fictional answer. [K1]",
      citations: [syntheticExplainCitation()],
      usage: null,
    });
    await flushPromises();
    expect(wrapper.text()).toContain("Newest fictional answer");

    resolveSearch({
      kind: "search-success",
      results: [syntheticSearchItem({ title: "STALE RESULT" })],
      message: null,
    });
    await flushPromises();
    expect(wrapper.text()).not.toContain("STALE RESULT");
  });
});

function breedingClientWith(
  result: BreedingCallResult = {
    kind: "success",
    response: breedingSuccess(),
  },
): BreedingClient {
  return { plan: vi.fn(async () => result) };
}

function catalogClientWith(
  result: SpeciesCatalogCallResult = {
    kind: "success",
    response: speciesCatalogSuccess(),
  },
): SpeciesCatalogClient {
  return { load: vi.fn(async () => result) };
}

async function switchToBreeding(): Promise<void> {
  await wrapper!.get<HTMLInputElement>('input[value="breeding"]').setValue();
}

async function fillGoldenBreedingForm(): Promise<void> {
  const request = breedingRequest();
  await wrapper!.get("#breeding-target-species").setValue(
    request.target.species_id,
  );
  await wrapper!.get("#breeding-target-gender").setValue(
    request.target.gender,
  );
  for (const [index, item] of request.inventory.entries()) {
    await wrapper!
      .get(".breeding-form fieldset:nth-of-type(2) > button")
      .trigger("click");
    await wrapper!
      .get(`[name="inventory-${index}-instance-id"]`)
      .setValue(item.instance_id);
    await wrapper!
      .get(`[name="inventory-${index}-species-id"]`)
      .setValue(item.species_id);
    await wrapper!
      .get(`[name="inventory-${index}-gender"]`)
      .setValue(item.gender);
  }
}

describe("verified breeding UI", () => {
  it("loads the catalog only after entering breeding and exposes all locales", async () => {
    const breedingCatalogClient = catalogClientWith();
    wrapper = mount(App, {
      props: {
        client: clientWith(),
        breedingClient: breedingClientWith(),
        breedingCatalogClient,
      },
    });

    expect(breedingCatalogClient.load).not.toHaveBeenCalled();
    await switchToBreeding();
    await flushPromises();

    expect(breedingCatalogClient.load).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("299 verified species available");
    expect(
      wrapper.findAll("#species-display-locale option").map((option) =>
        option.attributes("value"),
      ),
    ).toEqual([
      "de",
      "en",
      "es",
      "es-MX",
      "fr",
      "id",
      "it",
      "ja",
      "ko",
      "pl",
      "pt-BR",
      "ru",
      "th",
      "tr",
      "vi",
      "zh-Hans",
      "zh-Hant",
    ]);
    const anubis = wrapper.get(
      '#species-catalog-suggestions option[value="anubis"]',
    );
    expect(anubis.attributes("label")).toBe("Anubis · anubis");
  });

  it("normalizes localized target and inventory choices to stable IDs", async () => {
    const breedingClient = breedingClientWith();
    wrapper = mount(App, {
      props: {
        client: clientWith(),
        breedingClient,
        breedingCatalogClient: catalogClientWith(),
      },
    });
    await switchToBreeding();
    await flushPromises();
    await wrapper.get("#species-display-locale").setValue("ja");
    expect(
      wrapper
        .get('#species-catalog-suggestions option[value="anubis"]')
        .attributes("label"),
    ).toBe("アヌビス · anubis");

    await wrapper.get("#breeding-target-species").setValue("アヌビス");
    await wrapper
      .get(".breeding-form fieldset:nth-of-type(2) > button")
      .trigger("click");
    await wrapper
      .get('[name="inventory-0-instance-id"]')
      .setValue("anubis-owned");
    await wrapper
      .get('[name="inventory-0-species-id"]')
      .setValue("アヌビス");
    await wrapper
      .get('[name="inventory-0-gender"]')
      .setValue("female");
    await wrapper.get(".breeding-form").trigger("submit");
    await flushPromises();

    expect(
      wrapper.get<HTMLInputElement>("#breeding-target-species").element.value,
    ).toBe("anubis");
    expect(
      wrapper.get<HTMLInputElement>('[name="inventory-0-species-id"]').element
        .value,
    ).toBe("anubis");
    expect(breedingClient.plan).toHaveBeenCalledWith(
      {
        dataset_id:
          "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47",
        target: { species_id: "anubis", gender: "female" },
        inventory: [
          {
            instance_id: "anubis-owned",
            species_id: "anubis",
            gender: "female",
          },
        ],
        objective: "minimum_generations",
      },
      { signal: expect.any(AbortSignal) },
    );
  });

  it("keeps explicit manual ID entry when catalog loading fails", async () => {
    const breedingClient = breedingClientWith();
    wrapper = mount(App, {
      props: {
        client: clientWith(),
        breedingClient,
        breedingCatalogClient: catalogClientWith({
          kind: "network-error",
          message: "Catalog offline.",
        }),
      },
    });

    await switchToBreeding();
    await flushPromises();

    expect(wrapper.text()).toContain(
      "Catalog unavailable. Manual stable-ID entry remains available.",
    );
    expect(breedingClient.plan).not.toHaveBeenCalled();
    expect(
      wrapper.get<HTMLInputElement>("#breeding-target-species").element
        .disabled,
    ).toBe(false);
  });

  it("renders hostile-looking localized names as inert option text", async () => {
    const catalog = speciesCatalogSuccess();
    const anubis = catalog.records.find(
      (record) => record.species_id === "anubis",
    )!;
    anubis.localized_names.en = "<img src=x onerror=alert(1)>";
    wrapper = mount(App, {
      props: {
        client: clientWith(),
        breedingClient: breedingClientWith(),
        breedingCatalogClient: catalogClientWith({
          kind: "success",
          response: catalog,
        }),
      },
    });

    await switchToBreeding();
    await flushPromises();

    expect(wrapper.text()).toContain("<img src=x onerror=alert(1)>");
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find('a[href^="javascript:"]').exists()).toBe(false);
  });

  it("keeps knowledge as the default and switches to a truthful breeding disclosure", async () => {
    const breedingClient = breedingClientWith();
    wrapper = mount(App, {
      props: { client: clientWith(), breedingClient },
    });

    expect(wrapper.get("h1").text()).toBe(
      "Synthetic Knowledge Navigator",
    );
    expect(wrapper.get<HTMLInputElement>('input[value="knowledge"]').element.checked)
      .toBe(true);
    expect(wrapper.text()).toContain("No verified game facts loaded");
    expect(breedingClient.plan).not.toHaveBeenCalled();

    await switchToBreeding();
    expect(wrapper.get("h1").text()).toBe("Production Breeding Planner");
    expect(wrapper.text()).toContain("Read-only planning");
    expect(wrapper.text()).toContain(
      "palworld-pc-steam-v1.0.1-palcalc-8b7e2f779e47",
    );
    expect(wrapper.text()).toContain("does not read or modify a save file");
    expect(breedingClient.plan).not.toHaveBeenCalled();
  });

  it("rejects target and incomplete inventory locally and focuses the target", async () => {
    const breedingClient = breedingClientWith();
    wrapper = mount(App, {
      props: { client: clientWith(), breedingClient },
      attachTo: document.body,
    });
    await switchToBreeding();
    await wrapper
      .get(".breeding-form fieldset:nth-of-type(2) > button")
      .trigger("click");
    await wrapper.get(".breeding-form").trigger("submit");

    expect(breedingClient.plan).not.toHaveBeenCalled();
    expect(wrapper.get('[aria-label="Breeding form errors"]').text()).toContain(
      "Inventory row 1",
    );
    expect(wrapper.get("#breeding-target-species").attributes("aria-invalid"))
      .toBe("true");
    expect(document.activeElement).toBe(
      wrapper.get("#breeding-target-species").element,
    );
  });

  it("submits only the fixed accepted request and renders the two-generation route in order", async () => {
    const breedingClient = breedingClientWith();
    wrapper = mount(App, {
      props: { client: clientWith(), breedingClient },
    });
    await switchToBreeding();
    await fillGoldenBreedingForm();
    await wrapper.get(".breeding-form").trigger("submit");
    await flushPromises();

    expect(breedingClient.plan).toHaveBeenCalledWith(
      breedingRequest(),
      { signal: expect.any(AbortSignal) },
    );
    const steps = wrapper.findAll(".route-step");
    expect(steps).toHaveLength(2);
    expect(steps[0]!.text()).toContain(
      "dumud",
    );
    expect(steps[0]!.text()).toContain("katress_ignis");
    expect(steps[0]!.text()).toContain("katress");
    expect(steps[0]!.text()).toContain("ordinary_power");
    expect(steps[1]!.text()).toContain("katress");
    expect(steps[1]!.text()).toContain("wixen");
    expect(steps[1]!.text()).toContain("wixen_noct");
    expect(steps[1]!.text()).toContain("gender_directed");
    expect(wrapper.text()).toContain(
      "Probability-dependent cost is unavailable",
    );
    expect(wrapper.get('[role="status"]').text()).toContain(
      "2 breeding steps",
    );
  });

  it("renders a zero-step success without inventing a breeding step", async () => {
    const response = breedingZeroStepSuccess();
    wrapper = mount(App, {
      props: {
        client: clientWith(),
        breedingClient: breedingClientWith({
          kind: "success",
          response,
        }),
      },
    });
    await switchToBreeding();
    await wrapper.get("#breeding-target-species").setValue("wixen_noct");
    await wrapper
      .get(".breeding-form fieldset:nth-of-type(2) > button")
      .trigger("click");
    await wrapper
      .get('[name="inventory-0-instance-id"]')
      .setValue("wixen-noct-owned");
    await wrapper
      .get('[name="inventory-0-species-id"]')
      .setValue("wixen_noct");
    await wrapper
      .get('[name="inventory-0-gender"]')
      .setValue("female");
    await wrapper.get(".breeding-form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("Target already owned");
    expect(wrapper.findAll(".route-step")).toHaveLength(0);
  });

  it.each([
    {
      result: {
        kind: "gender-required",
        response: breedingGenderRequired(),
      } satisfies BreedingCallResult,
      copy: "Inventory genders are incomplete",
      detail: "katress-unknown",
      alert: false,
    },
    {
      result: {
        kind: "unreachable",
        response: breedingUnreachable(),
      } satisfies BreedingCallResult,
      copy: "Target is unreachable",
      detail: "dumud",
      alert: false,
    },
    {
      result: {
        kind: "http-invalid",
        reason: "response-shape",
        httpStatus: 200,
        message: "Invalid response.",
      } satisfies BreedingCallResult,
      copy: "Breeding response could not be used",
      detail: "response-shape",
      alert: true,
    },
    {
      result: {
        kind: "network-error",
        message: "Local service offline.",
      } satisfies BreedingCallResult,
      copy: "Breeding service could not be reached",
      detail: "Local service offline",
      alert: true,
    },
  ])("presents distinct $copy state", async ({
    result,
    copy,
    detail,
    alert,
  }) => {
    wrapper = mount(App, {
      props: {
        client: clientWith(),
        breedingClient: breedingClientWith(result),
      },
    });
    await switchToBreeding();
    await fillGoldenBreedingForm();
    await wrapper.get(".breeding-form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain(copy);
    expect(wrapper.text()).toContain(detail);
    expect(wrapper.find('[role="alert"]').exists()).toBe(alert);
  });

  it("renders hostile backend identifiers and messages as inert text", async () => {
    const response = breedingUnreachable();
    response.message = "<img src=x onerror=alert(1)>";
    response.reachable_states[0]!.species_id = "script";
    wrapper = mount(App, {
      props: {
        client: clientWith(),
        breedingClient: breedingClientWith({
          kind: "unreachable",
          response,
        }),
      },
    });
    await switchToBreeding();
    await fillGoldenBreedingForm();
    await wrapper.get(".breeding-form").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("<img src=x onerror=alert(1)>");
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find("script").exists()).toBe(false);
    expect(wrapper.find('a[href^="javascript:"]').exists()).toBe(false);
  });
});
