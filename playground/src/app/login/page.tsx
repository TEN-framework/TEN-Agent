// src/app/login/page.tsx
'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useDispatch } from 'react-redux'
import { setAuthenticated } from '@/store/reducers/authReducer'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const router = useRouter()
  const dispatch = useDispatch()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Perform login logic here
    const token = "your-authentication-token"; // Replace with actual token
    localStorage.setItem("authToken", token);
    dispatch(setAuthenticated(true));
    router.push('/chatbot');
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <input
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="Username"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      <button type="submit">Login</button>
    </form>
  )
}