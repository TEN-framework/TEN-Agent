import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface AuthState {
  isAuthenticated: boolean
  user: string | null
}

const initialState: AuthState = {
  isAuthenticated: false,
  user: null
}

export const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    login: (state, action) => {
      state.isAuthenticated = true
      state.user = action.payload
    },
    logout: (state) => {
      state.isAuthenticated = false
      state.user = null
    },
    setAuthenticated(state, action: PayloadAction<boolean>) {
      state.isAuthenticated = action.payload;
    }
  }
})

export const { setAuthenticated } = authSlice.actions;
export const { login, logout } = authSlice.actions
export default authSlice.reducer