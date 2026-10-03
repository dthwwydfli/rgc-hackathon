import type { AppPaths, Moment, Persona, Product } from "./types";
import { assertArray, assertObject, fetchJson } from "./parse-json";

function parseProducts(raw: unknown): { products: Product[] } {
  const root = assertObject(raw, "products.json");
  const products = assertArray(root.products, "products") as Product[];
  for (const product of products) {
    assertObject(product, "product");
    if (!product.id || !product.name) {
      throw new Error("product requires id and name");
    }
    if (!Number.isInteger(product.price_pence)) {
      throw new Error(`product ${product.id}: price_pence must be integer`);
    }
  }
  return { products };
}

function parsePersonas(raw: unknown): { personas: Persona[] } {
  const root = assertObject(raw, "personas.json");
  const personas = assertArray(root.personas, "personas") as Persona[];
  return { personas };
}

function parseMoments(raw: unknown): { moments: Moment[] } {
  const root = assertObject(raw, "moments.json");
  const moments = assertArray(root.moments, "moments") as Moment[];
  for (const moment of moments) {
    if (!Number.isInteger(moment.start_minute) || !Number.isInteger(moment.end_minute)) {
      throw new Error(`moment ${moment.id}: start_minute and end_minute must be integers`);
    }
    if (moment.end_minute <= moment.start_minute) {
      throw new Error(`moment ${moment.id}: end_minute must be after start_minute`);
    }
  }
  return { moments };
}

export async function loadConfig(paths: AppPaths) {
  try {
    const [products, personas, moments] = await Promise.all([
      fetchJson(paths.products).then(parseProducts),
      fetchJson(paths.personas).then(parsePersonas),
      fetchJson(paths.moments).then(parseMoments),
    ]);
    return { products, personas, moments, source: "live" as const, usedMock: false };
  } catch (liveError) {
    const [products, personas, moments] = await Promise.all([
      fetchJson(paths.mockProducts).then(parseProducts),
      fetchJson(paths.mockPersonas).then(parsePersonas),
      fetchJson(paths.mockMoments).then(parseMoments),
    ]);
    return {
      products,
      personas,
      moments,
      source: "mock" as const,
      usedMock: true,
      liveError: liveError instanceof Error ? liveError.message : String(liveError),
    };
  }
}
