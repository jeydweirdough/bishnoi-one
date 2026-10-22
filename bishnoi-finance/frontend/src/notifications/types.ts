// Finance's notifications, as GET /finance/notifications sends them (app/notify.py makes them).

export type Notice = {
  id: string;
  /** entry.waiting, entry.approved, entry.rejected, fund.to_release, fund.to_check, fund.to_settle */
  kind: string;
  text: string;
  /** The page it's about, inside Finance. */
  link: string | null;
  at: string;
  read: boolean;
};

export type Inbox = { unread: number; items: Notice[] };
