import Screen from "../../../../src/screens/product";

/**
 * The route. In the Orbit shell this screen sat under `/m/[module]/…` and
 * read the module from the URL; here the app *is* Inventory, so the route
 * says so and the screen is unchanged either way.
 */
export default function Page(p: { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  return (
    <Screen
      params={p.params.then((v) => ({ ...v, module: "inventory" }))}
      searchParams={p.searchParams}
    />
  );
}
