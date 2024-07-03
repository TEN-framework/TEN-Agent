import Image from 'next/image'
import logoSrc from "@/assets/logo.png"

interface LogoProps {
  width?: number
  height?: number
}

const Logo = (props: LogoProps) => {
  const { width = 100, height = 100 } = props

  return <Image width={width} height={height} src={logoSrc} alt="Logo"></Image>
}

export default Logo 
