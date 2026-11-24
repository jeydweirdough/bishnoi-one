import type { ComponentProps } from "react";
import { PageHeader as SharedPageHeader } from "@/src/platform/ui/sheet";
import { FinancePageActions } from "@/src/modules/finance/printing/page-actions";

/** Finance arranges its page actions without changing another app's header. */
export function PageHeader(props: ComponentProps<typeof SharedPageHeader>) {
  return <div className="finance-page-heading">
    <SharedPageHeader {...props} actions={<FinancePageActions>{props.actions}</FinancePageActions>} />
  </div>;
}
