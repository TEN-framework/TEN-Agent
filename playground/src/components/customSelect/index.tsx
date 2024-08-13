import { Select, SelectProps } from "antd"
import styles from "./index.module.scss"

type CustomSelectProps = SelectProps & {
  prefixIcon?: React.ReactNode;
}

const CustomSelect = (props: CustomSelectProps) => {

  const { prefixIcon, className, ...rest } = props;

  return <div className={`${styles.selectWrapper} ${className}`}>
    {prefixIcon && <div className={styles.prefixIconWrapper}>{prefixIcon}</div>}
    <Select {...rest} rootClassName="customSelect"></Select>
  </div>
}


export default CustomSelect
