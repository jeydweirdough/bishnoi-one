import Screen from "../../../src/screens/approvals";

export { metadata } from "../../../src/screens/approvals";

/**
 * The route. In the Nabhi shell this screen sits under `/m/[module]/approvals`
 * and takes the module from the URL; here the app *is* Finance, so the route
 * says so and the screen stays the same either way.
 */
export default function Page({ searchParams }: PageProps<"/approvals">) {
  return <Screen params={Promise.resolve({ module: "finance" })} searchParams={searchParams} />;
}
