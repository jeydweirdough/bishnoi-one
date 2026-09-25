import Screen from "../../../src/screens/letters";

export { metadata } from "../../../src/screens/letters";

/**
 * The route. In the Nabhi shell this screen sits under `/m/[module]/letters`
 * and takes the module from the URL; here the app *is* Finance, so the route
 * says so and the screen stays the same either way.
 */
export default function Page({ searchParams }: PageProps<"/letters">) {
  return <Screen params={Promise.resolve({ module: "finance" })} searchParams={searchParams} />;
}
