"use client"

import { type SWRResponse, type SWRConfiguration } from "swr"
import useSWR from "swr"

// https://github.com/vercel/swr/discussions/2330#discussioncomment-4460054
export function useCancelableSWR<T>(
  key: string,
  opts?: SWRConfiguration,
): [SWRResponse<T>, AbortController] {
  const controller = new AbortController()
  return [
    useSWR(
      key,
      (url: string) =>
        fetch(url, { signal: controller.signal }).then((res) => res.json()),
      {
        // revalidateOnFocus: false,
        errorRetryCount: 3,
        refreshInterval: 1000 * 60,
        // dedupingInterval: 30000,
        // focusThrottleInterval: 60000,
        ...opts,
      },
    ),
    controller,
  ]
  // to use it:
  // const [{ data }, controller] = useCancelableSWR('/api')
  // ...
  // controller.abort()
}
