export interface AudioVisualizerProps {
  type: "agent" | "user"
  frequencies: Float32Array[]
  gap: number
  barWidth: number
  minBarHeight: number
  maxBarHeight: number
  borderRadius: number
}

export default function AudioVisualizer(props: AudioVisualizerProps) {
  const {
    frequencies,
    gap,
    barWidth,
    minBarHeight,
    maxBarHeight,
    borderRadius,
    type,
  } = props

  const summedFrequencies = frequencies.map((bandFrequencies) => {
    const sum = bandFrequencies.reduce((a, b) => a + b, 0)
    if (sum <= 0) {
      return 0
    }
    return Math.sqrt(sum / bandFrequencies.length)
  })

  return (
    <div
      className={`flex items-center justify-center`}
      style={{ gap: `${gap}px` }}
    >
      {summedFrequencies.map((frequency, index) => {
        const style = {
          height:
            minBarHeight + frequency * (maxBarHeight - minBarHeight) + "px",
          borderRadius: borderRadius + "px",
          width: barWidth + "px",
          transition:
            "background-color 0.35s ease-out, transform 0.25s ease-out",
          // transform: transform,
          backgroundColor: type === "agent" ? "#0888FF" : "#EAECF0",
          boxShadow: type === "agent" ? "0 0 10px #EAECF0" : "none",
        }

        return <span key={index} style={style} />
      })}
    </div>
  )
}
