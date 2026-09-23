import Screen from "../../src/screens/overview";

export { metadata } from "../../src/screens/overview";

/**
 * The route. In the Orbit shell this screen sat under `/m/[module]/…` and
 * read the module from the URL; here the app *is* Inventory, so the route
 * says so and the screen is unchanged either way.
 */
export default function Page({ searchParams }: PageProps<"/">) {
  return <Screen params={Promise.resolve({ module: "inventory" })} searchParams={searchParams} />;
}
