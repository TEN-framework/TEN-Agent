import { cn } from "@/lib/utils"

export default function RTCCard(props: { className?: string }) {
  const { className } = props
  return (
    <>
      <div className={cn("flex-shrink-0", className)}>
        <div className="flex h-full items-center justify-center">
          <div className="text-center">
            {/* <Video className="h-16 w-16 mx-auto mb-4" /> */}
            <h2 className="mb-2 text-xl font-semibold">Audio & Video</h2>
            <p>Your audio and video controls go here.</p>
          </div>
        </div>
      </div>
    </>
  )
}
