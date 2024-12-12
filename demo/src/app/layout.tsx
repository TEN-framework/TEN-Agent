import { StoreProvider } from "@/store"
import type { Metadata, Viewport } from "next"
import "./global.css"
import { Toaster } from "@/components/ui/sonner"
import { Roboto } from "next/font/google"
import { cn } from "@/lib/utils"

const roboto = Roboto({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-roboto",
  display: "swap",
})

export const metadata: Metadata = {
  title: "TEN Agent",
  description:
    "A Realtime Conversational AI Agent powered by TEN",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black",
  },
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  minimumScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={cn("dark", "antialiased", roboto.variable)}>
        {/* <ConfigProvider
          theme={{
            components: {
              Select: {
                selectorBg: "#181A1D",
              },
            },
          }}
        > */}
        <StoreProvider>{children}</StoreProvider>
        {/* </ConfigProvider> */}
        <Toaster richColors closeButton theme="dark" />
      </body>
    </html>
  )
}
