"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export const PROJECT_QUERY_PARAM = "project";

export function useProjectScope() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const search = searchParams.toString();
  const project = searchParams.get(PROJECT_QUERY_PARAM) || "";

  const setProject = useCallback(
    (nextProject: string) => {
      const params = new URLSearchParams(search);
      const cleaned = nextProject.trim();
      if (cleaned) {
        params.set(PROJECT_QUERY_PARAM, cleaned);
      } else {
        params.delete(PROJECT_QUERY_PARAM);
      }
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [pathname, router, search],
  );

  return { project, setProject };
}

export function scopedHref(href: string, project: string) {
  if (!project) return href;
  const [path, rawQuery = ""] = href.split("?");
  const params = new URLSearchParams(rawQuery);
  params.set(PROJECT_QUERY_PARAM, project);
  return `${path}?${params.toString()}`;
}
