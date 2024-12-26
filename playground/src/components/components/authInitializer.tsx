import { useEffect, ReactNode } from "react";
import { useRouter } from "next/router";
import { useAppSelector } from "@/common";
import { RootState } from "@/store";

interface AuthInitializerProps {
  children: ReactNode;
}

const AuthInitializer = ({ children }: AuthInitializerProps) => {
  const router = useRouter();
  const isAuthenticated = useAppSelector((state: RootState) => state.auth.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
};

export default AuthInitializer;