import { cn } from "@/lib/utils"

export default function ChatCard(props: { className?: string }) {
  const { className } = props
  return (
    <>
      {/* Chat Card */}
      <div className={cn("flex-grow", className)}>
        <div className="flex h-full w-full flex-col">
          <div className="flex-grow overflow-y-auto p-4">
            {/* Chat messages would go here */}
            <p className="mb-2">User 1: Hello!</p>
            <p className="mb-2">User 2: Hi there!</p>
          </div>
          <div className="border-t p-4">
            <input
              type="text"
              placeholder="Type a message..."
              className="w-full rounded border p-2"
            />
          </div>
        </div>
      </div>
    </>
  )
}
