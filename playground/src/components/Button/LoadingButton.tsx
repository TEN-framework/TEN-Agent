import { Button, ButtonProps } from "@/components/ui/button"
import { AnimatedSpinnerIcon } from "@/components/Icon"

export interface LoadingButtonProps extends Omit<ButtonProps, "asChild"> {
  loading?: boolean
  svgProps?: React.SVGProps<SVGSVGElement>
}

export function LoadingButton(props: LoadingButtonProps) {
  const { loading, disabled, children, svgProps, ...rest } = props
  return (
    <Button {...rest} disabled={loading || disabled}>
      {loading && <AnimatedSpinnerIcon {...svgProps} />}
      {children}
    </Button>
  )
}
