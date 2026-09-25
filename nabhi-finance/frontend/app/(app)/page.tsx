import Screen from "../../src/screens/overview";

export { metadata } from "../../src/screens/overview";

/**
 * The route. In the Nabhi shell this screen sits at `/m/[module]` and takes the
 * module from the URL; here the app *is* Finance, so the route says so and the
 * screen stays the same either way.
 */
export default function Page({ searchParams }: PageProps<"/">) {
  return <Screen params={Promise.resolve({ module: "finance" })} searchParams={searchParams} />;
}
