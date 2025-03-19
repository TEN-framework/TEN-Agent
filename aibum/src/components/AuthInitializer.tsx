'use client';

import { ReactNode, useEffect } from "react";
import { getOptionsFromLocal, setOptionsToLocal } from "@/common/storage";
import { getRandomChannel } from "@/common/utils";

interface AuthInitializerProviderProps {
  children: ReactNode;
}

export default function AuthInitializerProvider({ children }: AuthInitializerProviderProps) {
  useEffect(() => {
    if (typeof window !== "undefined") {
      const options = getOptionsFromLocal();
      if (!options.channel) {
        // 只设置随机 channel
        const newOptions = {
          ...options,
          channel: getRandomChannel(),
        };
        setOptionsToLocal(newOptions);
      }
    }
  }, []);

  return <>{children}</>;
} 