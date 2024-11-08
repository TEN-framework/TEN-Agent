import { LogoIcon, SmallLogoIcon } from "@/components/Icon"
import { HeaderRoomInfo, HeaderActions } from "./HeaderComponents"
import { cn } from "@/lib/utils"

export default function Header(props: { className?: string }) {
  const { className } = props
  return (
    <>
      {/* Header */}
      <header
        className={cn(
          "flex items-center justify-between bg-[#181a1d] p-2 md:p-4",
          className,
        )}
      >
        <div className="flex items-center space-x-2">
          {/* <LogoIcon className="hidden h-5 md:block" />
          <SmallLogoIcon className="block h-4 md:hidden" /> */}
          <h1 className="text-sm font-bold md:text-xl">TEN Agent</h1>
        </div>
        <HeaderRoomInfo />
        <HeaderActions />
      </header>
    </>
  )
}
