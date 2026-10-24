// Finance's notifications, as GET /finance/notifications sends them (app/notify.py makes them).

export type Notice = {
  /** One notification's id, or "group:<kind>" for several unread of a kind shown as one line. */
  id: string;
  /** The notifications this line stands for (one, or the group's). */
  ids: string[];
  /** Whether it asks something of you (counts in the red number); news doesn't. */
  counts: boolean;
  /** entry.waiting, entry.approved, entry.rejected, fund.to_release, fund.to_check, fund.to_settle */
  kind: string;
  text: string;
  /** The page it's about, inside Finance. */
  link: string | null;
  at: string;
  read: boolean;
};

export type Inbox = { unread: number; items: Notice[] };
