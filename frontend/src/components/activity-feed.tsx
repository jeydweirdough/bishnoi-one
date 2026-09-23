"use client";

import { createContext, useContext, useOptimistic, type ReactNode } from "react";
import type { Activity } from "@/src/platform/lib/types";

type Feed = { activities: Activity[]; add: (activity: Activity) => void };

const FeedContext = createContext<Feed | null>(null);

/**
 * A customer's history, shared by the log form and the timeline so a logged
 * call shows up the moment it's saved. The optimistic entry lasts while the
 * save runs; when the server's copy arrives it takes its place, and if the save
 * fails it simply goes away.
 */
export function ActivityFeed({ activities, children }: { activities: Activity[]; children: ReactNode }) {
  const [shown, add] = useOptimistic(activities, (list: Activity[], activity: Activity) => [activity, ...list]);
  return <FeedContext.Provider value={{ activities: shown, add }}>{children}</FeedContext.Provider>;
}

export function useActivityFeed(): Feed | null {
  return useContext(FeedContext);
}

export const isPending = (id: string) => id.startsWith("pending-");
