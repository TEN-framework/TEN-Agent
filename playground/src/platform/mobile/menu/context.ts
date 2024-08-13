import { createContext } from "react"

export interface MenuContextType {
  scrollToBottom: () => void;
}

export const MenuContext = createContext<MenuContextType>({
  scrollToBottom: () => { }
});
