export interface IconProps {
  width?: number
  height?: number
  color?: string
  viewBox?: string
  size?: "small" | "default"
  // style?: React.CSSProperties
  transform?: string
  onClick?: () => void
}
