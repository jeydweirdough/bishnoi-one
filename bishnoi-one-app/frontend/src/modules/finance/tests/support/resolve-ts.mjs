// Tests only: Finance's code imports its own TypeScript files without an extension
// ("./engine"), as Next.js expects, and through the one app's "@/" (its own folder:
// tsconfig.json "paths"). Node knows neither, so "@/" is turned into the one app's folder,
// and an import not found as written is tried again with ".ts". Nothing outside these
// tests uses it. Moved into the one app 2026-10-24.

const ONE_APP = new URL("../../../../../", import.meta.url);

export async function resolve(specifier, context, next) {
  const wanted = specifier.startsWith("@/") ? new URL(specifier.slice(2), ONE_APP).href : specifier;
  try {
    return await next(wanted, context);
  } catch (error) {
    const local = wanted.startsWith("./") || wanted.startsWith("../") || wanted.startsWith("file:");
    if (error?.code === "ERR_MODULE_NOT_FOUND" && local && !/\.[a-z]+$/i.test(wanted)) return next(`${wanted}.ts`, context);
    throw error;
  }
}
