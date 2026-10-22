// Tests only: Finance's code imports its own TypeScript files without an extension
// ("./engine"), as Next.js expects. Node needs the extension, so when a relative import
// isn't found as written, this tries it with ".ts". Nothing outside tests/ uses it.

export async function resolve(specifier, context, next) {
  try {
    return await next(specifier, context);
  } catch (error) {
    const relative = specifier.startsWith("./") || specifier.startsWith("../");
    if (error?.code === "ERR_MODULE_NOT_FOUND" && relative && !/\.[a-z]+$/i.test(specifier)) return next(`${specifier}.ts`, context);
    throw error;
  }
}
